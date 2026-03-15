# Zigbee Sensor Data Collector

Coordinator-side code for collecting Zigbee sensor data on a Raspberry Pi 4
using a SONOFF Zigbee 3.0 USB Dongle Plus V2.  Stores all sensor readings in
SQLite for later analysis with pandas / scikit-learn.

## Architecture

```
ESP32-C6 (presence)────┐
ESP32-C6 (sound)      ─┤                  ┌─────────────┐     ┌───────────┐
Arista Multifunction  ─┤                  │             │     │           │
Arista Temp & Humidity─┼── Zigbee 802.15.4 ──▶│ zigbee2mqtt │──MQTT──▶│ collector │──▶ SQLite
Arista Vibration      ─┤                  │  (coordinator)│     │  (Python) │     sensor_data.db
(other Zigbee 3.0)    ─┘                  └─────────────┘     └───────────┘
```

## Components

| Component | Description |
|-----------|-------------|
| `docker-compose.yml` | Mosquitto MQTT broker + zigbee2mqtt |
| `config/zigbee2mqtt/` | Coordinator config (SONOFF dongle on `/dev/ttyACM0`) |
| `converters/sound_monitor.js` | Custom zigbee2mqtt converter for the ESP32-C6 sound sensor |
| `converters/presence-node.js` | Custom converter for the ElectronicsConsult presence sensor (LD2410C mmWave) |
| `converters/arista-multifunction.js` | Custom converter for Arista sensors (ARST-MS, ARST-TH, ARST-VB) |
| `collector/collector.py` | MQTT subscriber — stores all numeric attributes to SQLite |
| `collector/db.py` | SQLite schema (EAV) and helpers |
| `collector/query_example.py` | Example: load data into pandas, pivot to wide format for ML |

## Quick Start

### 1. Start the coordinator stack

```bash
docker compose up -d
```

This starts:
- **Mosquitto** on port 1883 (MQTT broker)
- **zigbee2mqtt** on port 8080 (web UI for pairing devices)

### 2. Pair devices

Open http://localhost:8080 — permit_join is enabled by default.
Put each sensor into pairing mode per its manual.  zigbee2mqtt will
auto-discover standard ZCL clusters (temperature, humidity, occupancy, illuminance, etc.).

Custom external converters handle non-standard devices:

- **ESP32-C6 sound monitor** (`converters/sound_monitor.js`) — maps Analog Input `present_value` to `sound_level`
- **ElectronicsConsult presence node** (`converters/presence-node.js`) — maps mmWave presence + ToF range
- **Arista multifunction sensors** (`converters/arista-multifunction.js`) — handles all three Arista models:
  - **ARST-MS** (Multifunction): PIR occupancy, reed switch contact, temperature, illuminance
  - **ARST-TH** (Temp & Humidity): temperature, humidity (SHTC3)
  - **ARST-VB** (Vibration): vibration detection (LSM6DSL), temperature

### 3. Start the data collector

```bash
cd collector
pip install -r requirements.txt
python collector.py
```

Options:
```
--host HOST   MQTT broker hostname (default: localhost)
--port PORT   MQTT broker port (default: 1883)
--db PATH     SQLite database path (default: ../data/sensor_data.db)
```

The collector auto-discovers all devices and stores every numeric attribute.
No code changes needed when new sensors are added to the network.

### 4. Query data for ML

```bash
python collector/query_example.py
```

Or in a notebook:

```python
from collector.db import get_connection
import pandas as pd

conn = get_connection()
df = pd.read_sql_query("""
    SELECT r.ts, d.friendly, r.attribute, r.value
    FROM readings r JOIN devices d ON d.id = r.device_id
    ORDER BY r.ts
""", conn, parse_dates=["ts"])
```

## Database Schema (EAV)

**`devices`** — one row per sensor

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| ieee | TEXT UNIQUE | IEEE 802.15.4 address |
| friendly | TEXT | zigbee2mqtt friendly name |
| model | TEXT | Device model (e.g. "SNZB-02") |
| vendor | TEXT | Manufacturer |
| first_seen | TEXT | ISO 8601 timestamp |
| last_seen | TEXT | ISO 8601 timestamp |

**`readings`** — one row per (timestamp, device, attribute)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| ts | TEXT | ISO 8601 timestamp |
| device_id | INTEGER FK | References devices.id |
| attribute | TEXT | e.g. "temperature", "sound_level", "occupancy" |
| value | REAL | Numeric value (binary attributes stored as 0.0/1.0) |

### Storage estimate (3-day collection)

| Sensors | Attrs/sensor | Rate | Rows/day | 3-day total | ~DB size |
|---------|-------------|------|----------|-------------|----------|
| 1 | 1 | 1 Hz | 86,400 | 259,200 | ~15 MB |
| 5 | 3 avg | 1 Hz | 1,296,000 | 3,888,000 | ~220 MB |
| 10 | 5 avg | 1 Hz | 4,320,000 | 12,960,000 | ~740 MB |

SQLite with WAL journaling handles this fine.  The collector batches
writes every 5 seconds to reduce I/O on the RPi's SD card.

## Supported Sensor Attributes

The collector stores **any** numeric attribute published by zigbee2mqtt.
Common ones:

| Attribute | Typical sensors | Unit |
|-----------|----------------|------|
| `presence` | ElectronicsConsult presence node (binary → 0/1) | — |
| `range_cm` | ElectronicsConsult presence node (VL53L0X ToF) | cm |
| `sound_level` | ESP32-C6 sound monitor | 0.0–1.0 |
| `temperature` | Arista ARST-MS/TH/VB, other ZCL devices | °C |
| `humidity` | Arista ARST-TH, other ZCL devices | % |
| `occupancy` | Arista ARST-MS (PIR), other PIR sensors (binary → 0/1) | — |
| `contact` | Arista ARST-MS (reed switch, binary → 0/1) | — |
| `illuminance` / `illuminance_lux` | Arista ARST-MS (APDS-9922), other light sensors | lux |
| `vibration` | Arista ARST-VB (LSM6DSL, binary → 0/1) | — |
| `battery` | All battery devices (Arista, etc.) | % |
| `battery_voltage` | All battery devices | V |
| `linkquality` | All devices | LQI |

## Configuration

### zigbee2mqtt

Edit `config/zigbee2mqtt/configuration.yaml`:
- `serial.port` — set to your dongle path (default `/dev/ttyACM0`)
- `advanced.channel` — Zigbee channel (default 15)
- `permit_join` — set to `false` after all devices are paired

### Disabling permit_join for production

Once all sensors are paired, disable permit_join:

```yaml
permit_join: false
```

Then restart: `docker compose restart zigbee2mqtt`

## RPi Docker Setup (from scratch)

### 1. Install Docker on Raspberry Pi OS

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

Log out and back in (or `newgrp docker`) for the group change to take effect.

Verify:
```bash
docker --version
docker compose version
```

### 2. Clone and configure

```bash
git clone <this-repo-url> ~/zigbee2mqtt
cd ~/zigbee2mqtt
```

Plug in the SONOFF Zigbee 3.0 USB Dongle Plus V2. Confirm it appears:
```bash
ls /dev/ttyACM0
```

If the dongle shows up on a different path (e.g. `/dev/ttyUSB0`), update
`docker-compose.yml` and `config/zigbee2mqtt/configuration.yaml` to match.

### 3. Start the stack

```bash
docker compose up -d
```

This pulls and starts two containers:
- **mosquitto** — MQTT broker on port 1883
- **zigbee2mqtt** — Zigbee coordinator + web UI on port 8080

Check they're running:
```bash
docker compose ps
docker compose logs -f zigbee2mqtt   # Ctrl-C to stop tailing
```

### 4. Pair devices

Open `http://<rpi-ip>:8080` in a browser. Permit join is enabled by default.
Power on each sensor — it will appear in the Z2M UI once paired.

### 5. Start the data collector

```bash
cd collector
pip install -r requirements.txt
python collector.py
```

### 6. Manage the stack

```bash
docker compose stop          # stop containers (keeps data)
docker compose start         # restart stopped containers
docker compose down          # stop and remove containers (volumes preserved)
docker compose pull          # pull latest images
docker compose up -d         # recreate with latest images
docker compose logs -f       # tail all logs
```

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `permission denied` on docker socket | `sudo usermod -aG docker $USER` then log out/in |
| `/dev/ttyACM0` not found | Check dongle is plugged in; try `ls /dev/ttyACM*` or `ls /dev/ttyUSB*` |
| Z2M can't open serial port | Stop any other process using the port (`sudo fuser /dev/ttyACM0`); check `devices:` in `docker-compose.yml` |
| Stale MQTT data after converter change | `docker compose down`, delete `config/zigbee2mqtt/database.db`, restart Mosquitto to clear retained messages, then `docker compose up -d` |
| Containers restart-looping | `docker compose logs zigbee2mqtt` to check error; common cause is wrong serial port or adapter type |

## Hardware

- **Coordinator:** SONOFF Zigbee 3.0 USB Dongle Plus V2 (EFR32MG21, `/dev/ttyACM0`)
- **Target platform:** Raspberry Pi 4
- **Sensors:** Arista multifunction (ARST-MS, ARST-TH, ARST-VB) + ESP32-C6 sound monitor + ElectronicsConsult presence node + any Zigbee 3.0 device
