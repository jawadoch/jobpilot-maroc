"""Export CSV/JSON et import CSV validé (avec aperçu et détection des doublons)."""
import csv
import io
import json
import re
import secrets
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from flask import current_app

from ..constants import CATEGORIES, PRIORITIES, SECTORS, WORK_MODES
from ..extensions import db
from ..models import (
    Application,
    ChecklistTemplateItem,
    Document,
    PrepSubject,
    PreparationTopic,
    PrivateJobDetails,
    PublicCompetitionDetails,
    Status,
    UserProfile,
    log_activity,
)
from ..utils import fr_date, parse_date, utcnow
from .application_service import apply_checklist_template, duplicate_key, normalize
from .deadline_service import refresh_application

# Colonnes du modèle d'import (et des premières colonnes de l'export CSV)
IMPORT_COLUMNS = [
    ("titre", "Intitulé du poste (obligatoire)"),
    ("organisation", "Organisation / administration (obligatoire)"),
    ("secteur", "public ou privé (obligatoire)"),
    ("categorie", "Concours public, CDI, CDD, Stage, Freelance, Doctorat, Autre"),
    ("specialite", ""),
    ("ville", ""),
    ("pays", "Maroc par défaut"),
    ("mode_travail", "Sur site, Hybride, Télétravail, Non précisé"),
    ("url", ""),
    ("source", ""),
    ("reference", "Référence / code du concours"),
    ("statut", "Libellé ou code du statut"),
    ("priorite", "Basse, Moyenne, Haute (ou 1-3)"),
    ("date_decouverte", "JJ/MM/AAAA"),
    ("date_envoi", "JJ/MM/AAAA"),
    ("date_limite", "JJ/MM/AAAA (concours publics)"),
    ("prochaine_action", ""),
    ("echeance_action", "JJ/MM/AAAA"),
    ("notes", ""),
]
EXPORT_EXTRA_COLUMNS = ["id", "resultat_concours", "archivee", "exemple", "cree_le", "mis_a_jour_le"]
TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")


# --- Export ---------------------------------------------------------------------

def application_row(app: Application) -> dict:
    public = app.public_details if app.sector == "public" else None
    deadline = public.deadline_date if public else None
    return {
        "titre": app.title,
        "organisation": app.organization,
        "secteur": app.sector_label,
        "categorie": app.category_label,
        "specialite": app.specialty or "",
        "ville": app.city or "",
        "pays": app.country or "",
        "mode_travail": app.work_mode_label,
        "url": app.posting_url or "",
        "source": app.source or "",
        "reference": app.reference or "",
        "statut": app.status_label,
        "priorite": app.priority_label,
        "date_decouverte": fr_date(app.date_discovered, ""),
        "date_envoi": fr_date(app.date_applied, ""),
        "date_limite": fr_date(deadline, ""),
        "prochaine_action": app.next_action or "",
        "echeance_action": fr_date(app.next_action_due, ""),
        "notes": app.notes or "",
        "id": app.id,
        "resultat_concours": public.result_label if public else "",
        "archivee": "oui" if app.archived else "non",
        "exemple": "oui" if app.is_sample else "non",
        "cree_le": app.created_at.strftime("%d/%m/%Y %H:%M") + " UTC" if app.created_at else "",
        "mis_a_jour_le": app.updated_at.strftime("%d/%m/%Y %H:%M") + " UTC" if app.updated_at else "",
    }


def export_csv(applications) -> bytes:
    """CSV compatible Excel : UTF-8 avec BOM, séparateur point-virgule."""
    buffer = io.StringIO()
    columns = [c for c, _ in IMPORT_COLUMNS] + EXPORT_EXTRA_COLUMNS
    writer = csv.DictWriter(buffer, fieldnames=columns, delimiter=";", lineterminator="\r\n")
    writer.writeheader()
    for app in applications:
        writer.writerow(application_row(app))
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def import_template_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow([c for c, _ in IMPORT_COLUMNS])
    writer.writerow([
        "Ingénieur d’État — Data", "Administration (à compléter)", "public", "Concours public",
        "Big Data", "Rabat", "Maroc", "Sur site", "", "Site officiel", "REF-000", "À examiner",
        "Haute", "01/10/2026", "", "31/10/2026", "Préparer le dossier", "20/10/2026", "Ligne d’exemple à supprimer",
    ])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _jsonable(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def model_to_dict(obj, exclude=()):
    return {c.name: _jsonable(getattr(obj, c.name)) for c in obj.__table__.columns if c.name not in exclude}


def application_to_dict(app: Application) -> dict:
    data = model_to_dict(app)
    data["status_label"] = app.status_label
    data["public_details"] = model_to_dict(app.public_details) if app.public_details else None
    data["private_details"] = model_to_dict(app.private_details) if app.private_details else None
    data["events"] = [model_to_dict(e) for e in app.events]
    data["checklist"] = [model_to_dict(i) for i in app.checklist_items]
    data["documents"] = [
        {"document_id": link.document_id, "name": link.document.name, "version": link.document.version,
         "purpose": link.purpose}
        for link in app.document_links
    ]
    data["preparation_topics"] = [model_to_dict(t) for t in app.prep_topics]
    return data


def export_json(applications, full=False) -> bytes:
    payload = {
        "application": "JobPilot Maroc",
        "format_version": 1,
        "exported_at_utc": utcnow().isoformat(timespec="seconds"),
        "applications": [application_to_dict(a) for a in applications],
    }
    if full:
        profile = UserProfile.query.first()
        payload.update({
            "profile": model_to_dict(profile) if profile else None,
            "statuses": [model_to_dict(s) for s in Status.query.order_by(Status.position)],
            "documents": [model_to_dict(d) for d in Document.query.order_by(Document.id)],
            "preparation_subjects": [model_to_dict(s) for s in PrepSubject.query.order_by(PrepSubject.position)],
            "preparation_topics": [model_to_dict(t) for t in PreparationTopic.query.order_by(PreparationTopic.id)],
            "checklist_template": [model_to_dict(t) for t in ChecklistTemplateItem.query.order_by(ChecklistTemplateItem.position)],
        })
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


# --- Import ---------------------------------------------------------------------

def _lookup(value, mapping: dict, default=None):
    """Retrouve un code à partir du code ou du libellé (insensible casse/accents)."""
    key = normalize(value)
    if not key:
        return default
    for code, label in mapping.items():
        if key in (normalize(code), normalize(label)):
            return code
    return None


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Encodage du fichier non reconnu (utilisez UTF-8).")


def parse_import_csv(raw: bytes) -> dict:
    text = _decode(raw)
    if not text.strip():
        raise ValueError("Le fichier est vide.")
    first_line = text.splitlines()[0]
    delimiter = max([";", ",", "\t"], key=first_line.count)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = [normalize(h).replace(" ", "_") for h in (reader.fieldnames or [])]
    reader.fieldnames = headers
    for required in ("titre", "organisation", "secteur"):
        if required not in headers:
            raise ValueError(f"Colonne obligatoire absente : « {required} ». Utilisez le modèle CSV.")

    statuses = {s.code: s.label for s in Status.query.all()}
    default_status = Status.query.order_by(Status.position).first()
    existing_keys = {duplicate_key(a.title, a.organization, a.reference): a.id for a in Application.query.all()}
    seen_keys = set()
    rows = []
    for line_no, raw_row in enumerate(reader, start=2):
        row = {k: (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue
        errors = []
        title, org = row.get("titre", ""), row.get("organisation", "")
        if not title:
            errors.append("titre manquant")
        if not org:
            errors.append("organisation manquante")
        if len(title) > 200 or len(org) > 200:
            errors.append("titre ou organisation trop long (200 caractères max.)")
        sector = _lookup(row.get("secteur"), SECTORS)
        if sector is None:
            errors.append("secteur invalide (public ou privé)")
        category = _lookup(row.get("categorie"), CATEGORIES, default="concours" if sector == "public" else "autre")
        if category is None:
            errors.append(f"catégorie inconnue « {row.get('categorie')} »")
        work_mode = _lookup(row.get("mode_travail"), WORK_MODES, default="unknown")
        if work_mode is None:
            errors.append(f"mode de travail inconnu « {row.get('mode_travail')} »")
        status = _lookup(row.get("statut"), statuses, default=default_status.code if default_status else None)
        if status is None:
            errors.append(f"statut inconnu « {row.get('statut')} »")
        priority_text = row.get("priorite", "")
        priority = int(priority_text) if priority_text in ("1", "2", "3") else _lookup(priority_text, PRIORITIES, default=2)
        if priority is None:
            errors.append(f"priorité inconnue « {priority_text} »")
        dates = {}
        for column in ("date_decouverte", "date_envoi", "date_limite", "echeance_action"):
            value = row.get(column, "")
            parsed = parse_date(value)
            if value and parsed is None:
                errors.append(f"date invalide en colonne {column} : « {value} »")
            dates[column] = parsed.isoformat() if parsed else None
        url = row.get("url", "")
        if url and not url.lower().startswith(("http://", "https://")):
            errors.append("l’URL doit commencer par http:// ou https://")

        key = duplicate_key(title, org, row.get("reference"))
        duplicate = None
        if key in existing_keys:
            duplicate = f"existe déjà (candidature #{existing_keys[key]})"
        elif key in seen_keys:
            duplicate = "doublon dans le fichier"
        seen_keys.add(key)

        rows.append({
            "line": line_no,
            "errors": errors,
            "duplicate": duplicate,
            "data": {
                "title": title, "organization": org, "sector": sector, "category": category,
                "specialty": row.get("specialite") or None, "city": row.get("ville") or None,
                "country": row.get("pays") or "Maroc", "work_mode": work_mode,
                "posting_url": url or None, "source": row.get("source") or None,
                "reference": row.get("reference") or None, "status": status, "priority": priority,
                "date_discovered": dates["date_decouverte"], "date_applied": dates["date_envoi"],
                "deadline": dates["date_limite"], "next_action": row.get("prochaine_action") or None,
                "next_action_due": dates["echeance_action"], "notes": row.get("notes") or None,
            },
        })
    return {"rows": rows, "valid": sum(1 for r in rows if not r["errors"] and not r["duplicate"])}


def _import_dir() -> Path:
    folder = Path(current_app.config["INSTANCE_DIR"]) / "imports"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def store_preview(preview: dict) -> str:
    token = secrets.token_hex(16)
    (_import_dir() / f"{token}.json").write_text(json.dumps(preview, ensure_ascii=False), encoding="utf-8")
    return token


def load_preview(token: str) -> dict | None:
    if not TOKEN_RE.match(token or ""):
        return None
    path = _import_dir() / f"{token}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def discard_preview(token: str):
    if TOKEN_RE.match(token or ""):
        path = _import_dir() / f"{token}.json"
        if path.is_file():
            path.unlink()


def commit_import(preview: dict) -> tuple[int, int]:
    """Insère les lignes valides ; les doublons sont revérifiés au moment de l'insertion."""
    existing = {duplicate_key(a.title, a.organization, a.reference) for a in Application.query.all()}
    created, skipped = 0, 0
    for row in preview["rows"]:
        data = dict(row["data"])
        key = duplicate_key(data["title"], data["organization"], data["reference"])
        if row["errors"] or row["duplicate"] or key in existing:
            skipped += 1
            continue
        deadline = parse_date(data.pop("deadline"))
        for field in ("date_discovered", "date_applied", "next_action_due"):
            data[field] = parse_date(data[field])
        app = Application(**data)
        if app.sector == "public":
            app.public_details = PublicCompetitionDetails(result="pending", deadline_date=deadline)
            apply_checklist_template(app)
        else:
            app.private_details = PrivateJobDetails(currency="MAD")
        db.session.add(app)
        refresh_application(app)
        log_activity("import", "Candidature importée depuis un fichier CSV", app)
        existing.add(key)
        created += 1
    db.session.commit()
    return created, skipped
