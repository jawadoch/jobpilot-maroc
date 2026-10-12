import re

import pytest

from app import create_app
from app.extensions import db
from app.models import Application


@pytest.fixture()
def csrf_client(tmp_path):
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": True,
        "SECRET_KEY": "test",
        "INSTANCE_DIR": tmp_path,
        "DATABASE_PATH": tmp_path / "test.db",
        "UPLOAD_FOLDER": tmp_path / "uploads",
        "BACKUP_FOLDER": tmp_path / "backups",
    })
    with app.app_context():
        yield app.test_client()
        db.session.remove()
        db.engine.dispose()


def test_post_without_csrf_token_is_rejected(csrf_client):
    response = csrf_client.post("/candidatures/nouvelle", data={"title": "x", "organization": "y", "sector": "public"})
    assert response.status_code == 400
    assert "Session expirée" in response.get_data(as_text=True)
    assert Application.query.count() == 0
    assert csrf_client.post("/parametres/donnees-exemple/ajouter").status_code == 400


def test_form_round_trip_with_csrf_token(csrf_client):
    html = csrf_client.get("/candidatures/nouvelle?sector=private").get_data(as_text=True)
    token = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html).group(1)
    response = csrf_client.post("/candidatures/nouvelle", data={
        "csrf_token": token, "title": "Poste", "organization": "Org", "sector": "private", "category": "cdi",
        "work_mode": "unknown", "status": "a_examiner", "priority": "2", "public_details-result": "pending",
        "private_details-currency": "MAD", "private_details-cv_document_id": "0",
        "private_details-cover_letter_document_id": "0",
    })
    assert response.status_code == 302
    assert Application.query.count() == 1


def test_security_headers(csrf_client):
    response = csrf_client.get("/")
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
