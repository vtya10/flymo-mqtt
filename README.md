# Flymo MQTT Bridge

A local Bluetooth Low Energy (BLE) to MQTT bridge for compatible Flymo EasiLife robotic lawn mowers.

The bridge runs on a Linux device such as a Raspberry Pi, communicates directly with the mower over Bluetooth, and publishes mower status and statistics to MQTT.

Home Assistant MQTT Discovery is supported, allowing sensors and mower controls to appear automatically in Home Assistant.

## Features

- Local BLE communication with the mower
- No cloud connection required by this bridge
- MQTT state publishing
- MQTT availability reporting
- Home Assistant MQTT Discovery
- Battery level
- Charging status
- Mower state
- Current mower activity
- Next scheduled start
- Lifetime running statistics
- Lifetime cutting statistics
- Lifetime charging statistics
- Lifetime searching statistics
- Blade usage
- Charging cycle count
- Collision count
- MQTT mower controls:
  - Park
  - Pause
  - Resume
  - Mow for 3 hours
- systemd service support
- Credentials and mower configuration kept outside the repository

## Tested Hardware

Development and testing has primarily been performed with:

- Flymo EasiLife Go 150
- Raspberry Pi
- Linux / BlueZ
- Python 3
- Mosquitto MQTT
- Home Assistant

Other mower models supported by the underlying `automower-ble` library may work, but have not necessarily been tested with this project.

## How It Works

The Raspberry Pi communicates locally with the mower using Bluetooth Low Energy.

The bridge periodically reads mower information and publishes a JSON state message to MQTT.

Home Assistant can discover the mower automatically through MQTT Discovery.

Commands travel in the opposite direction:

Home Assistant -> MQTT -> Flymo MQTT Bridge -> BLE -> Mower

## Requirements

You will need:

- A Linux system with Bluetooth support
- Python 3
- BlueZ
- An MQTT broker
- A compatible Flymo/Husqvarna mower
- The `automower-ble` Python package

Home Assistant is optional but is the primary intended MQTT consumer.

## Installation

Clone the repository:

```bash
git clone git@github.com:vtya10/flymo-mqtt.git
cd flymo-mqtt
```

Create a Python virtual environment:

```bash
python3 -m venv ~/automower-ble-venv
source ~/automower-ble-venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Finding Your Mower

The mower must first be visible to BlueZ.

Start the Bluetooth utility:

```bash
bluetoothctl
```

Enable scanning:

```text
scan on
```

Look for your mower and note its Bluetooth MAC address.

Pairing requirements can vary between mower models and firmware versions. The mower may need to be placed into its Bluetooth/pairing mode before BlueZ can pair successfully.

Once identified, the mower-specific values are stored in the private environment file described below.

## Configuration

Copy the example configuration:

```bash
mkdir -p ~/.config
cp mo-mqtt.env.example ~/.config/mo-mqtt.env
chmod 600 ~/.config/mo-mqtt.env
```

Edit it:

```bash
nano ~/.config/mo-mqtt.env
```

Example:

```text
MO_ADDRESS=AA:BB:CC:DD:EE:FF
MO_CHANNEL_ID=1234567890
MO_PIN=1234

MO_MQTT_HOST=192.168.1.10
MO_MQTT_PORT=1883
MO_MQTT_USERNAME=mqtt_user
MO_MQTT_PASSWORD=your_password
```

Do not commit your real environment file.

## MQTT Topics

The default base topic is:

```text
flymo/mo
```

State:

```text
flymo/mo/state
```

Availability:

```text
flymo/mo/availability
```

Commands:

```text
flymo/mo/command
```

Supported command payloads are:

```text
park
pause
resume
override
```

`override` starts the mower using the mower's override/mowing behaviour used by this bridge.

## Home Assistant

Home Assistant MQTT Discovery is published automatically when the bridge starts.

Depending on the mower and bridge version, entities include:

- Battery
- Charging
- State
- Activity
- Next Start
- Lifetime Cutting
- Lifetime Running
- Lifetime Charging
- Lifetime Searching
- Blade Usage
- Charging Cycles
- Collisions

Control buttons include:

- Park
- Pause
- Resume
- Mow 3 Hours

MQTT Discovery must be enabled in Home Assistant.

## Running Manually

Load the configuration:

```bash
set -a
source ~/.config/mo-mqtt.env
set +a
```

Then run:

```bash
python3 mo_mqtt.py
```

## systemd

An example service is provided in:

```text
systemd/mo-mqtt.service
```

Review the paths in the service file and adjust them for your installation.

Install it with:

```bash
sudo cp systemd/mo-mqtt.service /etc/systemd/system/mo-mqtt.service
sudo systemctl daemon-reload
sudo systemctl enable --now mo-mqtt.service
```

Check status:

```bash
systemctl status mo-mqtt.service
```

View logs:

```bash
journalctl -u mo-mqtt.service -f
```

A healthy connection should report successful MQTT connectivity followed by mower polling.

## Security

Mower credentials and MQTT credentials should never be committed to Git.

Keep them in a separate environment file such as:

```text
~/.config/mo-mqtt.env
```

and protect it with:

```bash
chmod 600 ~/.config/mo-mqtt.env
```

## Disclaimer

This is an unofficial community project.

It is not affiliated with, endorsed by, or supported by Flymo, Husqvarna Group, Home Assistant, or the manufacturers of any referenced products.

Use it at your own risk. Robotic lawn mowers are physical machinery: test remote-control functionality carefully and follow the manufacturer's safety guidance.

## Acknowledgements

This project uses the `automower-ble` Python library for communication with compatible mowers.

Thanks to the developers and contributors of that project for making local BLE mower communication possible.

## License

Licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).
