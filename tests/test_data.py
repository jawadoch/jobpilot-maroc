import io
import json
import re
import sqlite3

from app.models import Application
from app.services import statistics
from app.services.deadline_service import deadline_level

from .conftest import private_payload, public_payload


def test_csv_export_excel_compatible(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload(city="Laâyoune"))
    r = client.get("/donnees/candidatures.csv")
    assert r.status_code == 200
    assert r.data.startswith(b"\xef\xbb\xbf")  # BOM UTF-8 pour Excel
    text = r.data.decode("utf-8-sig")
    header = text.splitlines()[0]
    assert header.startswith("titre;organisation;secteur")
    assert "Laâyoune" in text and "Ingénieur d’État — Informatique" in text
    assert "15/01/2030" in text  # date au format français


def test_json_exports(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    data = json.loads(client.get("/donnees/candidatures.json").data)
    assert data["applications"][0]["public_details"]["competition_code"] == "CODE-1"
    assert data["applications"][0]["checklist"]
    full = json.loads(client.get("/donnees/export-complet.json").data)
    assert {"profile", "statuses", "documents", "preparation_subjects"} <= set(full)


def _import(client, csv_text, encoding="utf-8-sig"):
    r = client.post("/donnees/import", data={"file": (io.BytesIO(csv_text.encode(encoding)), "import.csv")},
                    content_type="multipart/form-data")
    html = r.get_data(as_text=True)
    token = re.search(r'name="token"[^>]*value="([a-f0-9]{32})"', html)
    return html, token.group(1) if token else None


def test_csv_import_preview_validation_and_duplicates(client, ctx):
    client.post("/candidatures/nouvelle", data=private_payload())  # existe déjà
    csv_text = (
        "titre;organisation;secteur;categorie;ville;statut;priorite;date_limite\n"
        "Ingénieur Data;Agence publique;public;Concours public;Rabat;À examiner;Haute;30/11/2030\n"
        "Data Engineer;Entreprise test;privé;CDI;Casablanca;;;\n"
        "Sans secteur;Org;inconnu;;;;;\n"
        "Mauvaise date;Org;public;;;;;31/02/2030\n"
        "Ingénieur Data;Agence publique;public;;;;;\n"
    )
    html, token = _import(client, csv_text)
    assert token
    assert "secteur invalide" in html and "date invalide" in html
    assert "existe déjà" in html and "doublon dans le fichier" in html
    assert Application.query.count() == 1  # rien n'est inséré avant confirmation

    client.post("/donnees/import/confirmer", data={"token": token, "action": "importer"})
    assert Application.query.count() == 2
    imported = Application.query.filter_by(title="Ingénieur Data").one()
    assert imported.sector == "public" and imported.priority == 3
    assert imported.public_details.deadline_date.isoformat() == "2030-11-30"
    assert imported.checklist_items

    # ré-importer le même fichier ne crée pas de doublon
    html, token = _import(client, csv_text)
    client.post("/donnees/import/confirmer", data={"token": token, "action": "importer"})
    assert Application.query.count() == 2


def test_csv_import_accepts_cp1252_and_comma(client, ctx):
    html, token = _import(client, "titre,organisation,secteur\nIngénieur,Société,privé\n", encoding="cp1252")
    client.post("/donnees/import/confirmer", data={"token": token, "action": "importer"})
    assert Application.query.filter_by(title="Ingénieur").count() == 1


def test_import_round_trip_from_export(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    exported = client.get("/donnees/candidatures.csv").data.decode("utf-8-sig")
    html, token = _import(client, exported.replace("Ingénieur d’État — Informatique", "Copie importée"))
    client.post("/donnees/import/confirmer", data={"token": token, "action": "importer"})
    assert Application.query.filter_by(title="Copie importée").count() == 1


def test_backup_and_restore(client, app, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    r = client.post("/parametres/sauvegarde/creer")
    assert r.status_code == 200 and r.data.startswith(b"SQLite format 3\x00")
    backup_bytes = r.data

    client.post("/candidatures/nouvelle", data=private_payload())
    assert Application.query.count() == 2

    # refus : confirmation manquante
    client.post("/parametres/sauvegarde/restaurer", data={
        "file": (io.BytesIO(backup_bytes), "b.db"), "confirm_text": "non"}, content_type="multipart/form-data")
    assert Application.query.count() == 2
    # refus : fichier invalide
    client.post("/parametres/sauvegarde/restaurer", data={
        "file": (io.BytesIO(b"pas une base"), "b.db"), "acknowledge": "y", "confirm_text": "RESTAURER"},
        content_type="multipart/form-data")
    assert Application.query.count() == 2

    r = client.post("/parametres/sauvegarde/restaurer", data={
        "file": (io.BytesIO(backup_bytes), "b.db"), "acknowledge": "y", "confirm_text": "RESTAURER"},
        content_type="multipart/form-data", follow_redirects=True)
    assert "Base restaurée" in r.get_data(as_text=True)
    assert Application.query.count() == 1
    safety = list(app.config["BACKUP_FOLDER"].glob("jobpilot-avant-restauration-*.db"))
    assert safety
    conn = sqlite3.connect(safety[0])
    assert conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 2
    conn.close()


def test_backup_download_rejects_path_traversal(client):
    assert client.get("/parametres/sauvegarde/..%2F..%2Fsecret_key").status_code == 404
    assert client.get("/parametres/sauvegarde/jobpilot.db").status_code == 404


def test_statistics_empty_and_response_rate(client, ctx):
    stats = statistics.dashboard_stats()
    assert stats["total"] == 0 and stats["response"]["rate"] is None
    charts = statistics.chart_data()
    assert charts["sector"]["values"] == [0, 0]

    client.post("/candidatures/nouvelle", data=public_payload(status="envoyee", force_status="y"))
    client.post("/candidatures/nouvelle", data=private_payload(status="entretien_rh"))
    client.post("/candidatures/nouvelle", data=private_payload(title="Autre", status="a_examiner"))
    client.post("/candidatures/nouvelle", data=private_payload(title="Retirée", status="retiree"))
    stats = statistics.dashboard_stats()
    assert stats["total"] == 4
    # envoyées = envoyee + entretien_rh (préparation et retirée exclues) ; réponses = entretien_rh
    assert stats["response"] == {"submitted": 2, "responded": 1, "rate": 50.0}
    assert stats["active"] == 3


def test_deadline_levels():
    from datetime import date
    today = date(2026, 10, 12)
    assert deadline_level(date(2026, 10, 11), today=today) == "overdue"
    assert deadline_level(today, today=today) == "today"
    assert deadline_level(date(2026, 10, 15), today=today) == "soon3"
    assert deadline_level(date(2026, 10, 19), today=today) == "soon7"
    assert deadline_level(date(2026, 11, 1), today=today) == "upcoming"
    assert deadline_level(date(2026, 10, 1), done=True, today=today) == "done"
    assert deadline_level(None) is None
