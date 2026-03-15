#!/usr/bin/env python3
"""MQTT collector — subscribes to zigbee2mqtt and stores all numeric
sensor attributes in SQLite for later ML analysis.

Handles any sensor type: sound level, PIR/motion, temperature,
humidity, vibration, lux, etc.  No code changes needed when new
sensors join the network.

Usage:
    python collector.py                        # defaults
    python collector.py --host 192.168.1.10    # remote broker
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from db import get_connection, upsert_device, insert_readings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("collector")

# Zigbee2mqtt publishes device messages to:  zigbee2mqtt/<friendly_name>
# Bridge info goes to:                       zigbee2mqtt/bridge/*
BASE_TOPIC = "zigbee2mqtt"

# Attributes that are always non-numeric or internal — skip them.
SKIP_ATTRIBUTES = {
    "last_seen", "elapsed", "update", "update_available",
    "device_temperature",  # usually internal chip temp, not ambient
}

# Attributes that are boolean/binary — convert to 0/1 for storage.
BINARY_ATTRIBUTES = {
    "occupancy", "contact", "vibration", "tamper",
    "battery_low", "water_leak", "smoke", "gas",
    "presence",
}


FLUSH_INTERVAL_S = 5  # Batch DB writes every N seconds (reduces I/O for long runs)


class Collector:
    def __init__(self, broker_host: str, broker_port: int, db_path: Path):
        self._db_path = db_path
        self.conn = get_connection(db_path)
        self._device_cache: dict[str, int] = {}  # friendly_name -> device_id
        self._device_meta: dict[str, dict] = {}  # friendly_name -> {ieee, model, vendor}
        self._buffer: list[tuple[str, int, str, float]] = []  # (ts, device_id, attr, value)
        self._buffer_lock = threading.Lock()
        self._readings_count = 0

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(broker_host, broker_port)

        # Periodic flush thread
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    # ── MQTT callbacks ────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        log.info("Connected to MQTT broker (rc=%s)", rc)
        # Subscribe to all device topics and bridge device list
        client.subscribe(f"{BASE_TOPIC}/#")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic

        # Bridge device list — cache IEEE / model metadata
        if topic == f"{BASE_TOPIC}/bridge/devices":
            self._handle_device_list(msg.payload)
            return

        # Skip bridge topics
        if "/bridge/" in topic:
            return

        # Device data message: zigbee2mqtt/<friendly_name>
        friendly = topic.removeprefix(f"{BASE_TOPIC}/")
        if "/" in friendly:
            return  # sub-topic like /set or /availability

        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        if not isinstance(payload, dict):
            return

        self._handle_reading(friendly, payload)

    # ── Internal handlers ─────────────────────────────────────────

    def _handle_device_list(self, raw: bytes) -> None:
        try:
            devices = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        for dev in devices:
            friendly = dev.get("friendly_name", "")
            ieee = dev.get("ieee_address", "")
            defn = dev.get("definition") or {}
            model = defn.get("model", "")
            vendor = defn.get("vendor", "")
            if ieee and friendly:
                self._device_meta[friendly] = {
                    "ieee": ieee, "model": model, "vendor": vendor,
                }
                log.info("Discovered device: %s (%s / %s)", friendly, model, ieee)

    def _handle_reading(self, friendly: str, payload: dict) -> None:
        # Resolve device_id (lazy upsert)
        device_id = self._resolve_device(friendly)
        if device_id is None:
            return

        # Extract numeric attributes
        numeric: dict[str, float] = {}
        for key, val in payload.items():
            if key in SKIP_ATTRIBUTES:
                continue
            if key in BINARY_ATTRIBUTES:
                numeric[key] = 1.0 if val else 0.0
            elif isinstance(val, (int, float)) and not isinstance(val, bool):
                numeric[key] = float(val)

        if not numeric:
            return

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        with self._buffer_lock:
            for attr, val in numeric.items():
                self._buffer.append((ts, device_id, attr, val))

    def _resolve_device(self, friendly: str) -> int | None:
        if friendly in self._device_cache:
            return self._device_cache[friendly]

        meta = self._device_meta.get(friendly, {})
        ieee = meta.get("ieee", friendly)  # fallback to friendly as identifier
        model = meta.get("model", "")
        vendor = meta.get("vendor", "")

        device_id = upsert_device(self.conn, ieee, friendly, model, vendor)
        self._device_cache[friendly] = device_id
        return device_id

    # ── Buffer flush ────────────────────────────────────────────

    def _flush_loop(self) -> None:
        # Separate connection for the flush thread (SQLite requires per-thread connections)
        self._flush_conn = get_connection(self._db_path)
        while True:
            time.sleep(FLUSH_INTERVAL_S)
            self._flush()

    def _flush(self) -> None:
        with self._buffer_lock:
            if not self._buffer:
                return
            batch = self._buffer.copy()
            self._buffer.clear()

        self._flush_conn.executemany(
            "INSERT INTO readings (ts, device_id, attribute, value) VALUES (?, ?, ?, ?)",
            batch,
        )
        self._flush_conn.commit()
        self._readings_count += len(batch)
        if self._readings_count % 1000 == 0 or len(batch) >= 10:
            log.info("Total readings stored: %d (+%d this flush)", self._readings_count, len(batch))

    # ── Lifecycle ─────────────────────────────────────────────────

    def run(self) -> None:
        log.info("Collector running — press Ctrl+C to stop")
        self.client.loop_forever()

    def stop(self) -> None:
        log.info("Flushing remaining buffer...")
        self._flush()
        log.info("Shutting down — %d total readings stored", self._readings_count)
        self.client.disconnect()
        self.conn.close()
        if hasattr(self, '_flush_conn'):
            self._flush_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Zigbee sensor data collector")
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--db", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "sensor_data.db",
                        help="SQLite database path")
    args = parser.parse_args()

    collector = Collector(args.host, args.port, args.db)

    def _shutdown(signum, frame):
        collector.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    collector.run()


if __name__ == "__main__":
    main()
