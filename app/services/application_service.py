"""Règles métier sur les candidatures."""
import re
import unicodedata

from ..extensions import db
from ..models import (
    Application,
    ChecklistItem,
    ChecklistTemplateItem,
    PrivateJobDetails,
    PublicCompetitionDetails,
    Status,
    log_activity,
)
from .deadline_service import refresh_application


def normalize(value) -> str:
    """Minuscules, sans accents ni ponctuation : « d’État » == « d'etat » == « D ETAT »."""
    text = re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFC", str(value or "")))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def duplicate_key(title, organization, reference=None) -> tuple:
    return normalize(title), normalize(organization), normalize(reference)


def find_duplicate(title, organization, reference=None, exclude_id=None) -> Application | None:
    """Comparaison normalisée (casse, accents, espaces) titre + organisation + référence."""
    key = duplicate_key(title, organization, reference)
    for app in Application.query.all():
        if app.id != exclude_id and duplicate_key(app.title, app.organization, app.reference) == key:
            return app
    return None


def ensure_details(app: Application):
    if app.sector == "public" and app.public_details is None:
        app.public_details = PublicCompetitionDetails(result="pending")
    if app.sector == "private" and app.private_details is None:
        app.private_details = PrivateJobDetails(currency="MAD")


def apply_checklist_template(app: Application) -> int:
    """Ajoute les éléments du modèle absents de la checklist ; renvoie le nombre ajouté."""
    existing = {normalize(item.label) for item in app.checklist_items}
    position = max((i.position for i in app.checklist_items), default=-1) + 1
    added = 0
    for tpl in ChecklistTemplateItem.query.order_by(ChecklistTemplateItem.position).all():
        if normalize(tpl.label) in existing:
            continue
        app.checklist_items.append(ChecklistItem(
            label=tpl.label, category=tpl.category, required=tpl.required, position=position,
        ))
        position += 1
        added += 1
    return added


def status_change_blocked(app: Application, new_code: str) -> str | None:
    """Message d'avertissement si le statut exige un dossier complet qui ne l'est pas."""
    status = Status.query.filter_by(code=new_code).first()
    if status is None or not status.requires_complete_dossier:
        return None
    if app.status == new_code:
        return None
    summary = app.checklist_summary
    if summary["missing"]:
        labels = ", ".join(i.label for i in summary["missing"])
        return (f"Impossible de passer au statut « {status.label} » : pièces obligatoires manquantes "
                f"({labels}). Cochez « Forcer le statut » pour passer outre.")
    return None


def duplicate_application(app: Application) -> Application:
    first_status = Status.query.order_by(Status.position).first()
    copy = Application(
        title=f"{app.title} (copie)",
        organization=app.organization,
        sector=app.sector,
        category=app.category,
        specialty=app.specialty,
        city=app.city,
        country=app.country,
        work_mode=app.work_mode,
        posting_url=app.posting_url,
        source=app.source,
        contact_name=app.contact_name,
        contact_email=app.contact_email,
        contact_phone=app.contact_phone,
        reference=app.reference,
        description=app.description,
        notes=app.notes,
        date_discovered=app.date_discovered,
        status=first_status.code if first_status else app.status,
        priority=app.priority,
        is_sample=app.is_sample,
    )
    if app.public_details:
        cols = [c.name for c in PublicCompetitionDetails.__table__.columns
                if c.name not in ("id", "application_id")]
        copy.public_details = PublicCompetitionDetails(**{c: getattr(app.public_details, c) for c in cols})
        copy.public_details.result = "pending"
    if app.private_details:
        cols = [c.name for c in PrivateJobDetails.__table__.columns
                if c.name not in ("id", "application_id")]
        copy.private_details = PrivateJobDetails(**{c: getattr(app.private_details, c) for c in cols})
    for item in app.checklist_items:
        copy.checklist_items.append(ChecklistItem(
            label=item.label, category=item.category, required=item.required,
            position=item.position, notes=item.notes,
        ))
    db.session.add(copy)
    refresh_application(copy)
    log_activity("duplicate", f"Candidature dupliquée depuis #{app.id}", copy)
    return copy
