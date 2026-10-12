"""Modèles SQLAlchemy de JobPilot Maroc.

Conventions de dates :
- Les dates « métier » saisies par l'utilisateur (date limite, examen, entretien…)
  sont stockées en heure locale marocaine, sous forme de Date + Time optionnelle.
- Les horodatages techniques (created_at, updated_at, uploaded_at) sont en UTC
  et convertis en heure de Casablanca à l'affichage.
"""
from datetime import datetime

from .constants import (
    CATEGORIES,
    CLOSED_KINDS,
    COMPETITION_RESULTS,
    DIFFICULTIES,
    DOCUMENT_CATEGORIES,
    EVENT_ICONS,
    EVENT_KINDS,
    PREP_STATUS_BADGES,
    PREP_STATUSES,
    PRIORITIES,
    SECTORS,
    STATUS_KIND_BADGES,
    SUBMISSION_METHODS,
    WORK_MODES,
)
from .extensions import db
from .utils import today_local, utcnow


class UserProfile(db.Model):
    __tablename__ = "user_profile"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False, default="")
    headline = db.Column(db.String(200))
    degree = db.Column(db.String(250))
    degree_school = db.Column(db.String(150))
    degree_year = db.Column(db.String(10))
    previous_degree = db.Column(db.String(250))
    previous_school = db.Column(db.String(150))
    previous_year = db.Column(db.String(10))
    domains = db.Column(db.Text)
    location = db.Column(db.String(120))
    target_cities = db.Column(db.Text)
    objective = db.Column(db.Text)
    email = db.Column(db.String(150))
    phone = db.Column(db.String(40))
    linkedin = db.Column(db.String(250))
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    @staticmethod
    def _split(value):
        return [part.strip() for part in (value or "").split(",") if part.strip()]

    @property
    def city_list(self):
        return self._split(self.target_cities)

    @property
    def domain_list(self):
        return self._split(self.domains)


class Status(db.Model):
    __tablename__ = "statuses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    label = db.Column(db.String(80), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="preparation")
    position = db.Column(db.Integer, nullable=False, default=0)
    requires_complete_dossier = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def is_closed(self):
        return self.kind in CLOSED_KINDS

    @property
    def badge_class(self):
        return STATUS_KIND_BADGES.get(self.kind, "text-bg-secondary")

    def __repr__(self):
        return f"<Status {self.code}>"


class Application(db.Model):
    __tablename__ = "applications"
    __table_args__ = (
        db.Index("ix_applications_sector_status", "sector", "status"),
        db.CheckConstraint("priority BETWEEN 1 AND 3", name="ck_applications_priority"),
        db.CheckConstraint("sector IN ('public', 'private')", name="ck_applications_sector"),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    organization = db.Column(db.String(200), nullable=False)
    sector = db.Column(db.String(10), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False, default="autre", index=True)
    specialty = db.Column(db.String(150))
    city = db.Column(db.String(100), index=True)
    country = db.Column(db.String(80), default="Maroc")
    work_mode = db.Column(db.String(10), nullable=False, default="unknown")
    posting_url = db.Column(db.String(500))
    source = db.Column(db.String(100))
    contact_name = db.Column(db.String(150))
    contact_email = db.Column(db.String(150))
    contact_phone = db.Column(db.String(40))
    reference = db.Column(db.String(100), index=True)
    description = db.Column(db.Text)
    notes = db.Column(db.Text)
    date_discovered = db.Column(db.Date)
    date_applied = db.Column(db.Date, index=True)
    status = db.Column(db.String(40), db.ForeignKey("statuses.code"), nullable=False, index=True)
    priority = db.Column(db.Integer, nullable=False, default=2, index=True)
    next_action = db.Column(db.String(250))
    next_action_due = db.Column(db.Date)
    # Prochaine échéance non terminée (événements + prochaine action), dénormalisée
    # pour permettre le tri et le filtrage en SQL. Voir services/deadline_service.py
    next_due_date = db.Column(db.Date, index=True)
    archived = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_sample = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    status_obj = db.relationship("Status", lazy="joined")
    public_details = db.relationship(
        "PublicCompetitionDetails", uselist=False, back_populates="application",
        cascade="all, delete-orphan",
    )
    private_details = db.relationship(
        "PrivateJobDetails", uselist=False, back_populates="application",
        cascade="all, delete-orphan",
    )
    events = db.relationship(
        "ApplicationEvent", back_populates="application", cascade="all, delete-orphan",
        order_by="(ApplicationEvent.event_date, ApplicationEvent.event_time)",
    )
    document_links = db.relationship(
        "ApplicationDocument", back_populates="application", cascade="all, delete-orphan",
    )
    checklist_items = db.relationship(
        "ChecklistItem", back_populates="application", cascade="all, delete-orphan",
        order_by="(ChecklistItem.position, ChecklistItem.id)",
    )
    # Sans cascade de suppression : les sujets de révision sont conservés
    # (application_id passe à NULL) si la candidature est supprimée.
    prep_topics = db.relationship("PreparationTopic", back_populates="application")

    # --- Libellés --------------------------------------------------------------
    @property
    def sector_label(self):
        return SECTORS.get(self.sector, self.sector)

    @property
    def category_label(self):
        return CATEGORIES.get(self.category, self.category)

    @property
    def work_mode_label(self):
        return WORK_MODES.get(self.work_mode, "Non précisé")

    @property
    def priority_label(self):
        return PRIORITIES.get(self.priority, "—")

    @property
    def status_label(self):
        return self.status_obj.label if self.status_obj else self.status

    @property
    def is_public(self):
        return self.sector == "public"

    @property
    def is_closed(self):
        return bool(self.status_obj and self.status_obj.is_closed)

    @property
    def is_active(self):
        return not self.archived and not self.is_closed

    @property
    def documents(self):
        return [link.document for link in self.document_links]

    @property
    def pending_events(self):
        return [e for e in self.events if not e.done]

    @property
    def deadline_event(self):
        for event in self.events:
            if event.kind == "deadline":
                return event
        return None

    # --- Dossier / checklist ---------------------------------------------------
    @property
    def checklist_summary(self):
        required = [i for i in self.checklist_items if i.required]
        done = [i for i in required if i.done]
        missing = [i for i in required if not i.done]
        percent = round(100 * len(done) / len(required)) if required else None
        return {
            "total": len(self.checklist_items),
            "required": len(required),
            "done": len(done),
            "missing": missing,
            "optional_missing": [i for i in self.checklist_items if not i.required and not i.done],
            "percent": percent,
            "ready": not missing,
        }

    def __repr__(self):
        return f"<Application {self.id} {self.title!r}>"


class PublicCompetitionDetails(db.Model):
    __tablename__ = "public_competition_details"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    administration = db.Column(db.String(200))
    competition_title = db.Column(db.String(250))
    competition_code = db.Column(db.String(100))
    grade = db.Column(db.String(150))
    scale = db.Column(db.String(50))
    specialty = db.Column(db.String(150))
    vacancies = db.Column(db.Integer)
    candidates_count = db.Column(db.Integer)
    region = db.Column(db.String(150))
    announcement_url = db.Column(db.String(500))
    submission_method = db.Column(db.String(20))
    opening_date = db.Column(db.Date)
    deadline_date = db.Column(db.Date, index=True)
    deadline_time = db.Column(db.Time)
    eligibility = db.Column(db.Text)
    required_diploma = db.Column(db.Text)
    required_documents_text = db.Column(db.Text)
    mobility_required = db.Column(db.Text)
    possible_assignment = db.Column(db.Text)
    shortlist_date = db.Column(db.Date)
    results_date = db.Column(db.Date)
    result = db.Column(db.String(20), nullable=False, default="pending")
    result_url = db.Column(db.String(500))
    admin_notes = db.Column(db.Text)

    application = db.relationship("Application", back_populates="public_details")

    @property
    def result_label(self):
        return COMPETITION_RESULTS.get(self.result, "—")

    @property
    def submission_method_label(self):
        return SUBMISSION_METHODS.get(self.submission_method or "", "Non précisé")


class PrivateJobDetails(db.Model):
    __tablename__ = "private_job_details"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    salary_min = db.Column(db.Numeric(12, 2))
    salary_max = db.Column(db.Numeric(12, 2))
    salary_expectation = db.Column(db.Numeric(12, 2))
    salary_frequency = db.Column(db.String(20))
    currency = db.Column(db.String(10), default="MAD")
    currency_other = db.Column(db.String(20))
    mobility_requirements = db.Column(db.Text)
    relocation_notes = db.Column(db.Text)
    cv_document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"))
    cover_letter_document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"))
    referral = db.Column(db.String(250))
    tech_assessment_required = db.Column(db.Boolean, nullable=False, default=False)
    tech_assessment_date = db.Column(db.Date)
    tech_assessment_time = db.Column(db.Time)
    interview_feedback = db.Column(db.Text)
    hr_feedback = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)
    negotiation_status = db.Column(db.String(20))
    offer_details = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)

    application = db.relationship("Application", back_populates="private_details")
    cv_document = db.relationship("Document", foreign_keys=[cv_document_id])
    cover_letter_document = db.relationship("Document", foreign_keys=[cover_letter_document_id])

    @property
    def currency_label(self):
        if self.currency == "other":
            return self.currency_other or ""
        return self.currency or "MAD"


class ApplicationEvent(db.Model):
    """Étape, échéance ou rendez-vous lié à une candidature (multi-étapes)."""

    __tablename__ = "application_events"
    __table_args__ = (db.Index("ix_events_done_date", "done", "event_date"),)

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind = db.Column(db.String(20), nullable=False, default="other", index=True)
    title = db.Column(db.String(200))
    event_date = db.Column(db.Date, nullable=False, index=True)
    event_time = db.Column(db.Time)
    location = db.Column(db.String(250))
    details = db.Column(db.Text)
    done = db.Column(db.Boolean, nullable=False, default=False)
    outcome = db.Column(db.Text)
    # Renseigné quand l'événement est synchronisé depuis un champ de la fiche
    # (ex. "public_deadline") : sa date se modifie alors depuis la fiche.
    auto_key = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    application = db.relationship("Application", back_populates="events")

    @property
    def kind_label(self):
        return EVENT_KINDS.get(self.kind, "Autre")

    @property
    def icon(self):
        return EVENT_ICONS.get(self.kind, "bi-calendar-event")

    @property
    def display_title(self):
        return self.title or self.kind_label

    @property
    def starts_at(self):
        return datetime.combine(self.event_date, self.event_time) if self.event_time else None


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(30), nullable=False, default="autre", index=True)
    # Nom de fichier généré (UUID) dans le dossier uploads/ — jamais un chemin libre
    stored_filename = db.Column(db.String(100), unique=True)
    original_filename = db.Column(db.String(255))
    mime_type = db.Column(db.String(100))
    size_bytes = db.Column(db.Integer)
    version = db.Column(db.String(30), nullable=False, default="1")
    notes = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    expires_on = db.Column(db.Date)
    previous_version_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"))
    is_sample = db.Column(db.Boolean, nullable=False, default=False, index=True)

    previous_version = db.relationship("Document", remote_side=[id], backref="newer_versions")
    application_links = db.relationship(
        "ApplicationDocument", back_populates="document", cascade="all, delete-orphan"
    )

    @property
    def category_label(self):
        return DOCUMENT_CATEGORIES.get(self.category, "Autre")

    @property
    def has_file(self):
        return bool(self.stored_filename)

    @property
    def extension(self):
        if self.original_filename and "." in self.original_filename:
            return self.original_filename.rsplit(".", 1)[1].lower()
        return ""

    @property
    def is_expired(self):
        return bool(self.expires_on and self.expires_on < today_local())

    @property
    def display_name(self):
        return f"{self.name} (v{self.version})"


class ApplicationDocument(db.Model):
    """Association plusieurs-à-plusieurs candidature ↔ document."""

    __tablename__ = "application_documents"

    application_id = db.Column(
        db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True
    )
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    attached_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    purpose = db.Column(db.String(150))

    application = db.relationship("Application", back_populates="document_links")
    document = db.relationship("Document", back_populates="application_links")


class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(30))
    required = db.Column(db.Boolean, nullable=False, default=True)
    done = db.Column(db.Boolean, nullable=False, default=False)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"))
    notes = db.Column(db.String(250))
    position = db.Column(db.Integer, nullable=False, default=0)

    application = db.relationship("Application", back_populates="checklist_items")
    document = db.relationship("Document")

    @property
    def category_label(self):
        return DOCUMENT_CATEGORIES.get(self.category or "", "")


class ChecklistTemplateItem(db.Model):
    """Modèle de checklist appliqué aux nouveaux concours publics."""

    __tablename__ = "checklist_template_items"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(30))
    required = db.Column(db.Boolean, nullable=False, default=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    @property
    def category_label(self):
        return DOCUMENT_CATEGORIES.get(self.category or "", "")


class PrepSubject(db.Model):
    __tablename__ = "prep_subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    group = db.Column(db.String(150), nullable=False, default="Autre")
    position = db.Column(db.Integer, nullable=False, default=0)

    topics = db.relationship("PreparationTopic", back_populates="subject")


class PreparationTopic(db.Model):
    __tablename__ = "preparation_topics"
    __table_args__ = (
        db.CheckConstraint("confidence BETWEEN 1 AND 5", name="ck_topic_confidence"),
    )

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("prep_subjects.id"), nullable=False, index=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    topic = db.Column(db.String(250), nullable=False)
    priority = db.Column(db.Integer, nullable=False, default=2)
    difficulty = db.Column(db.Integer, nullable=False, default=2)
    confidence = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default="not_started", index=True)
    notes = db.Column(db.Text)
    next_revision = db.Column(db.Date, index=True)
    minutes_spent = db.Column(db.Integer, nullable=False, default=0)
    exam_weight = db.Column(db.String(50))
    is_sample = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    subject = db.relationship("PrepSubject", back_populates="topics")
    application = db.relationship("Application", back_populates="prep_topics")

    @property
    def status_label(self):
        return PREP_STATUSES.get(self.status, self.status)

    @property
    def status_badge(self):
        return PREP_STATUS_BADGES.get(self.status, "text-bg-secondary")

    @property
    def priority_label(self):
        return PRIORITIES.get(self.priority, "—")

    @property
    def difficulty_label(self):
        return DIFFICULTIES.get(self.difficulty, "—")

    @property
    def is_weak(self):
        return self.confidence <= 2 and self.status != "mastered"


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    application_title = db.Column(db.String(200))
    action = db.Column(db.String(40), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    application = db.relationship("Application")


class SavedFilter(db.Model):
    __tablename__ = "saved_filters"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    endpoint = db.Column(db.String(60), nullable=False, default="applications.index")
    query_string = db.Column(db.String(1000), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class AppMeta(db.Model):
    """Paires clé/valeur internes (version des données de référence, etc.)."""

    __tablename__ = "app_meta"

    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(250))


def log_activity(action: str, message: str, application: Application | None = None):
    """Ajoute une ligne au journal (sans contenu de document)."""
    entry = ActivityLog(
        action=action,
        message=message[:500],
        application=application,
        application_title=application.title if application else None,
    )
    db.session.add(entry)
    return entry
