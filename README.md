# zigbee2mqtt

Zigbee coordinator and sensor data pipeline running on a Raspberry Pi — collects readings from any Zigbee 3.0 device and stores them in SQLite via MQTT, with custom converters for ESP32-C6 sensors.

## Key Technologies

- **Coordinator:** SONOFF Zigbee 3.0 USB Dongle Plus V2 (EFR32MG21) on Raspberry Pi 4
- **Bridge:** zigbee2mqtt (Docker) + Mosquitto MQTT broker
- **Collector:** Python (paho-mqtt) → SQLite with Entity-Attribute-Value schema
- **Custom converters:** JavaScript — ESP32-C6 presence node (LD2410C mmWave + VL53L0X), sound level monitor, Arista multi-sensor
- **Deployment:** Docker Compose

## What's Included

| Component | Description |
|---|---|
| `docker-compose.yml` | zigbee2mqtt + Mosquitto stack |
| `collector/collector.py` | MQTT subscriber that auto-discovers devices and persists all numeric attributes to SQLite |
| `converters/` | Custom JS converters for non-standard Zigbee devices |
| `config/` | zigbee2mqtt configuration for SONOFF coordinator |

## Getting Started

**Prerequisites:** Docker, Docker Compose, SONOFF Zigbee 3.0 dongle on `/dev/ttyUSB0`

```bash
docker compose up -d
python3 collector/collector.py
```

Data is stored in `data/sensor_data.db`. See `collector/query_example.py` for sample queries.

---

Built by Owen O'Hehir — embedded Linux, IoT, Matter & Rust consulting at [electronicsconsult.com](https://electronicsconsult.com). Available for contract and consulting work.
