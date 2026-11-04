from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_SENSOR_TYPES = ("Temperatura", "Umidade", "Pressão", "Gás")
DEFAULT_STATIONS = 4
DEFAULT_READINGS_PER_SENSOR = 100
DEFAULT_DAYS = 7
VALUE_MIN = 0
VALUE_MAX = 4095  # 12-bit sensor reading

SCHEMA = """
CREATE TABLE readings (
    sensor_type TEXT NOT NULL,
    value INTEGER NOT NULL CHECK (value >= 0),
    station_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (sensor_type, station_id, timestamp)
);

CREATE INDEX ix_readings_timestamp ON readings (timestamp);
"""


def default_database_path() -> Path:
    """Return the sqlite.db path used by the web application."""
    return Path(__file__).resolve().parents[2] / "sqlite.db"


def generate_readings(
    *,
    station_ids: Sequence[int],
    sensor_types: Sequence[str] = DEFAULT_SENSOR_TYPES,
    readings_per_sensor: int = DEFAULT_READINGS_PER_SENSOR,
    start: datetime,
    end: datetime,
    value_min: int = VALUE_MIN,
    value_max: int = VALUE_MAX,
    rng: random.Random | None = None,
) -> list[tuple[str, int, int, datetime]]:
    """Generate random readings.

    Every station/sensor pair receives the same timestamps, which mimics a
    message containing all sensors of a balloon at once. Timestamps are unique
    within each pair, so the (sensor_type, station_id, timestamp) primary key is
    never violated.
    """
    if readings_per_sensor < 0:
        raise ValueError("readings_per_sensor must be zero or positive")
    if end < start:
        raise ValueError("end must be greater than or equal to start")
    if value_min < 0:
        raise ValueError("value_min must be zero or positive")
    if value_max < value_min:
        raise ValueError("value_max must be greater than or equal to value_min")
    if len(set(station_ids)) != len(station_ids):
        raise ValueError("station_ids must not contain duplicates")
    if len(set(sensor_types)) != len(sensor_types):
        raise ValueError("sensor_types must not contain duplicates")

    rng = rng or random.Random()
    window_seconds = int((end - start).total_seconds())

    if readings_per_sensor > window_seconds + 1:
        raise ValueError(
            "readings_per_sensor is larger than the number of available seconds "
            "in the chosen time range"
        )

    offsets = sorted(rng.sample(range(window_seconds + 1), readings_per_sensor))
    readings: list[tuple[str, int, int, datetime]] = []

    for station_id in station_ids:
        for sensor_type in sensor_types:
            for offset in offsets:
                readings.append(
                    (
                        sensor_type,
                        rng.randint(value_min, value_max),
                        station_id,
                        start + timedelta(seconds=offset),
                    )
                )

    rng.shuffle(readings)
    return readings


def create_database(
    database: str | Path,
    readings: Sequence[tuple[str, int, int, datetime]],
    *,
    overwrite: bool = False,
) -> Path:
    """Create a SQLite database containing the supplied readings."""
    database = Path(database).expanduser().resolve()

    if database.exists():
        if not overwrite:
            raise FileExistsError(
                f"{database} already exists; use --force to overwrite it"
            )
        if database.is_dir():
            raise IsADirectoryError(f"{database} is a directory")
        database.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = database.with_name(database.name + suffix)
            sidecar.unlink(missing_ok=True)

    database.parent.mkdir(parents=True, exist_ok=True)

    rows = [
        (
            sensor_type,
            value,
            station_id,
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        )
        for sensor_type, value, station_id, timestamp in readings
    ]

    connection = sqlite3.connect(database)
    try:
        connection.executescript(SCHEMA)
        with connection:
            connection.executemany(
                """
                INSERT INTO readings (sensor_type, value, station_id, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )
    finally:
        connection.close()

    return database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a SQLite database with random meteorological balloon "
            "readings for the interface-web application."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="output SQLite file (default: sqlite.db next to pyproject.toml)",
    )
    parser.add_argument(
        "--stations",
        type=int,
        default=DEFAULT_STATIONS,
        help=f"number of stations, IDs 0..N-1 (default: {DEFAULT_STATIONS})",
    )
    parser.add_argument(
        "--readings",
        type=int,
        default=DEFAULT_READINGS_PER_SENSOR,
        help=(
            "readings per station/sensor pair "
            f"(default: {DEFAULT_READINGS_PER_SENSOR})"
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"time span covered by the readings, in days (default: {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="random seed for reproducible data",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite the database file if it already exists",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.stations < 1:
        parser.error("--stations must be at least 1")
    if args.days < 1:
        parser.error("--days must be at least 1")

    database = (args.database or default_database_path()).expanduser().resolve()
    rng = random.Random(args.seed)
    end = datetime.now().replace(microsecond=0)
    start = end - timedelta(days=args.days)
    station_ids = list(range(args.stations))

    try:
        readings = generate_readings(
            station_ids=station_ids,
            sensor_types=DEFAULT_SENSOR_TYPES,
            readings_per_sensor=args.readings,
            start=start,
            end=end,
            rng=rng,
        )
        create_database(database, readings, overwrite=args.force)
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Created {database}")
    print(f"  stations:          {len(station_ids)} ({station_ids[0]}..{station_ids[-1]})")
    print(f"  sensor types:      {', '.join(DEFAULT_SENSOR_TYPES)}")
    print(f"  readings per pair: {args.readings}")
    print(f"  total readings:    {len(readings)}")
    print(f"  time range:        {start:%Y-%m-%d %H:%M:%S} .. {end:%Y-%m-%d %H:%M:%S}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
