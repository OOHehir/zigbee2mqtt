"""SQLite database for Zigbee sensor readings.

Schema uses Entity-Attribute-Value (EAV) pattern so any sensor type
with any set of attributes can be stored without schema changes.

Tables
------
devices:    IEEE address, friendly name, model, first/last seen
readings:   timestamp, device FK, attribute name, numeric value
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sensor_data.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ieee        TEXT UNIQUE NOT NULL,
            friendly    TEXT NOT NULL DEFAULT '',
            model       TEXT NOT NULL DEFAULT '',
            vendor      TEXT NOT NULL DEFAULT '',
            first_seen  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            last_seen   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );

        CREATE TABLE IF NOT EXISTS readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            device_id   INTEGER NOT NULL REFERENCES devices(id),
            attribute   TEXT NOT NULL,
            value       REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts);
        CREATE INDEX IF NOT EXISTS idx_readings_device ON readings(device_id);
        CREATE INDEX IF NOT EXISTS idx_readings_attr ON readings(attribute);
        CREATE INDEX IF NOT EXISTS idx_readings_device_attr ON readings(device_id, attribute);
    """)


def upsert_device(conn: sqlite3.Connection, ieee: str, friendly: str = "",
                   model: str = "", vendor: str = "") -> int:
    """Insert or update a device. Returns the device id."""
    conn.execute("""
        INSERT INTO devices (ieee, friendly, model, vendor)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ieee) DO UPDATE SET
            friendly  = CASE WHEN excluded.friendly  != '' THEN excluded.friendly  ELSE devices.friendly  END,
            model     = CASE WHEN excluded.model     != '' THEN excluded.model     ELSE devices.model     END,
            vendor    = CASE WHEN excluded.vendor    != '' THEN excluded.vendor    ELSE devices.vendor    END,
            last_seen = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    """, (ieee, friendly, model, vendor))
    conn.commit()
    row = conn.execute("SELECT id FROM devices WHERE ieee = ?", (ieee,)).fetchone()
    return row[0]


def insert_readings(conn: sqlite3.Connection, device_id: int,
                    attributes: dict[str, float]) -> None:
    """Insert one row per numeric attribute."""
    conn.executemany(
        "INSERT INTO readings (device_id, attribute, value) VALUES (?, ?, ?)",
        [(device_id, attr, val) for attr, val in attributes.items()]
    )
    conn.commit()
