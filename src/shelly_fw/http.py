import ipaddress
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

import requests


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
        subnet: ipaddress.IPv4Network,
        host: str = "0.0.0.0",
        port: int = 8007,
    ) -> None:
        self.directory = directory
        self.bind_host = host
        self.host = local_ip_for_network(subnet)
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            return

        handler = partial(
            SimpleHTTPRequestHandler,
            directory=str(self.directory),
        )
        self._server = ThreadingHTTPServer((self.bind_host, self.port), handler)
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

    def stop(self) -> None:
        if self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()

        if self._thread is not None:
            self._thread.join()

        self._server = None
        self._thread = None


def local_ip_for_network(subnet: ipaddress.IPv4Network) -> str:
    target = str(next(subnet.hosts()))

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((target, 1))
        return sock.getsockname()[0]
