#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import sys

from bleak import BleakScanner
from automower_ble.mower import Mower


# ---------------------------------------------------------------------------
# Mo configuration
# ---------------------------------------------------------------------------

ADDRESS = os.environ["MO_ADDRESS"]
CHANNEL_ID = int(os.environ["MO_CHANNEL_ID"])
PIN = int(os.environ["MO_PIN"])

# Keep the automower library quiet unless something goes wrong.
logging.getLogger("automower_ble").setLevel(logging.WARNING)
logging.getLogger("bleak").setLevel(logging.WARNING)


def enum_name(value):
    """Return a friendly name for an enum-like result."""
    if value is None:
        return "Unknown"

    try:
        return value.name
    except AttributeError:
        return str(value)


async def connect_to_mo():
    print("Looking for Mo...")

    device = await BleakScanner.find_device_by_address(
        ADDRESS,
        timeout=30,
    )

    if device is None:
        print("ERROR: Mo not found.")
        print("Try waking/power-cycling the mower and run the command again.")
        return None

    mower = Mower(
        CHANNEL_ID,
        ADDRESS,
        pin=PIN,
    )

    try:
        result = await mower.connect(device)
    except Exception as exc:
        print(f"ERROR: Unable to connect to Mo: {exc}")
        return None

    if result != 0:
        print(f"ERROR: Connection failed: {result}")
        try:
            await mower.disconnect()
        except Exception:
            pass
        return None

    return mower


async def show_status(mower):
    print("\nMo Status")
    print("=" * 40)

    manufacturer = await mower.get_manufacturer()
    model = await mower.get_model()
    battery = await mower.battery_level()
    charging = await mower.is_charging()
    state = await mower.mower_state()
    activity = await mower.mower_activity()
    name = await mower.command("GetUserMowerNameAsAsciiString")
    serial = await mower.command("GetSerialNumber")
    next_start = await mower.mower_next_start_time()

    print(f"Name          : {name}")
    print(f"Manufacturer  : {manufacturer}")
    print(f"Model         : {model}")
    print(f"Serial        : {serial}")
    print(f"Battery       : {battery}%")
    print(f"Charging      : {'Yes' if charging else 'No'}")
    print(f"State         : {enum_name(state)}")
    print(f"Activity      : {enum_name(activity)}")

    if next_start:
        print(f"Next start    : {next_start:%Y-%m-%d %H:%M:%S}")
    else:
        print("Next start    : None")

    print("=" * 40)


async def send_command(mower, command):
    if command == "park":
        print("Sending PARK command to Mo...")
        result = await mower.mower_park()

    elif command == "pause":
        print("Sending PAUSE command to Mo...")
        result = await mower.mower_pause()

    elif command == "resume":
        print("Sending RESUME command to Mo...")
        result = await mower.mower_resume()

    elif command == "override":
        print("Starting 3-hour mowing override...")
        result = await mower.mower_override()

    else:
        print(f"Unknown command: {command}")
        return

    print(f"Command result: {result}")


async def main():
    parser = argparse.ArgumentParser(
        description="Control Mo - Flymo EasiLife Go 150 via Bluetooth"
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=[
            "status",
            "park",
            "pause",
            "resume",
            "override",
        ],
        help="Command to send to Mo",
    )

    args = parser.parse_args()

    mower = await connect_to_mo()

    if mower is None:
        sys.exit(1)

    try:
        if args.command == "status":
            await show_status(mower)
        else:
            await send_command(mower, args.command)

    except Exception as exc:
        print(f"ERROR: {exc}")

    finally:
        try:
            await mower.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
