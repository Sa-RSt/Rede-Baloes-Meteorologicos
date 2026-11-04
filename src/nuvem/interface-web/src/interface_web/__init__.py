from __future__ import annotations

import os
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

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create the readings table if it does not exist."""
        db.create_all()
        click.echo("Banco de dados inicializado.")

    # For this small read-only application it is convenient to make sure the
    # table exists as soon as the app is created. create_all() is a no-op when
    # the table (and the database file) already exist.
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
