from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask

from interface_web import create_app, db
from interface_web.models import Reading


@pytest.fixture
def app(tmp_path: Path) -> Iterator[Flask]:
    """A fresh application backed by an isolated SQLite database."""
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.sqlite'}",
        }
    )

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app: Flask):
    return app.test_client()


@pytest.fixture
def readings(app: Flask) -> list[Reading]:
    """Seed a known set of readings covering two stations and four sensors."""
    rows = [
        Reading(
            station_id=1,
            sensor_type="Temperatura",
            value=20,
            timestamp=datetime(2026, 11, 4, 10, 0, 0),
        ),
        Reading(
            station_id=1,
            sensor_type="Temperatura",
            value=22,
            timestamp=datetime(2026, 11, 4, 12, 0, 0),
        ),
        Reading(
            station_id=1,
            sensor_type="Umidade",
            value=80,
            timestamp=datetime(2026, 11, 4, 12, 0, 0),
        ),
        Reading(
            station_id=1,
            sensor_type="Pressão",
            value=1013,
            timestamp=datetime(2026, 11, 4, 11, 0, 0),
        ),
        Reading(
            station_id=1,
            sensor_type="Gás",
            value=400,
            timestamp=datetime(2026, 11, 4, 9, 0, 0),
        ),
        Reading(
            station_id=2,
            sensor_type="Temperatura",
            value=15,
            timestamp=datetime(2026, 11, 4, 11, 30, 0),
        ),
        Reading(
            station_id=2,
            sensor_type="Umidade",
            value=70,
            timestamp=datetime(2026, 11, 4, 11, 45, 0),
        ),
    ]

    with app.app_context():
        db.session.add_all(rows)
        db.session.commit()

    return rows


@pytest.fixture
def seeded_client(client, readings: list[Reading]):
    """A test client for a database already containing the sample readings."""
    return client
