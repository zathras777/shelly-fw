import ipaddress
import socket
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

import requests


class FirmwareHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type) -> None:
        super().__init__(server_address, handler_class)
        self._active_requests = 0
        self._last_activity = time.monotonic()
        self._idle_condition = threading.Condition()

    def request_started(self) -> None:
        with self._idle_condition:
            self._active_requests += 1
            self._last_activity = time.monotonic()
            self._idle_condition.notify_all()

    def request_finished(self) -> None:
        with self._idle_condition:
            self._active_requests -= 1
            self._last_activity = time.monotonic()
            self._idle_condition.notify_all()

    def wait_for_idle(self, idle_seconds: float, timeout: float) -> bool:
        deadline = time.monotonic() + timeout

        with self._idle_condition:
            while True:
                now = time.monotonic()
                idle_for = now - self._last_activity

                if self._active_requests == 0 and idle_for >= idle_seconds:
                    return True

                if now >= deadline:
                    return False

                if self._active_requests == 0:
                    wait_for = min(deadline - now, idle_seconds - idle_for)
                else:
                    wait_for = deadline - now

                self._idle_condition.wait(max(0.1, wait_for))


class FirmwareRequestHandler(SimpleHTTPRequestHandler):
    def handle(self) -> None:
        if isinstance(self.server, FirmwareHTTPServer):
            self.server.request_started()

        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if isinstance(self.server, FirmwareHTTPServer):
                self.server.request_finished()

    def finish(self) -> None:
        try:
            super().finish()
        except (BrokenPipeError, ConnectionResetError):
            pass


class FirmwareStore:
    def __init__(self) -> None:
        self._tmp = TemporaryDirectory(prefix="shelly-fw-")
        self.path = Path(self._tmp.name)
        self.downloaded = 0

    def download(self, url: str, filename: str) -> Path:
        target = self.path / filename
        response = requests.get(url, verify=False)
        with open(target, "wb") as f:
            f.write(response.content)
        self.downloaded += 1
        return target

    def cleanup(self) -> None:
        self._tmp.cleanup()

    def __enter__(self) -> "FirmwareStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.cleanup()


class FirmwareServer:
    def __init__(
        self,
        directory: Path,
        subnet: str | ipaddress.IPv4Network,
        host: str = "0.0.0.0",
        port: int = 8007,
    ) -> None:
        self.directory = directory
        self.bind_host = host
        self.host = local_ip_for_network(subnet)
        self.port = port
        self._server: FirmwareHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            return

        handler = partial(
            FirmwareRequestHandler,
            directory=str(self.directory),
        )
        self._server = FirmwareHTTPServer((self.bind_host, self.port), handler)
        self.port = self._server.server_port
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="shelly-fw-http",
            daemon=True,
        )
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def url_for(self, path: Path | str) -> str:
        filename = path.name if isinstance(path, Path) else path
        return f"{self.base_url}/{quote(filename)}"

    def wait_for_idle(self, idle_seconds: float = 10.0, timeout: float = 300.0) -> bool:
        if self._server is None:
            return True

        return self._server.wait_for_idle(idle_seconds=idle_seconds, timeout=timeout)

    def stop(self) -> None:
        if self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()

        if self._thread is not None:
            self._thread.join()

        self._server = None
        self._thread = None


def local_ip_for_network(subnet: str | ipaddress.IPv4Network) -> str:
    network = ipaddress.ip_network(subnet)
    target = str(next(network.hosts()))

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((target, 1))
        return sock.getsockname()[0]
