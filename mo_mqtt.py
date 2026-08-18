#!/usr/bin/env python3

import asyncio
import json
import logging
import os
import time

import paho.mqtt.client as mqtt
from bleak import BleakScanner
from automower_ble.mower import Mower

# ============================================================
# Mo configuration
# ============================================================

ADDRESS = os.environ["MO_ADDRESS"]
CHANNEL_ID = int(os.environ["MO_CHANNEL_ID"])
PIN = int(os.environ["MO_PIN"])


# ============================================================
# MQTT configuration
# ============================================================

MQTT_HOST = os.environ["MO_MQTT_HOST"]
MQTT_PORT = int(os.getenv("MO_MQTT_PORT", "1883"))

MQTT_USERNAME = os.getenv("MO_MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MO_MQTT_PASSWORD")

BASE_TOPIC = "flymo/mo"

STATE_TOPIC = f"{BASE_TOPIC}/state"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/availability"
COMMAND_TOPIC = f"{BASE_TOPIC}/command"


# ============================================================
# General settings
# ============================================================

POLL_INTERVAL = 60

logging.getLogger("automower_ble").setLevel(logging.WARNING)
logging.getLogger("bleak").setLevel(logging.WARNING)


# ============================================================
# Helpers
# ============================================================

def enum_name(value):
    if value is None:
        return "UNKNOWN"

    try:
        return value.name
    except AttributeError:
        return str(value)


# ============================================================
# MQTT callbacks
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"MQTT connected: {reason_code}")

    if reason_code == 0:
        client.subscribe(COMMAND_TOPIC)
        print(f"Listening for commands on {COMMAND_TOPIC}")


def on_message(client, userdata, msg):
    command = msg.payload.decode().strip().lower()

    print(f"MQTT command received: {command}")

    loop = userdata["loop"]
    ble_lock = userdata["ble_lock"]

    asyncio.run_coroutine_threadsafe(
        send_mower_command(command, ble_lock),
        loop
    )


def create_mqtt_client(loop, ble_lock):
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="mo-ble-bridge"
    )

    client.user_data_set(
        {
            "loop": loop,
            "ble_lock": ble_lock,
        }
    )

    client.on_connect = on_connect
    client.on_message = on_message

    if MQTT_USERNAME:
        client.username_pw_set(
            MQTT_USERNAME,
            MQTT_PASSWORD
        )

    client.will_set(
        AVAILABILITY_TOPIC,
        payload="offline",
        retain=True
    )

    client.connect(
        MQTT_HOST,
        MQTT_PORT,
        60
    )

    client.loop_start()

    return client


# ============================================================
# Home Assistant MQTT Discovery
# ============================================================

def publish_discovery(client):
    device = {
        "identifiers": ["flymo_easilife_go_150_mo"],
        "name": "Mo",
        "manufacturer": "Flymo",
        "model": "Easilife Go 150",
    }

    entities = {

        # ----------------------------------------------------
        # Current mower status
        # ----------------------------------------------------

        "battery": {
            "component": "sensor",
            "name": "Battery",
            "value_template": "{{ value_json.battery }}",
            "unit_of_measurement": "%",
            "device_class": "battery",
            "state_class": "measurement",
            "icon": "mdi:battery",
        },

        "charging": {
            "component": "binary_sensor",
            "name": "Charging",
            "value_template":
                "{{ 'ON' if value_json.charging else 'OFF' }}",
            "device_class": "battery_charging",
            "icon": "mdi:battery-charging",
        },

        "state": {
            "component": "sensor",
            "name": "State",
            "value_template": "{{ value_json.state }}",
            "icon": "mdi:robot-mower",
        },

        "activity": {
            "component": "sensor",
            "name": "Activity",
            "value_template": "{{ value_json.activity }}",
            "icon": "mdi:robot-mower-outline",
        },

        "next_start": {
            "component": "sensor",
            "name": "Next Start",
            "value_template": "{{ value_json.next_start }}",
            "device_class": "timestamp",
            "icon": "mdi:calendar-clock",
        },

        # ----------------------------------------------------
        # Lifetime statistics
        # ----------------------------------------------------

        "lifetime_running": {
            "component": "sensor",
            "name": "Lifetime Running",
            "value_template":
                "{{ (value_json.total_running_seconds / 3600) | round(1) }}",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "icon": "mdi:timer-outline",
        },

        "lifetime_cutting": {
            "component": "sensor",
            "name": "Lifetime Cutting",
            "value_template":
                "{{ (value_json.total_cutting_seconds / 3600) | round(1) }}",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "icon": "mdi:grass",
        },

        "lifetime_charging": {
            "component": "sensor",
            "name": "Lifetime Charging",
            "value_template":
                "{{ (value_json.total_charging_seconds / 3600) | round(1) }}",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "icon": "mdi:battery-charging",
        },

        "lifetime_searching": {
            "component": "sensor",
            "name": "Lifetime Searching",
            "value_template":
                "{{ (value_json.total_searching_seconds / 3600) | round(1) }}",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "icon": "mdi:map-search-outline",
        },

        "charging_cycles": {
            "component": "sensor",
            "name": "Charging Cycles",
            "value_template":
                "{{ value_json.number_of_charging_cycles }}",
            "state_class": "total_increasing",
            "icon": "mdi:battery-sync",
        },

        "collisions": {
            "component": "sensor",
            "name": "Collisions",
            "value_template":
                "{{ value_json.number_of_collisions }}",
            "state_class": "total_increasing",
            "icon": "mdi:car-crash",
        },

        "blade_usage": {
            "component": "sensor",
            "name": "Blade Usage",
            "value_template":
                "{{ (value_json.blade_usage_seconds / 3600) | round(1) }}",
            "unit_of_measurement": "h",
            "state_class": "total_increasing",
            "icon": "mdi:content-cut",
        },
    }

    # --------------------------------------------------------
    # Publish sensor discovery
    # --------------------------------------------------------

    for object_id, config in entities.items():
        config = config.copy()

        component = config.pop("component")
        name = config.pop("name")

        payload = {
            "name": name,
            "unique_id": f"mo_{object_id}",
            "state_topic": STATE_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "device": device,
            **config,
        }

        topic = (
            f"homeassistant/{component}/"
            f"mo/{object_id}/config"
        )

        client.publish(
            topic,
            json.dumps(payload),
            retain=True
        )

    # --------------------------------------------------------
    # Control buttons
    # --------------------------------------------------------

    buttons = {
        "park": {
            "name": "Park",
            "payload": "park",
            "icon": "mdi:home-map-marker",
        },

        "pause": {
            "name": "Pause",
            "payload": "pause",
            "icon": "mdi:pause",
        },

        "resume": {
            "name": "Resume",
            "payload": "resume",
            "icon": "mdi:play",
        },

        "override": {
            "name": "Mow 3 Hours",
            "payload": "override",
            "icon": "mdi:robot-mower",
        },
    }

    for object_id, config in buttons.items():
        payload = {
            "name": config["name"],
            "unique_id": f"mo_{object_id}",
            "command_topic": COMMAND_TOPIC,
            "payload_press": config["payload"],
            "availability_topic": AVAILABILITY_TOPIC,
            "icon": config["icon"],
            "device": device,
        }

        topic = (
            f"homeassistant/button/"
            f"mo/{object_id}/config"
        )

        client.publish(
            topic,
            json.dumps(payload),
            retain=True
        )


# ============================================================
# Send commands to Mo
# ============================================================

async def send_mower_command(command, ble_lock):
    valid_commands = {
        "park",
        "pause",
        "resume",
        "override",
    }

    if command not in valid_commands:
        print(f"Unknown command: {command}")
        return

    async with ble_lock:
        print(f"Sending '{command}' to Mo...")

        device = await BleakScanner.find_device_by_address(
            ADDRESS,
            timeout=30
        )

        if device is None:
            print("Mo not found for command.")
            return

        mower = Mower(
            CHANNEL_ID,
            ADDRESS,
            pin=PIN
        )

        try:
            result = await mower.connect(device)

            if result != 0:
                print(
                    f"Command connection failed: {result}"
                )
                return

            if command == "park":
                result = await mower.mower_park()

            elif command == "pause":
                result = await mower.mower_pause()

            elif command == "resume":
                result = await mower.mower_resume()

            elif command == "override":
                result = await mower.mower_override()

            print(
                f"Command '{command}' result: {result}"
            )

        except Exception as exc:
            print(
                f"Command '{command}' failed: {exc}"
            )

        finally:
            try:
                await mower.disconnect()
            except Exception:
                pass


# ============================================================
# Read Mo
# ============================================================

async def read_mo(ble_lock):
    async with ble_lock:
        print("Looking for Mo...")

        device = await BleakScanner.find_device_by_address(
            ADDRESS,
            timeout=30
        )

        if device is None:
            raise RuntimeError("Mo not found")

        mower = Mower(
            CHANNEL_ID,
            ADDRESS,
            pin=PIN
        )

        try:
            result = await mower.connect(device)

            if result != 0:
                raise RuntimeError(
                    f"Mower connection returned {result}"
                )

            # ------------------------------------------------
            # Current status
            # ------------------------------------------------

            battery = await mower.battery_level()
            charging = await mower.is_charging()
            state = await mower.mower_state()
            activity = await mower.mower_activity()
            next_start = await mower.mower_next_start_time()

            # ------------------------------------------------
            # Lifetime statistics stored by Mo
            # ------------------------------------------------

            stats = await mower.command(
                "GetAllStatistics"
            )

            return {
                "battery": battery,
                "charging": bool(charging),
                "state": enum_name(state),
                "activity": enum_name(activity),

                "next_start": (
                    next_start.isoformat()
                    if next_start else None
                ),

                "total_running_seconds":
                    stats.get("totalRunningTime"),

                "total_cutting_seconds":
                    stats.get("totalCuttingTime"),

                "total_charging_seconds":
                    stats.get("totalChargingTime"),

                "total_searching_seconds":
                    stats.get("totalSearchingTime"),

                "number_of_collisions":
                    stats.get("numberOfCollisions"),

                "number_of_charging_cycles":
                    stats.get("numberOfChargingCycles"),

                "blade_usage_seconds":
                    stats.get("cuttingBladeUsageTime"),
            }

        finally:
            try:
                await mower.disconnect()
            except Exception:
                pass


# ============================================================
# Main loop
# ============================================================

async def main():
    loop = asyncio.get_running_loop()

    # Prevent the status poll and a command from attempting
    # to use Mo's BLE connection at the same time.
    ble_lock = asyncio.Lock()

    client = create_mqtt_client(
        loop,
        ble_lock
    )

    # Give MQTT a moment to connect before publishing
    # Home Assistant discovery messages.
    await asyncio.sleep(1)

    publish_discovery(client)

    client.publish(
        AVAILABILITY_TOPIC,
        "online",
        retain=True
    )

    print("Mo MQTT bridge started.")
    print(f"Publishing to {STATE_TOPIC}")
    print(f"Polling every {POLL_INTERVAL} seconds")
    print()

    try:
        while True:
            try:
                data = await read_mo(
                    ble_lock
                )

                print(
                    f"Battery: {data['battery']}% | "
                    f"Charging: {data['charging']} | "
                    f"State: {data['state']} | "
                    f"Activity: {data['activity']} | "
                    f"Lifetime mow: "
                    f"{data['total_cutting_seconds'] / 3600:.1f}h"
                )

                client.publish(
                    STATE_TOPIC,
                    json.dumps(data),
                    retain=True
                )

                client.publish(
                    AVAILABILITY_TOPIC,
                    "online",
                    retain=True
                )

            except Exception as exc:
                print(
                    f"Mo read failed: {exc}"
                )

                client.publish(
                    AVAILABILITY_TOPIC,
                    "offline",
                    retain=True
                )

            await asyncio.sleep(
                POLL_INTERVAL
            )

    finally:
        client.publish(
            AVAILABILITY_TOPIC,
            "offline",
            retain=True
        )

        time.sleep(0.5)

        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
