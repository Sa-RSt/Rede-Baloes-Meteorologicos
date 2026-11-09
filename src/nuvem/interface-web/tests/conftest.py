from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask

from interface_web import create_app, db
from interface_web.models import Balloon, Reading


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
    """Seed a known set of readings covering two balloons and four sensors."""
    balloons = [
        Balloon(id=1, nome="Balão 1"),
        Balloon(id=2, nome="Balão 2"),
    ]
    rows = [
        Reading(
            balao_id=1,
            sensor="Temperatura",
            leitura=20,
            data_hora=datetime(2026, 11, 4, 10, 0, 0),
        ),
        Reading(
            balao_id=1,
            sensor="Temperatura",
            leitura=22,
            data_hora=datetime(2026, 11, 4, 12, 0, 0),
        ),
        Reading(
            balao_id=1,
            sensor="Umidade",
            leitura=80,
            data_hora=datetime(2026, 11, 4, 12, 0, 0),
        ),
        Reading(
            balao_id=1,
            sensor="Pressão",
            leitura=1013,
            data_hora=datetime(2026, 11, 4, 11, 0, 0),
        ),
        Reading(
            balao_id=1,
            sensor="Gás",
            leitura=400,
            data_hora=datetime(2026, 11, 4, 9, 0, 0),
        ),
        Reading(
            balao_id=2,
            sensor="Temperatura",
            leitura=15,
            data_hora=datetime(2026, 11, 4, 11, 30, 0),
        ),
        Reading(
            balao_id=2,
            sensor="Umidade",
            leitura=70,
            data_hora=datetime(2026, 11, 4, 11, 45, 0),
        ),
    ]

    with app.app_context():
        db.session.add_all(balloons)
        db.session.add_all(rows)
        db.session.commit()

    return rows


@pytest.fixture
def seeded_client(client, readings: list[Reading]):
    """A test client for a database already containing the sample readings."""
    return client
