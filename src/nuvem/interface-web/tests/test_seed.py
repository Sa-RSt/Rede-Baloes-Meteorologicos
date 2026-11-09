from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta

import pytest

from interface_web import seed


def sample_balloons(created_at: datetime | None = None):
    return seed.generate_balloons([1, 2], created_at=created_at)


def sample_readings(rng: random.Random | None = None):
    end = datetime(2026, 11, 4, 12, 0, 0)
    start = end - timedelta(days=2)
    return seed.generate_readings(
        balloon_ids=[1, 2],
        sensor_types=["Temperatura", "Umidade"],
        readings_per_sensor=5,
        start=start,
        end=end,
        rng=rng,
    )


def test_generate_balloons_creates_names() -> None:
    balloons = sample_balloons(datetime(2026, 11, 4, 12, 0, 0))

    assert [(b[0], b[2]) for b in balloons] == [
        (1, datetime(2026, 11, 4, 12, 0, 0)),
        (2, datetime(2026, 11, 4, 12, 0, 0)),
    ]


def test_generate_balloons_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="balloon_ids"):
        seed.generate_balloons([1, 1])


def test_generate_readings_is_deterministic_with_a_seed() -> None:
    first = sample_readings(random.Random(42))
    second = sample_readings(random.Random(42))

    assert first == second
    assert len(first) == 2 * 2 * 5


def test_generate_readings_has_valid_values_and_unique_keys() -> None:
    end = datetime(2026, 11, 4, 12, 0, 0)
    start = end - timedelta(days=2)
    readings = sample_readings(random.Random(1))

    assert all(0 <= leitura <= 4095 for _, _, leitura, _ in readings)
    assert all(start <= data_hora <= end for _, _, _, data_hora in readings)

    keys = {
        (balao_id, sensor, data_hora) for balao_id, sensor, _, data_hora in readings
    }
    assert len(keys) == len(readings)


def test_generate_readings_rejects_duplicate_balloon_ids() -> None:
    with pytest.raises(ValueError, match="balloon_ids"):
        seed.generate_readings(
            balloon_ids=[1, 1],
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 2),
        )


def test_generate_readings_rejects_too_many_readings_for_time_range() -> None:
    with pytest.raises(ValueError, match="larger than"):
        seed.generate_readings(
            balloon_ids=[1],
            readings_per_sensor=100,
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 1, 0, 0, 30),
        )


def test_create_database_writes_balloons_and_readings(tmp_path) -> None:
    database = tmp_path / "random.sqlite"
    balloons = sample_balloons()
    readings = sample_readings(random.Random(2))

    written = seed.create_database(database, balloons, readings)

    assert written == database.resolve()
    with sqlite3.connect(database) as connection:
        balloon_rows = connection.execute(
            "SELECT id, nome FROM Baloes ORDER BY id"
        ).fetchall()
        reading_rows = connection.execute(
            "SELECT balao_id, sensor, leitura, data_hora FROM Leituras"
        ).fetchall()

    assert [i for i, _ in balloon_rows] == [1, 2]
    assert len(reading_rows) == len(readings)
    assert {row[1] for row in reading_rows} == {"Temperatura", "Umidade"}
    assert {row[0] for row in reading_rows} == {1, 2}


def test_create_database_creates_the_expected_indexes(tmp_path) -> None:
    database = tmp_path / "indexes.sqlite"
    seed.create_database(database, sample_balloons(), sample_readings(random.Random(4)))

    with sqlite3.connect(database) as connection:
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }

    assert {"idx_leituras_balao", "idx_leituras_data"} <= indexes


def test_create_database_requires_force_to_overwrite(tmp_path) -> None:
    database = tmp_path / "random.sqlite"
    balloons = sample_balloons()
    readings = sample_readings(random.Random(3))
    seed.create_database(database, balloons, readings)

    with pytest.raises(FileExistsError, match="--force"):
        seed.create_database(database, balloons, readings)

    seed.create_database(database, balloons, readings[:1], overwrite=True)
    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM Leituras").fetchone()[0]

    assert count == 1


def test_cli_creates_populated_database(tmp_path, capsys) -> None:
    database = tmp_path / "cli.sqlite"

    exit_code = seed.main(
        [
            "--database",
            str(database),
            "--baloes",
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
        count = connection.execute("SELECT COUNT(*) FROM Leituras").fetchone()[0]
        balloon_ids = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT balao_id FROM Leituras"
            ).fetchall()
        }
        balloons = connection.execute(
            "SELECT id, nome FROM Baloes ORDER BY id"
        ).fetchall()

    assert count == 24
    assert balloon_ids == {1, 2}
    assert [i for i, _ in balloons] == [1, 2]


def test_cli_accepts_legacy_stations_option(tmp_path, capsys) -> None:
    database = tmp_path / "cli.sqlite"

    assert (
        seed.main(
            [
                "--database",
                str(database),
                "--stations",
                "2",
                "--readings",
                "1",
                "--days",
                "1",
            ]
        )
        == 0
    )

    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM Baloes").fetchone()[0]

    assert count == 2
    assert "balloons:          2 (1..2)" in capsys.readouterr().out


def test_cli_refuses_to_overwrite_without_force(tmp_path, capsys) -> None:
    database = tmp_path / "cli.sqlite"
    args = [
        "--database",
        str(database),
        "--baloes",
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
