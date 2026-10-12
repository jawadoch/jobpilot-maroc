"""Initialisation sûre de la base : crée les tables manquantes et les données de
référence (statuts, matières, modèle de checklist, profil) sans jamais supprimer
de données existantes."""
from sqlalchemy import inspect, text

from ..constants import (
    DEFAULT_CHECKLIST_TEMPLATE,
    DEFAULT_PREP_SUBJECTS,
    DEFAULT_PROFILE,
    DEFAULT_STATUSES,
)
from ..extensions import db
from ..models import AppMeta, ChecklistTemplateItem, PrepSubject, Status, UserProfile

REFERENCE_DATA_VERSION = "1"


def init_database():
    db.create_all()  # ne crée que les tables absentes, ne supprime rien
    with db.engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
    ensure_reference_data()


def ensure_reference_data():
    meta = db.session.get(AppMeta, "reference_data_version")
    if meta is None:
        if Status.query.count() == 0:
            for pos, (code, label, kind, requires) in enumerate(DEFAULT_STATUSES):
                db.session.add(Status(code=code, label=label, kind=kind, position=pos,
                                      requires_complete_dossier=requires))
        if PrepSubject.query.count() == 0:
            pos = 0
            for group, names in DEFAULT_PREP_SUBJECTS.items():
                for name in names:
                    db.session.add(PrepSubject(name=name, group=group, position=pos))
                    pos += 1
        if ChecklistTemplateItem.query.count() == 0:
            for pos, (label, category, required) in enumerate(DEFAULT_CHECKLIST_TEMPLATE):
                db.session.add(ChecklistTemplateItem(label=label, category=category,
                                                     required=required, position=pos))
        db.session.add(AppMeta(key="reference_data_version", value=REFERENCE_DATA_VERSION))
    if UserProfile.query.first() is None:
        db.session.add(UserProfile(**DEFAULT_PROFILE))
    db.session.commit()


def get_profile() -> UserProfile:
    profile = UserProfile.query.first()
    if profile is None:
        profile = UserProfile(**DEFAULT_PROFILE)
        db.session.add(profile)
        db.session.commit()
    return profile


def table_names():
    return set(inspect(db.engine).get_table_names())
