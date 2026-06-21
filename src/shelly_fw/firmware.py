import re
from dataclasses import dataclass
from pathlib import Path

import requests
import urllib3
from packaging.version import Version

from .discover import ShellyDevice
from .http import FirmwareServer, FirmwareStore

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_SHELLY_VERSION_RE = re.compile(
    r"v?"
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:[-_.]?(?P<pre>alpha|a|beta|b|rc|dev)(?P<pre_num>\d+)?)?",
    re.IGNORECASE,
)

_PRERELEASE_TAGS = {
    "alpha": "a",
    "a": "a",
    "beta": "b",
    "b": "b",
    "rc": "rc",
    "dev": "dev",
}


@dataclass(frozen=True)
class FirmwareVersion:
    version: str
    build_id: str
    url: str


@dataclass(frozen=True)
class FirmwareInfo:
    stable: FirmwareVersion
    beta: FirmwareVersion | None
    time: int


def parse_firmware_info(data: dict) -> FirmwareInfo:
    stable = FirmwareVersion(**data["stable"])

    beta = None
    if "beta" in data:
        beta = FirmwareVersion(**data["beta"])

    return FirmwareInfo(
        stable=stable,
        beta=beta,
        time=data["time"],
    )


def parse_shelly_version(version: str) -> Version | None:
    match = _SHELLY_VERSION_RE.search(version.strip())
    if match is None:
        return None

    normalized = (
        f"{match.group('major')}.{match.group('minor')}.{match.group('patch')}"
    )
    pre = match.group("pre")
    if pre is not None:
        tag = _PRERELEASE_TAGS[pre.lower()]
        number = match.group("pre_num") or "0"
        normalized = f"{normalized}{tag}{number}"

    return Version(normalized)


def choose_firmware_channel(current_version: str, info: FirmwareInfo) -> str | None:
    current = parse_shelly_version(current_version)
    if current is None:
        return None

    # Device is already on beta/dev/rc etc.
    if current.is_prerelease:
        if info.beta is None:
            return None

        beta = parse_shelly_version(info.beta.version)
        if beta is None:
            return None

        if beta > current:
            return "beta"

        return None

    # Device is on stable. Do not jump to beta automatically.
    if info.stable.version is None:
        return None

    stable = parse_shelly_version(info.stable.version)
    if stable is None:
        return None

    if stable > current:
        return "stable"

    return None


def get_channel_firmware_url(info: FirmwareInfo, channel: str) -> str:
    if channel == "stable":
        return info.stable.url
    elif channel == "beta":
        if info.beta is None:
            raise ValueError("Beta channel is not available")
        return info.beta.url
    else:
        raise ValueError(f"Invalid channel: {channel}")


class Firmware:
    def __init__(self, app: str, devices: list[ShellyDevice]):
        self.app = app
        self.devices = devices
        self.info: FirmwareInfo | None = None
        self.required: dict[str, list[ShellyDevice]] = {}
        self.files: dict[str, Path] = {}

    def __str__(self) -> str:
        return f"Firmware(app={self.app}, devices={len(self.devices)})"

    def get_firmware_details(self) -> bool:
        url = f"https://updates.shelly.cloud/update/{self.app}"
        response = requests.get(url, verify=False)
        data = response.json()
        self.info = parse_firmware_info(data)
        return self.info is not None

    def check_device_firmware(self) -> int:
        if self.info is None:
            return False
        self.required = {}
        updates_required = 0
        for device in self.devices:
            if device.version is None:
                continue
            channel = choose_firmware_channel(device.version, self.info)
            if channel is None:
                continue
            self.required.setdefault(channel, []).append(device)
            updates_required += 1
        return updates_required

    def download_firmware(self, store: FirmwareStore):
        if self.info is None:
            return False

        for channel, _ in self.required.items():
            firmware_filename = f"{self.app}-{channel}-firmware.zip"
            url = get_channel_firmware_url(self.info, channel)
            store.download(url, firmware_filename)
        return True

    def update_devices(self, server: FirmwareServer):
        for channel, devices in self.required.items():
            firmware_url = server.url_for(f"{self.app}-{channel}-firmware.zip")
            for device in devices:
                print(f"  {device.ip} -> {firmware_url}")
                device_url = f"http://{device.ip}/ota"
                print(f"    {device_url}")
                response = requests.get(device_url, params={"url": firmware_url})
                print(f"    {response.status_code} {response.reason}")
