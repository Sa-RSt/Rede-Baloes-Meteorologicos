from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import click
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create and configure the interface-web Flask application."""
    app = Flask(__name__)

    # The database lives next to pyproject.toml by default, so the application
    # behaves the same regardless of the directory it is started from.
    project_root = Path(app.root_path).resolve().parents[1]
    default_database = project_root / "sqlite.db"

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-secret-key"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", f"sqlite:///{default_database}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is not None:
        app.config.update(test_config)

    db.init_app(app)

    # Importing the model registers it with SQLAlchemy.
    from . import models  # noqa: F401
    from .routes import bp

    app.register_blueprint(bp)

    @app.template_filter("timestamp")
    def format_timestamp(value: Any) -> str:
        if value is None:
            return "\u2014"
        if isinstance(value, str):
            return value
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @app.template_filter("number")
    def format_number(value: Any) -> str:
        """Render NUMERIC values without trailing zeros or exponent notation."""
        if value is None:
            return "\u2014"
        if isinstance(value, Decimal):
            if value == value.to_integral_value():
                return str(int(value))
            return format(value.normalize(), "f")
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create the Baloes and Leituras tables if they do not exist."""
        db.create_all()
        click.echo("Banco de dados inicializado.")

    # For this small read-only application it is convenient to make sure the
    # tables exist as soon as the app is created. create_all() is a no-op when
    # the tables (and the database file) already exist.
    with app.app_context():
        db.create_all()

    return app


def main() -> None:
    app = create_app()
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
