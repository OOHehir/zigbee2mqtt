#!/usr/bin/env python3
"""Example: load collected sensor data into pandas for ML prep.

Run after the collector has stored some data:
    python query_example.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sensor_data.db"


def load_readings(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load all readings joined with device metadata."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query("""
        SELECT
            r.ts            AS timestamp,
            d.friendly      AS device,
            d.model         AS model,
            r.attribute,
            r.value
        FROM readings r
        JOIN devices d ON d.id = r.device_id
        ORDER BY r.ts
    """, conn, parse_dates=["timestamp"])
    conn.close()
    return df


def pivot_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot to wide format: one column per (device, attribute).

    Useful for ML features — each row is a timestamp, columns are
    sensor readings across all devices and attributes.
    """
    df["feature"] = df["device"] + ":" + df["attribute"]
    wide = df.pivot_table(
        index="timestamp",
        columns="feature",
        values="value",
        aggfunc="mean",
    )
    # Forward-fill missing values (sensors report at different rates)
    wide = wide.ffill()
    return wide


if __name__ == "__main__":
    df = load_readings()
    print(f"Total readings: {len(df)}")
    print(f"Devices:        {df['device'].nunique()}")
    print(f"Attributes:     {df['attribute'].unique().tolist()}")
    print()

    if not df.empty:
        wide = pivot_wide(df)
        print(f"Wide format: {wide.shape[0]} rows x {wide.shape[1]} features")
        print(wide.head())
    else:
        print("No data yet — run the collector first.")
