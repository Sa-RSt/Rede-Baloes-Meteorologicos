from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser

import pytest
from flask import Flask, url_for
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from interface_web import db
from interface_web.models import Reading


class ReadingsTableParser(HTMLParser):
    """Extract the rows of the readings table as plain strings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_table = False
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "readings-table":
            self._in_table = True
        elif self._in_table and tag == "tr":
            self._row = []
        elif self._row is not None and tag in {"td", "th"}:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "table" and self._in_table:
            self._in_table = False


def parse_readings_table(html: str) -> list[list[str]]:
    parser = ReadingsTableParser()
    parser.feed(html)
    return parser.rows


def href_for(app: Flask, station_id: int, sensor_type: str) -> str:
    with app.test_request_context():
        return url_for(
            "main.readings",
            station_id=station_id,
            sensor_type=sensor_type,
        )


def station_href(app: Flask, station_id: int) -> str:
    with app.test_request_context():
        return url_for("main.station", station_id=station_id)


def test_database_schema_is_created(app: Flask) -> None:
    with app.app_context():
        inspector = inspect(db.engine)
        assert "readings" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("readings")}
        assert columns == {"sensor_type", "value", "station_id", "timestamp"}


def test_negative_values_are_rejected(app: Flask) -> None:
    with app.app_context():
        db.session.add(
            Reading(
                station_id=9,
                sensor_type="Temperatura",
                value=-1,
                timestamp=datetime(2026, 11, 4, 12, 0, 0),
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_empty_database_shows_empty_state(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Nenhuma leitura encontrada" in body
    assert "Nenhuma estação encontrada" in body
    assert "readings-table" not in body


def test_index_lists_stations_as_responsive_cards(seeded_client, app: Flask) -> None:
    response = seeded_client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'class="row g-3"' in body
    assert "col-12 col-sm-6 col-lg-4 col-xxl-3 d-flex" in body
    assert "card station-card" in body

    for station_id in (1, 2):
        assert f'href="{station_href(app, station_id)}"' in body

    assert "Estação 1" in body
    assert "Estação 2" in body


def test_station_page_lists_sensors_as_responsive_cards(
    seeded_client, app: Flask
) -> None:
    response = seeded_client.get("/1")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Estação 1" in body
    assert 'class="row g-3"' in body
    assert "col-12 col-sm-6 col-lg-4 col-xxl-3 d-flex" in body
    assert "card station-card" in body

    for sensor_type in ["Temperatura", "Umidade", "Pressão", "Gás"]:
        assert f'href="{href_for(app, 1, sensor_type)}"' in body

    assert "2 leituras" in body
    assert "1 leitura" in body


def test_reading_page_breadcrumb_links_back_to_station(
    seeded_client, app: Flask
) -> None:
    body = seeded_client.get("/1/Temperatura").get_data(as_text=True)

    assert f'href="{station_href(app, 1)}"' in body


def test_readings_sorted_by_timestamp_most_recent_first(seeded_client) -> None:
    response = seeded_client.get("/1/Temperatura")
    assert response.status_code == 200

    rows = parse_readings_table(response.get_data(as_text=True))
    header, *data = rows

    assert header == ["#", "Timestamp", "Valor", "Sensor", "Estação"]
    assert [row[1] for row in data] == [
        "2026-11-04 12:00:00",
        "2026-11-04 10:00:00",
    ]
    assert [row[2] for row in data] == ["22", "20"]


def test_readings_table_shows_all_columns(seeded_client) -> None:
    rows = parse_readings_table(seeded_client.get("/1/Temperatura").get_data(as_text=True))
    _, *data = rows

    assert data[0] == [
        "1",
        "2026-11-04 12:00:00",
        "22",
        "Temperatura",
        "1",
    ]
    assert data[1] == [
        "2",
        "2026-11-04 10:00:00",
        "20",
        "Temperatura",
        "1",
    ]


def test_all_readings_are_rendered_without_pagination(client, app: Flask) -> None:
    with app.app_context():
        db.session.add_all(
            [
                Reading(
                    station_id=3,
                    sensor_type="Temperatura",
                    value=index,
                    timestamp=datetime(2026, 1, 1, 0, index, 0),
                )
                for index in range(25)
            ]
        )
        db.session.commit()

    rows = parse_readings_table(client.get("/3/Temperatura").get_data(as_text=True))

    assert len(rows) == 26  # 1 header + 25 readings


def test_menu_tree_lists_every_station_and_sensor(seeded_client, app: Flask) -> None:
    body = seeded_client.get("/1/Temperatura").get_data(as_text=True)

    assert "Estação 1" in body
    assert "Estação 2" in body
    assert f'href="{station_href(app, 1)}"' in body
    assert f'href="{station_href(app, 2)}"' in body
    for station_id, sensor_type in [
        (1, "Temperatura"),
        (1, "Umidade"),
        (1, "Pressão"),
        (1, "Gás"),
        (2, "Temperatura"),
        (2, "Umidade"),
    ]:
        assert f'href="{href_for(app, station_id, sensor_type)}"' in body

    assert "station-tree-node is-current" in body
    assert "station-tree-leaf active" in body


def test_navbar_links_to_other_sensors_of_current_station(
    seeded_client, app: Flask
) -> None:
    body = seeded_client.get("/1/Temperatura").get_data(as_text=True)
    navbar = body.split("navbar-station-links", 1)[1].split("</div>", 1)[0]

    for sensor_type in ["Temperatura", "Umidade", "Pressão", "Gás"]:
        assert f'href="{href_for(app, 1, sensor_type)}"' in navbar

    # Sensors belonging to another station must not appear in this station's
    # shortcut list inside the navbar.
    assert f'href="{href_for(app, 2, "Temperatura")}"' not in navbar


def test_each_station_sensor_pair_has_a_page(seeded_client, app: Flask) -> None:
    pairs = [
        (1, "Temperatura"),
        (1, "Umidade"),
        (1, "Pressão"),
        (1, "Gás"),
        (2, "Temperatura"),
        (2, "Umidade"),
    ]

    for station_id, sensor_type in pairs:
        response = seeded_client.get(href_for(app, station_id, sensor_type))
        assert response.status_code == 200, (station_id, sensor_type)


def test_unicode_sensor_type_in_url(seeded_client, app: Flask) -> None:
    response = seeded_client.get(href_for(app, 1, "Pressão"))

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "1013" in body
    assert "Pressão" in body


def test_unknown_station_returns_404(seeded_client) -> None:
    response = seeded_client.get("/99/Temperatura")

    assert response.status_code == 404
    assert "Página não encontrada" in response.get_data(as_text=True)


def test_unknown_station_page_returns_404(seeded_client) -> None:
    response = seeded_client.get("/99")

    assert response.status_code == 404
    assert "Página não encontrada" in response.get_data(as_text=True)


def test_unknown_sensor_returns_404(seeded_client) -> None:
    response = seeded_client.get("/1/SensorInexistente")

    assert response.status_code == 404


def test_page_includes_jquery_and_bootstrap(seeded_client) -> None:
    body = seeded_client.get("/1/Temperatura").get_data(as_text=True)

    assert "jquery-3.7.1.min.js" in body
    assert "bootstrap@5.3.3/dist/css/bootstrap.min.css" in body
    assert "bootstrap.bundle.min.js" in body
    assert "js/app.js" in body
