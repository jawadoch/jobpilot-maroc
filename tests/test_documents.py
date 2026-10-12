import io

from app.extensions import db
from app.models import Application, Document

from .conftest import public_payload

PDF = b"%PDF-1.4\n% test\n"


def upload(client, name="CV Data Engineer", category="cv", content=PDF, filename="cv.pdf", version="1"):
    return client.post("/documents/ajouter", data={
        "name": name, "category": category, "version": version,
        "file": (io.BytesIO(content), filename),
    }, content_type="multipart/form-data", follow_redirects=True)


def test_upload_download_and_secure_storage(client, app, ctx):
    response = upload(client)
    assert "Document ajouté" in response.get_data(as_text=True)
    doc = Document.query.one()
    assert doc.stored_filename.endswith(".pdf") and "cv" not in doc.stored_filename
    assert (app.config["UPLOAD_FOLDER"] / doc.stored_filename).is_file()
    r = client.get(f"/documents/{doc.id}/telecharger")
    assert r.status_code == 200 and r.data == PDF
    assert "attachment" in r.headers["Content-Disposition"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_upload_rejects_bad_extension_mismatch_and_size(client, ctx):
    upload(client, filename="evil.exe", content=b"MZ....")
    upload(client, filename="fake.pdf", content=b"not a pdf")
    upload(client, filename="big.pdf", content=b"%PDF" + b"0" * (2 * 1024 * 1024))
    assert Document.query.count() == 0


def test_stored_filename_cannot_escape_upload_folder(client, ctx):
    upload(client)
    doc = Document.query.one()
    doc.stored_filename = "../../config.py"
    db.session.commit()
    r = client.get(f"/documents/{doc.id}/telecharger")
    assert r.status_code == 302  # refusé, redirigé vers la fiche


def test_new_version_does_not_overwrite(client, app, ctx):
    upload(client)
    first = Document.query.one()
    first_file = first.stored_filename
    client.post(f"/documents/{first.id}/nouvelle-version", data={
        "version": "2", "file": (io.BytesIO(PDF + b"v2"), "cv-v2.pdf")}, content_type="multipart/form-data")
    docs = Document.query.order_by(Document.id).all()
    assert len(docs) == 2
    assert docs[1].previous_version_id == first.id and docs[1].version == "2"
    assert (app.config["UPLOAD_FOLDER"] / first_file).is_file()


def test_attach_document_and_link_checklist_item(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    upload(client)
    application = Application.query.one()
    doc = Document.query.one()
    cv_item = next(i for i in application.checklist_items if i.category == "cv")
    html = client.get(f"/candidatures/{application.id}?onglet=dossier").get_data(as_text=True)
    assert "Disponible dans la bibliothèque" in html

    client.post(f"/candidatures/{application.id}/checklist/{cv_item.id}/lier", data={"document_id": doc.id})
    db.session.expire_all()
    assert cv_item.done and cv_item.document_id == doc.id
    assert doc in application.documents

    client.post(f"/candidatures/{application.id}/documents/{doc.id}/detacher")
    db.session.expire_all()
    assert doc not in application.documents and cv_item.document_id is None


def test_delete_document_removes_file_and_links(client, app, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    upload(client)
    application = Application.query.one()
    doc = Document.query.one()
    stored = doc.stored_filename
    client.post(f"/candidatures/{application.id}/documents", data={"document_id": doc.id})
    client.post(f"/documents/{doc.id}/supprimer")
    assert Document.query.count() == 0
    assert not (app.config["UPLOAD_FOLDER"] / stored).exists()
    db.session.expire_all()
    assert application.document_links == []
