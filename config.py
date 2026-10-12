"""Configuration de JobPilot Maroc.

Toutes les valeurs sensibles ou propres à la machine sont lues depuis les
variables d'environnement (ou un fichier .env à la racine du projet).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # Si JOBPILOT_SECRET_KEY n'est pas défini, une clé aléatoire est générée
    # une seule fois et conservée dans instance/secret_key (voir app/__init__.py).
    SECRET_KEY = os.environ.get("JOBPILOT_SECRET_KEY")

    INSTANCE_DIR = Path(os.environ.get("JOBPILOT_INSTANCE_DIR", BASE_DIR / "instance"))
    DATABASE_PATH = INSTANCE_DIR / "jobpilot.db"
    BACKUP_FOLDER = INSTANCE_DIR / "backups"
    UPLOAD_FOLDER = Path(os.environ.get("JOBPILOT_UPLOAD_DIR", BASE_DIR / "uploads"))

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Taille maximale d'un document importé (Mo)
    MAX_UPLOAD_MB = _int_env("JOBPILOT_MAX_UPLOAD_MB", 10)
    # Taille maximale d'une requête (restauration d'une sauvegarde incluse)
    MAX_CONTENT_LENGTH = _int_env("JOBPILOT_MAX_REQUEST_MB", 200) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "odt", "rtf", "txt", "jpg", "jpeg", "png"}

    # Identifiant IANA du fuseau marocain (il n'existe pas de "Europe/Casablanca")
    TIMEZONE = "Africa/Casablanca"
    ITEMS_PER_PAGE = _int_env("JOBPILOT_ITEMS_PER_PAGE", 20)

    WTF_CSRF_TIME_LIMIT = None  # application locale mono-utilisateur
    HOST = os.environ.get("JOBPILOT_HOST", "127.0.0.1")
    PORT = _int_env("JOBPILOT_PORT", 5000)
