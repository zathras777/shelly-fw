from __future__ import annotations

import argparse
import ipaddress

from .discover import discover_devices, group_devices_by_app
from .firmware import Firmware
from .http import FirmwareServer, FirmwareStore


def parse_ipv4_network(value: str) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"'{value}' is not a valid subnet. "
            "Use something like 10.0.74.0/24, or 10.0.74.15/32 for one device."
        ) from exc

    if not isinstance(network, ipaddress.IPv4Network):
        raise argparse.ArgumentTypeError("Only IPv4 networks are supported")

    return network


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="shelly-fw",
        description="Discover and update Shelly devices on a local network.",
    )

    parser.add_argument(
        "subnet",
        type=parse_ipv4_network,
        help="Subnet to scan, e.g. 10.0.74.0/24",
    )

    parser.add_argument(
        "--include-gen1",
        action="store_true",
        default=False,
        help="Also scan for Gen1 Shelly devices using the /shelly endpoint.",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="HTTP timeout per device in seconds. Default: 2.0",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be done without applying updates.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply firmware updates.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=50,
        help="Number of parallel scan workers. Default: 50",
    )

    parser.add_argument(
        "--serve-timeout",
        type=float,
        default=300.0,
        help="Seconds to keep the firmware server available after update requests. Default: 300",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Scanning subnet {args.subnet} using {args.workers} workers...")

    devices = discover_devices(
        network=args.subnet,
        include_gen1=args.include_gen1,
        timeout=args.timeout,
        workers=args.workers,
    )

    if not devices:
        print("No Shelly devices found.")
        return
    print(f"Found {len(devices)} device(s)\n")

    apps = group_devices_by_app(devices)
    firmwares = []
    updates_rqd = 0

    with FirmwareStore() as store:
        for app, app_devices in apps.items():
            fw = Firmware(app=app, devices=app_devices)
            fw_details = fw.get_firmware_details()
            if fw_details is False:
                print("Unable to get firmware details for app: ", app)
                continue
            needed = fw.check_device_firmware()
            if needed == 0:
                continue
            updates_rqd += needed
            firmwares.append(fw)
            fw.download_firmware(store)

        if updates_rqd == 0:
            print("No firmware updates were required. Exiting...")
            return

        if store.downloaded == 0:
            print("No firmware updates were downloaded. Exiting...")
            return

        print(f"{updates_rqd} device(s) need updated...\n")

        server = FirmwareServer(store.path, args.subnet)
        server.start()
        try:
            for fw in firmwares:
                print(f"Updating {fw.app} device(s)...")
                fw.update_devices(server)

            print("\nWaiting for firmware to be downloaded...")
            if not server.wait_for_idle(timeout=args.serve_timeout):
                print("Firmware server timeout reached while downloads may still be active.")
        finally:
            server.stop()


if __name__ == "__main__":
    main()
