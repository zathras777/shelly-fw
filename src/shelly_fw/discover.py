from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from operator import ge

import requests


@dataclass(frozen=True)
class ShellyDevice:
    ip: IPv4Address
    generation: int
    model: str
    app: str | None
    version: str | None
    device_id: str | None
    mac: str | None


def discover_devices(
    network: IPv4Network,
    include_gen1: bool = False,
    timeout: float = 2.0,
    workers: int = 50,
) -> list[ShellyDevice]:
    hosts = list(network.hosts())
    devices: list[ShellyDevice] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(discover_device, host, include_gen1, timeout): host
            for host in hosts
        }

        for future in as_completed(futures):
            device = future.result()
            if device is not None:
                devices.append(device)

    return sorted(devices, key=lambda device: int(device.ip))


def discover_device(
    ip: IPv4Address,
    include_gen1: bool,
    timeout: float,
) -> ShellyDevice | None:
    gen2 = discover_gen2_device(ip, timeout)
    if gen2 is not None:
        return gen2

    if include_gen1:
        return discover_gen1_device(ip, timeout)

    return None


def group_devices_by_app(
    devices: list[ShellyDevice],
) -> dict[str, list[ShellyDevice]]:
    grouped: dict[str, list[ShellyDevice]] = {}

    for device in devices:
        if device.app is None:
            continue

        grouped.setdefault(device.app, []).append(device)

    return grouped


def discover_gen2_device(
    ip: IPv4Address,
    timeout: float,
) -> ShellyDevice | None:
    url = f"http://{ip}/rpc/Shelly.GetDeviceInfo"

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None
    except ValueError:
        return None

    model = data.get("model")
    generation = data.get("gen")

    if not model or generation is None:
        return None

    try:
        generation = int(generation)
    except ValueError:
        return None

    return ShellyDevice(
        ip=ip,
        generation=generation,
        model=str(model),
        app=_optional_str(data.get("app")),
        version=_optional_str(data.get("ver")),
        device_id=_optional_str(data.get("id")),
        mac=_optional_str(data.get("mac")),
    )


def discover_gen1_device(
    ip: IPv4Address,
    timeout: float,
) -> ShellyDevice | None:
    url = f"http://{ip}/shelly"

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None
    except ValueError:
        return None

    device_type = data.get("type")

    if not device_type:
        return None

    return ShellyDevice(
        ip=ip,
        generation=1,
        model=str(device_type),
        app=None,
        version=_optional_str(data.get("fw")),
        device_id=None,
        mac=_optional_str(data.get("mac")),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None
