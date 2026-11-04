from __future__ import annotations

from flask import Blueprint, abort, render_template
from sqlalchemy import func, select

from . import db
from .models import Reading

bp = Blueprint("main", __name__)


def station_tree() -> dict[int, list[str]]:
    """Return {station_id: [sensor_type, ...]} for the whole database."""
    rows = db.session.execute(
        select(Reading.station_id, Reading.sensor_type)
        .distinct()
        .order_by(Reading.station_id, Reading.sensor_type)
    ).all()

    tree: dict[int, list[str]] = {}
    for station_id, sensor_type in rows:
        tree.setdefault(station_id, []).append(sensor_type)
    return tree


@bp.get("/")
def index():
    """Show every station as a card linking to its sensor page."""
    return render_template("index.html", station_tree=station_tree())


@bp.get("/<int:station_id>")
def station(station_id: int):
    """Show every sensor of a station as a card linking to its table."""
    tree = station_tree()
    station_sensors = tree.get(station_id)

    if not station_sensors:
        abort(404)

    stats_rows = db.session.execute(
        select(
            Reading.sensor_type,
            func.count().label("reading_count"),
            func.max(Reading.timestamp).label("latest_timestamp"),
        )
        .where(Reading.station_id == station_id)
        .group_by(Reading.sensor_type)
    ).all()
    stats = {row.sensor_type: row for row in stats_rows}

    return render_template(
        "station.html",
        station_tree=tree,
        station_id=station_id,
        station_sensors=station_sensors,
        stats=stats,
    )


@bp.get("/<int:station_id>/<sensor_type>")
def readings(station_id: int, sensor_type: str):
    tree = station_tree()
    station_sensors = tree.get(station_id, [])

    # Only pages that correspond to a real sensor/station pair exist.
    if sensor_type not in station_sensors:
        abort(404)

    # Select columns instead of entities: this keeps every row even if the
    # underlying table has no primary key (or has duplicate timestamps).
    readings = db.session.execute(
        select(
            Reading.timestamp,
            Reading.value,
            Reading.sensor_type,
            Reading.station_id,
        )
        .where(
            Reading.station_id == station_id,
            Reading.sensor_type == sensor_type,
        )
        .order_by(Reading.timestamp.desc())
    ).all()

    return render_template(
        "readings.html",
        station_tree=tree,
        station_id=station_id,
        sensor_type=sensor_type,
        station_sensors=station_sensors,
        other_sensors=[sensor for sensor in station_sensors if sensor != sensor_type],
        readings=readings,
    )


@bp.app_errorhandler(404)
def not_found(_error):
    return (
        render_template("404.html", station_tree=station_tree()),
        404,
    )
