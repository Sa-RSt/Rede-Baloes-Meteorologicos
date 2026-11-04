from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta

import pytest

from interface_web import seed


def sample_readings(rng: random.Random | None = None):
    end = datetime(2026, 11, 4, 12, 0, 0)
    start = end - timedelta(days=2)
    return seed.generate_readings(
        station_ids=[0, 1],
        sensor_types=["Temperatura", "Umidade"],
        readings_per_sensor=5,
        start=start,
        end=end,
        rng=rng,
    )


def test_generate_readings_is_deterministic_with_a_seed() -> None:
    first = sample_readings(random.Random(42))
    second = sample_readings(random.Random(42))

    assert first == second
    assert len(first) == 2 * 2 * 5


def test_generate_readings_has_valid_values_and_unique_keys() -> None:
    end = datetime(2026, 11, 4, 12, 0, 0)
    start = end - timedelta(days=2)
    readings = sample_readings(random.Random(1))

    assert all(0 <= value <= 4095 for _, value, _, _ in readings)
    assert all(start <= timestamp <= end for _, _, _, timestamp in readings)

    keys = {(sensor, station, timestamp) for sensor, _, station, timestamp in readings}
    assert len(keys) == len(readings)


def test_generate_readings_rejects_duplicate_station_ids() -> None:
    with pytest.raises(ValueError, match="station_ids"):
        seed.generate_readings(
            station_ids=[1, 1],
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 2),
        )


def test_generate_readings_rejects_too_many_readings_for_time_range() -> None:
    with pytest.raises(ValueError, match="larger than"):
        seed.generate_readings(
            station_ids=[1],
            readings_per_sensor=100,
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 1, 0, 0, 30),
        )


def test_create_database_writes_all_readings(tmp_path) -> None:
    database = tmp_path / "random.sqlite"
    readings = sample_readings(random.Random(2))

    written = seed.create_database(database, readings)

    assert written == database.resolve()
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT sensor_type, value, station_id, timestamp FROM readings"
        ).fetchall()

    assert len(rows) == len(readings)
    assert {row[0] for row in rows} == {"Temperatura", "Umidade"}
    assert {row[2] for row in rows} == {0, 1}


def test_create_database_requires_force_to_overwrite(tmp_path) -> None:
    database = tmp_path / "random.sqlite"
    readings = sample_readings(random.Random(3))
    seed.create_database(database, readings)

    with pytest.raises(FileExistsError, match="--force"):
        seed.create_database(database, readings)

    seed.create_database(database, readings[:1], overwrite=True)
    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM readings").fetchone()[0]

    assert count == 1


def test_cli_creates_populated_database(tmp_path, capsys) -> None:
    database = tmp_path / "cli.sqlite"

    exit_code = seed.main(
        [
            "--database",
            str(database),
            "--stations",
            "2",
            "--readings",
            "3",
            "--days",
            "1",
            "--seed",
            "7",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert str(database.resolve()) in output
    assert "total readings:    24" in output

    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        stations = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT station_id FROM readings"
            ).fetchall()
        }

    assert count == 24
    assert stations == {0, 1}


def test_cli_refuses_to_overwrite_without_force(tmp_path, capsys) -> None:
    database = tmp_path / "cli.sqlite"
    args = [
        "--database",
        str(database),
        "--stations",
        "1",
        "--readings",
        "2",
        "--days",
        "1",
    ]

    assert seed.main(args) == 0
    assert seed.main(args) == 1
    assert "already exists; use --force" in capsys.readouterr().err
    assert seed.main([*args, "--force"]) == 0


def test_default_database_path_is_the_application_database() -> None:
    path = seed.default_database_path()

    assert path.name == "sqlite.db"
    assert path.parent.name == "interface-web"
