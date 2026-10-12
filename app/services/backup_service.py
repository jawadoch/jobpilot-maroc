"""Sauvegarde et restauration de la base SQLite + archive des documents.

La restauration :
1. valide le fichier (en-tête SQLite, intégrité, tables attendues) ;
2. crée automatiquement une sauvegarde de la base actuelle ;
3. copie la sauvegarde dans la base via l'API de sauvegarde SQLite.
Rien n'est supprimé silencieusement.
"""
import io
import re
import sqlite3
import zipfile
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..utils import now_local

REQUIRED_TABLES = {"applications", "statuses", "application_events", "documents", "checklist_items"}
BACKUP_NAME_RE = re.compile(r"^jobpilot-[a-z-]+-\d{8}-\d{6}(-\d+)?\.db$")
SQLITE_HEADER = b"SQLite format 3\x00"


def database_path() -> Path:
    return Path(current_app.config["DATABASE_PATH"])


def backup_folder() -> Path:
    folder = Path(current_app.config["BACKUP_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _copy_sqlite(source: Path, target: Path):
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def create_backup(label: str = "manuelle") -> Path:
    """Copie cohérente de la base (même si elle est ouverte) dans instance/backups."""
    db.session.commit()
    stamp = now_local().strftime("%Y%m%d-%H%M%S")
    folder = backup_folder()
    target = folder / f"jobpilot-{label}-{stamp}.db"
    counter = 1
    while target.exists():
        target = folder / f"jobpilot-{label}-{stamp}-{counter}.db"
        counter += 1
    _copy_sqlite(database_path(), target)
    return target


def list_backups():
    folder = backup_folder()
    files = [p for p in folder.iterdir() if p.is_file() and BACKUP_NAME_RE.match(p.name)]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def resolve_backup(name: str) -> Path | None:
    """Renvoie le chemin d'une sauvegarde existante, sans accepter de chemin arbitraire."""
    if not BACKUP_NAME_RE.match(name or ""):
        return None
    path = backup_folder() / name
    return path if path.is_file() else None


def validate_backup_file(path: Path) -> tuple[bool, str]:
    try:
        with open(path, "rb") as fh:
            if fh.read(16) != SQLITE_HEADER:
                return False, "Le fichier n’est pas une base de données SQLite."
    except OSError:
        return False, "Fichier illisible."
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            check = conn.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                return False, "La vérification d’intégrité de la sauvegarde a échoué."
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing = REQUIRED_TABLES - tables
            if missing:
                return False, "Ce fichier n’est pas une sauvegarde JobPilot (tables manquantes : " + ", ".join(sorted(missing)) + ")."
            count = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return False, f"Base de données invalide : {exc}"
    return True, f"Sauvegarde valide ({count} candidature{'s' if count != 1 else ''})."


def restore_backup(uploaded: Path) -> Path:
    ok, message = validate_backup_file(uploaded)
    if not ok:
        raise ValueError(message)
    safety_copy = create_backup("avant-restauration")
    db.session.remove()
    db.engine.dispose()
    _copy_sqlite(uploaded, database_path())
    db.engine.dispose()
    return safety_copy


def uploads_zip() -> io.BytesIO:
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if folder.exists():
            for path in sorted(folder.iterdir()):
                if path.is_file() and not path.name.startswith("."):
                    archive.write(path, arcname=f"uploads/{path.name}")
    buffer.seek(0)
    return buffer
