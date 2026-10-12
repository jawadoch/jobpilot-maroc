import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test",
        "INSTANCE_DIR": tmp_path,
        "DATABASE_PATH": tmp_path / "test.db",
        "UPLOAD_FOLDER": tmp_path / "uploads",
        "BACKUP_FOLDER": tmp_path / "backups",
        "MAX_UPLOAD_MB": 1,
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


def public_payload(**overrides):
    data = {
        "title": "Ingénieur d’État — Informatique",
        "organization": "Ministère test",
        "sector": "public",
        "category": "concours",
        "city": "Rabat",
        "country": "Maroc",
        "work_mode": "onsite",
        "status": "a_examiner",
        "priority": "3",
        "reference": "REF-1",
        "public_details-competition_code": "CODE-1",
        "public_details-grade": "Ingénieur d’État 1er grade",
        "public_details-scale": "Échelle 11",
        "public_details-deadline_date": "2030-01-15",
        "public_details-deadline_time": "16:00",
        "public_details-result": "pending",
        "private_details-currency": "MAD",
        "private_details-cv_document_id": "0",
        "private_details-cover_letter_document_id": "0",
    }
    data.update(overrides)
    return data


def private_payload(**overrides):
    data = {
        "title": "Data Engineer",
        "organization": "Entreprise test",
        "sector": "private",
        "category": "cdi",
        "city": "Casablanca",
        "country": "Maroc",
        "work_mode": "hybrid",
        "status": "a_examiner",
        "priority": "2",
        "public_details-result": "pending",
        "private_details-currency": "MAD",
        "private_details-cv_document_id": "0",
        "private_details-cover_letter_document_id": "0",
    }
    data.update(overrides)
    return data
