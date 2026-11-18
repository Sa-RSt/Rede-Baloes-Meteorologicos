from __future__ import annotations

import argparse
import random
import sqlite3
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

fake = Faker("pt_BR")

DEFAULT_SENSOR_TYPES = ("Temperatura", "Umidade", "Pressão", "Gás")
DEFAULT_BALLOONS = 4
DEFAULT_READINGS_PER_SENSOR = 100
DEFAULT_DAYS = 7
VALUE_MIN = 0
VALUE_MAX = 4095  # 12-bit sensor reading

# (balao_id, nome, criado_em)
BalloonRow = tuple[int, str, datetime | None]
# (balao_id, sensor, leitura, data_hora)
ReadingRow = tuple[int, str, int | float, datetime]

SCHEMA = """
CREATE TABLE IF NOT EXISTS Baloes (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(50) NOT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Leituras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    balao_id INTEGER NOT NULL,
    sensor VARCHAR(50) NOT NULL,
    leitura NUMERIC NOT NULL,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (balao_id) REFERENCES Baloes(id)
);

CREATE INDEX IF NOT EXISTS idx_leituras_balao ON Leituras(balao_id);
CREATE INDEX IF NOT EXISTS idx_leituras_data ON Leituras(data_hora);
"""


def default_database_path() -> Path:
    """Return the sqlite.db path used by the web application."""
    return Path(__file__).resolve().parents[2] / "sqlite.db"


def generate_balloons(
    balloon_ids: Sequence[int],
    *,
    created_at: datetime | None = None,
) -> list[BalloonRow]:
    """Build the auxiliary balloon records for the supplied IDs."""
    if len(set(balloon_ids)) != len(balloon_ids):
        raise ValueError("balloon_ids must not contain duplicates")

    return [(balloon_id, fake.bairro(), created_at) for balloon_id in balloon_ids]


def generate_readings(
    *,
    balloon_ids: Sequence[int],
    sensor_types: Sequence[str] = DEFAULT_SENSOR_TYPES,
    readings_per_sensor: int = DEFAULT_READINGS_PER_SENSOR,
    start: datetime,
    end: datetime,
    value_min: int = VALUE_MIN,
    value_max: int = VALUE_MAX,
    rng: random.Random | None = None,
) -> list[ReadingRow]:
    """Generate random readings for every balloon/sensor pair.

    Every pair receives the same timestamps, which mimics a message containing
    all sensors of a balloon at once. Timestamps are unique within each pair.
    """
    if readings_per_sensor < 0:
        raise ValueError("readings_per_sensor must be zero or positive")
    if end < start:
        raise ValueError("end must be greater than or equal to start")
    if value_min < 0:
        raise ValueError("value_min must be zero or positive")
    if value_max < value_min:
        raise ValueError("value_max must be greater than or equal to value_min")
    if len(set(balloon_ids)) != len(balloon_ids):
        raise ValueError("balloon_ids must not contain duplicates")
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
    readings: list[ReadingRow] = []

    for balloon_id in balloon_ids:
        for sensor_type in sensor_types:
            for offset in offsets:
                readings.append(
                    (
                        balloon_id,
                        sensor_type,
                        rng.randint(value_min, value_max),
                        start + timedelta(seconds=offset),
                    )
                )

    rng.shuffle(readings)
    return readings


def create_database(
    database: str | Path,
    balloons: Sequence[BalloonRow],
    readings: Sequence[ReadingRow],
    *,
    overwrite: bool = False,
) -> Path:
    """Create a SQLite database containing the supplied balloons and readings."""
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

    balloon_rows = [
        (
            balloon_id,
            nome,
            criado_em.strftime("%Y-%m-%d %H:%M:%S") if criado_em else None,
        )
        for balloon_id, nome, criado_em in balloons
    ]
    reading_rows = [
        (
            balloon_id,
            sensor,
            leitura,
            data_hora.strftime("%Y-%m-%d %H:%M:%S"),
        )
        for balloon_id, sensor, leitura, data_hora in readings
    ]

    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        with connection:
            connection.executemany(
                """
                INSERT INTO Baloes (id, nome, criado_em)
                VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                """,
                balloon_rows,
            )
            connection.executemany(
                """
                INSERT INTO Leituras (balao_id, sensor, leitura, data_hora)
                VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                """,
                reading_rows,
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
        "--baloes",
        "--stations",
        dest="balloons",
        type=int,
        default=DEFAULT_BALLOONS,
        help=(
            "number of balloons, IDs 1..N "
            f"(default: {DEFAULT_BALLOONS}; --stations is accepted as an alias)"
        ),
    )
    parser.add_argument(
        "--readings",
        type=int,
        default=DEFAULT_READINGS_PER_SENSOR,
        help=(
            f"readings per balloon/sensor pair (default: {DEFAULT_READINGS_PER_SENSOR})"
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

    if args.balloons < 1:
        parser.error("--baloes must be at least 1")
    if args.days < 1:
        parser.error("--days must be at least 1")

    database = (args.database or default_database_path()).expanduser().resolve()
    rng = random.Random(args.seed)
    end = datetime.now().replace(microsecond=0)
    start = end - timedelta(days=args.days)
    balloon_ids = list(range(1, args.balloons + 1))

    try:
        balloons = generate_balloons(balloon_ids, created_at=start)
        readings = generate_readings(
            balloon_ids=balloon_ids,
            sensor_types=DEFAULT_SENSOR_TYPES,
            readings_per_sensor=args.readings,
            start=start,
            end=end,
            rng=rng,
        )
        create_database(database, balloons, readings, overwrite=args.force)
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Created {database}")
    print(
        f"  balloons:          {len(balloon_ids)} ({balloon_ids[0]}..{balloon_ids[-1]})"
    )
    print(f"  sensor types:      {', '.join(DEFAULT_SENSOR_TYPES)}")
    print(f"  readings per pair: {args.readings}")
    print(f"  total readings:    {len(readings)}")
    print(f"  time range:        {start:%Y-%m-%d %H:%M:%S} .. {end:%Y-%m-%d %H:%M:%S}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
