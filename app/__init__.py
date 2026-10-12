"""Fabrique de l'application Flask JobPilot Maroc."""
import secrets
from pathlib import Path

import click
from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import Config

from . import constants
from .extensions import csrf, db
from .utils import register_template_filters, today_local


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    """Active les clés étrangères SQLite (ON DELETE CASCADE / SET NULL)."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _load_secret_key(app: Flask):
    if app.config.get("SECRET_KEY"):
        return
    key_file = Path(app.config["INSTANCE_DIR"]) / "secret_key"
    if key_file.exists():
        app.config["SECRET_KEY"] = key_file.read_text(encoding="utf-8").strip()
    else:
        key = secrets.token_hex(32)
        key_file.write_text(key, encoding="utf-8")
        app.config["SECRET_KEY"] = key


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, instance_path=str(Path(Config.INSTANCE_DIR).resolve()))
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    for key in ("INSTANCE_DIR", "UPLOAD_FOLDER", "BACKUP_FOLDER", "DATABASE_PATH"):
        app.config[key] = Path(app.config[key])
    if "SQLALCHEMY_DATABASE_URI" not in (overrides or {}):
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{app.config['DATABASE_PATH'].as_posix()}"

    for key in ("INSTANCE_DIR", "UPLOAD_FOLDER", "BACKUP_FOLDER"):
        app.config[key].mkdir(parents=True, exist_ok=True)
    _load_secret_key(app)

    db.init_app(app)
    csrf.init_app(app)
    register_template_filters(app)

    from .routes import applications, dashboard, documents, events, exports, preparation, settings

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(applications.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(preparation.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(exports.bp)

    _register_template_context(app)
    _register_error_handlers(app)
    _register_security_headers(app)
    _register_cli(app)

    from .services.setup_service import init_database

    with app.app_context():
        init_database()
    return app


def _register_template_context(app: Flask):
    from .models import Application
    from .services.deadline_service import LEVELS, deadline_badge, deadline_level
    from .services.setup_service import get_profile

    app.jinja_env.globals.update(
        deadline_badge=deadline_badge,
        deadline_level=deadline_level,
        LEVELS=LEVELS,
        C=constants,
    )

    @app.context_processor
    def inject_globals():
        if request.endpoint == "static":
            return {}
        overdue = Application.query.filter(
            Application.archived.is_(False),
            Application.next_due_date.isnot(None),
            Application.next_due_date <= today_local(),
        ).all()
        return {
            "profile": get_profile(),
            "today": today_local(),
            "nav_overdue_count": sum(1 for a in overdue if a.is_active),
        }


def _register_error_handlers(app: Flask):
    def render_error(code, title, message):
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(CSRFError)
    def csrf_error(_e):
        return render_error(400, "Session expirée",
                            "Le formulaire a expiré ou le jeton de sécurité est invalide. Rechargez la page et réessayez.")

    @app.errorhandler(400)
    def bad_request(_e):
        return render_error(400, "Requête invalide", "La requête envoyée est incorrecte.")

    @app.errorhandler(404)
    def not_found(_e):
        return render_error(404, "Page introuvable", "La page ou l’élément demandé n’existe pas (ou a été supprimé).")

    @app.errorhandler(413)
    def too_large(_e):
        limit = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return render_error(413, "Fichier trop volumineux", f"La taille maximale d’une requête est de {limit} Mo.")

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_error(500, "Erreur interne", "Une erreur inattendue s’est produite. Aucune donnée n’a été modifiée par cette requête.")


def _register_security_headers(app: Flask):
    @app.after_request
    def headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'",
        )
        return response


def _register_cli(app: Flask):
    @app.cli.command("init-db")
    def init_db_command():
        """Crée les tables manquantes et les données de référence (sans rien supprimer)."""
        from .services.setup_service import init_database

        init_database()
        click.echo(f"Base initialisée : {app.config['DATABASE_PATH']}")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Ajoute des données d'exemple FICTIVES (préfixées [EXEMPLE])."""
        from .services.seed_service import seed_demo

        count = seed_demo()
        click.echo(f"{count} candidature(s) d'exemple créée(s)." if count
                   else "Des données d'exemple existent déjà : rien n'a été ajouté.")

    @app.cli.command("purge-demo")
    def purge_demo_command():
        """Supprime uniquement les données d'exemple."""
        from .services.seed_service import purge_demo

        result = purge_demo()
        click.echo(f"Supprimé : {result['applications']} candidature(s), {result['documents']} document(s), "
                   f"{result['topics']} sujet(s) de révision d'exemple.")

    @app.cli.command("backup")
    def backup_command():
        """Crée une sauvegarde de la base dans instance/backups."""
        from .services.backup_service import create_backup

        click.echo(f"Sauvegarde créée : {create_backup('cli')}")
