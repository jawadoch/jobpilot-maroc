"""Stockage sécurisé des documents importés.

- Les fichiers sont renommés avec un identifiant aléatoire (UUID) : le nom
  fourni par l'utilisateur n'est jamais utilisé comme chemin.
- Extension, taille et signature (« magic bytes ») sont vérifiées.
- Les fichiers ne sont jamais exécutés ni affichés en ligne : téléchargement uniquement.
"""
import re
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

STORED_NAME_RE = re.compile(r"^[a-f0-9]{32}\.[a-z0-9]{2,5}$")

MIME_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt": "application/vnd.oasis.opendocument.text",
    "rtf": "application/rtf",
    "txt": "text/plain",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}

SIGNATURES = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "docx": [b"PK\x03\x04"],
    "odt": [b"PK\x03\x04"],
    "doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    "rtf": [b"{\\rtf"],
}


def upload_folder() -> Path:
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[1].lower() if filename and "." in filename else ""


def save_upload(file_storage) -> dict:
    """Valide et enregistre un fichier ; lève ValueError avec un message en français."""
    if file_storage is None or not file_storage.filename:
        raise ValueError("Aucun fichier sélectionné.")
    original = file_storage.filename
    ext = extension_of(original)
    allowed = current_app.config["ALLOWED_EXTENSIONS"]
    if ext not in allowed:
        raise ValueError("Type de fichier non autorisé. Formats acceptés : " + ", ".join(sorted(allowed)) + ".")

    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    if size == 0:
        raise ValueError("Le fichier est vide.")
    if size > max_mb * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux (maximum {max_mb} Mo).")

    head = stream.read(16)
    stream.seek(0)
    expected = SIGNATURES.get(ext)
    if expected and not any(head.startswith(sig) for sig in expected):
        raise ValueError("Le contenu du fichier ne correspond pas à son extension.")
    if ext == "txt" and b"\x00" in head:
        raise ValueError("Le fichier texte semble binaire.")

    stored = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(upload_folder() / stored)
    return {
        "stored_filename": stored,
        "original_filename": secure_filename(original) or f"document.{ext}",
        "mime_type": MIME_TYPES.get(ext, "application/octet-stream"),
        "size_bytes": size,
    }


def stored_path(stored_filename: str | None) -> Path | None:
    """Chemin d'un fichier stocké, uniquement s'il est valide et dans uploads/."""
    if not stored_filename or not STORED_NAME_RE.match(stored_filename):
        return None
    folder = upload_folder().resolve()
    path = (folder / stored_filename).resolve()
    if path.parent != folder or not path.is_file():
        return None
    return path


def delete_stored_file(stored_filename: str | None):
    path = stored_path(stored_filename)
    if path:
        path.unlink(missing_ok=True)
