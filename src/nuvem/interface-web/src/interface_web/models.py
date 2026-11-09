from __future__ import annotations

from sqlalchemy.orm import synonym

from . import db


class Balloon(db.Model):
    """A meteorological balloon registered in the network."""

    __tablename__ = "Baloes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    readings = db.relationship(
        "Reading",
        back_populates="balloon",
        cascade="all, delete-orphan",
        order_by="Reading.data_hora",
    )

    # Portuguese alias used by the database vocabulary.
    leituras = synonym("readings")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Balloon id={self.id!r} nome={self.nome!r}>"


class Reading(db.Model):
    """One sensor reading sent by a balloon."""

    __tablename__ = "Leituras"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    balao_id = db.Column(db.Integer, db.ForeignKey("Baloes.id"), nullable=False)
    sensor = db.Column(db.String(50), nullable=False)
    leitura = db.Column(db.Numeric, nullable=False)
    data_hora = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    balloon = db.relationship("Balloon", back_populates="readings")

    # Portuguese alias used by the database vocabulary.
    balao = synonym("balloon")

    __table_args__ = (
        db.Index("idx_leituras_balao", "balao_id"),
        db.Index("idx_leituras_data", "data_hora"),
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<Reading id={self.id!r} balao={self.balao_id!r} "
            f"sensor={self.sensor!r} leitura={self.leitura!r} "
            f"data_hora={self.data_hora!r}>"
        )


# Portuguese aliases, matching the names used by the database schema.
Balao = Balloon
Leitura = Reading
