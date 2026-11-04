from __future__ import annotations

from . import db


class Reading(db.Model):
    """One sensor reading sent by a balloon (station)."""

    __tablename__ = "readings"

    sensor_type = db.Column(db.Text, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    station_id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, primary_key=True, index=True)

    __table_args__ = (
        db.CheckConstraint("value >= 0", name="ck_readings_value_non_negative"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Reading station={self.station_id!r} sensor={self.sensor_type!r} "
            f"value={self.value!r} timestamp={self.timestamp!r}>"
        )
