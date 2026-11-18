from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, render_template
from sqlalchemy import func, select

from . import db
from .models import Balloon, Reading

bp = Blueprint("main", __name__)


def balloon_tree() -> dict[int, dict[str, Any]]:
    """Return every balloon with its known sensor types.

    The result has the shape ``{balao_id: {"nome": str, "sensors": [...]}}``.
    Balloons without readings are included, with an empty sensor list.
    """
    rows = db.session.execute(
        select(Balloon.id, Balloon.nome, Reading.sensor)
        .outerjoin(Reading, Reading.balao_id == Balloon.id)
        .distinct()
        .order_by(Balloon.id, Reading.sensor)
    ).all()

    tree: dict[int, dict[str, Any]] = {}
    for balao_id, nome, sensor in rows:
        entry = tree.setdefault(balao_id, {"nome": nome, "sensors": []})
        if sensor is not None:
            entry["sensors"].append(sensor)
    return tree


@bp.get("/")
def index():
    """Show every balloon as a card linking to its sensor page."""
    return render_template("index.html", balloon_tree=balloon_tree())


@bp.get("/<int:balao_id>")
def balloon(balao_id: int):
    """Show every sensor of a balloon as a card linking to its table."""
    tree = balloon_tree()
    entry = tree.get(balao_id)

    if entry is None:
        abort(404)

    stats_rows = db.session.execute(
        select(
            Reading.sensor,
            func.count().label("reading_count"),
            func.max(Reading.data_hora).label("latest_timestamp"),
        )
        .where(Reading.balao_id == balao_id)
        .group_by(Reading.sensor)
    ).all()
    stats = {row.sensor: row for row in stats_rows}

    return render_template(
        "balloon.html",
        balloon_tree=tree,
        balao_id=balao_id,
        balao_nome=entry["nome"],
        balloon_sensors=entry["sensors"],
        stats=stats,
    )


@bp.get("/<int:balao_id>/<sensor>")
def readings(balao_id: int, sensor: str):
    tree = balloon_tree()
    entry = tree.get(balao_id)
    balloon_sensors = entry["sensors"] if entry is not None else []

    # Only pages that correspond to a real balloon/sensor pair exist.
    if entry is None or sensor not in balloon_sensors:
        abort(404)

    # Select columns instead of entities: this keeps every row even if the
    # underlying table contains duplicate timestamps.
    readings = db.session.execute(
        select(
            Reading.id,
            Reading.data_hora,
            Reading.leitura,
            Reading.sensor,
            Reading.balao_id,
        )
        .where(
            Reading.balao_id == balao_id,
            Reading.sensor == sensor,
        )
        .order_by(Reading.data_hora.desc(), Reading.id.desc())
    ).all()

    return render_template(
        "readings.html",
        balloon_tree=tree,
        balao_id=balao_id,
        balao_nome=entry["nome"],
        sensor=sensor,
        balloon_sensors=balloon_sensors,
        readings=readings,
    )


@bp.app_errorhandler(404)
def not_found(_error):
    return (
        render_template("404.html", balloon_tree=balloon_tree()),
        404,
    )
