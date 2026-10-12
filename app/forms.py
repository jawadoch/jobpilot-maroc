"""Formulaires Flask-WTF (CSRF inclus) avec messages de validation en français."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    Form,
    FormField,
    HiddenField,
    IntegerField,
    SelectField,
    StringField,
    TextAreaField,
    TimeField,
)
from wtforms.i18n import get_translations
from wtforms.validators import URL, DataRequired, Length, NumberRange, Optional, Regexp, ValidationError

from .constants import (
    CATEGORIES,
    COMPETITION_RESULTS,
    CONFIDENCE_LEVELS,
    CURRENCIES,
    DIFFICULTIES,
    DOCUMENT_CATEGORIES,
    EVENT_KINDS,
    NEGOTIATION_STATUSES,
    PREP_STATUSES,
    PRIORITIES,
    SALARY_FREQUENCIES,
    SECTORS,
    STATUS_KINDS,
    SUBMISSION_METHODS,
    WORK_MODES,
)

FR = ["fr_FR", "fr"]
REQUIRED = "Ce champ est obligatoire."
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_RE = r"^[0-9+()./\s-]{6,30}$"
DOC_EXTENSIONS = ["pdf", "doc", "docx", "odt", "rtf", "txt", "jpg", "jpeg", "png"]


class FrenchMeta:
    def get_translations(self, form):
        return get_translations(FR)


class BaseForm(FlaskForm):
    class Meta(FrenchMeta):
        pass


class SubForm(Form):
    """Sous-formulaire imbriqué (le jeton CSRF est porté par le formulaire parent)."""

    class Meta:
        locales = FR


def url_field(label):
    return StringField(label, validators=[Optional(), Length(max=500),
                                          URL(require_tld=False, message="Adresse web invalide (http:// ou https://).")])


def choices(mapping):
    return list(mapping.items())


# --- Candidatures ---------------------------------------------------------------

class PublicDetailsForm(SubForm):
    administration = StringField("Administration / établissement public", validators=[Optional(), Length(max=200)])
    competition_title = StringField("Intitulé du concours", validators=[Optional(), Length(max=250)])
    competition_code = StringField("Référence / code du concours", validators=[Optional(), Length(max=100)])
    grade = StringField("Grade", validators=[Optional(), Length(max=150)],
                        render_kw={"placeholder": "ex. Ingénieur d’État de 1er grade"})
    scale = StringField("Échelle administrative", validators=[Optional(), Length(max=50)],
                        render_kw={"placeholder": "ex. Échelle 11"})
    specialty = StringField("Spécialité du concours", validators=[Optional(), Length(max=150)])
    vacancies = IntegerField("Nombre de postes", validators=[Optional(), NumberRange(min=0, max=100000)])
    candidates_count = IntegerField("Nombre de candidats (si connu)", validators=[Optional(), NumberRange(min=0, max=10000000)])
    region = StringField("Région / province", validators=[Optional(), Length(max=150)])
    announcement_url = url_field("Lien de l’annonce officielle")
    submission_method = SelectField("Mode de dépôt", choices=choices(SUBMISSION_METHODS), validators=[Optional()])
    opening_date = DateField("Ouverture des candidatures", validators=[Optional()])
    deadline_date = DateField("Date limite de dépôt", validators=[Optional()])
    deadline_time = TimeField("Heure limite", validators=[Optional()])
    eligibility = TextAreaField("Conditions d’éligibilité", validators=[Optional(), Length(max=5000)])
    required_diploma = TextAreaField("Diplôme exigé et équivalences", validators=[Optional(), Length(max=3000)])
    required_documents_text = TextAreaField("Pièces exigées (texte de l’annonce)", validators=[Optional(), Length(max=5000)])
    mobility_required = TextAreaField("Exigence de mobilité", validators=[Optional(), Length(max=2000)])
    possible_assignment = TextAreaField("Affectation possible (filiale, autre ville…)", validators=[Optional(), Length(max=2000)])
    shortlist_date = DateField("Publication des présélectionnés", validators=[Optional()])
    results_date = DateField("Publication des résultats", validators=[Optional()])
    result = SelectField("Résultat du concours", choices=choices(COMPETITION_RESULTS), default="pending")
    result_url = url_field("Lien des résultats officiels")
    admin_notes = TextAreaField("Notes administratives", validators=[Optional(), Length(max=5000)])


class PrivateDetailsForm(SubForm):
    salary_min = DecimalField("Salaire proposé — min.", places=2, validators=[Optional(), NumberRange(min=0)])
    salary_max = DecimalField("Salaire proposé — max.", places=2, validators=[Optional(), NumberRange(min=0)])
    salary_expectation = DecimalField("Mes prétentions", places=2, validators=[Optional(), NumberRange(min=0)])
    salary_frequency = SelectField("Fréquence", choices=choices(SALARY_FREQUENCIES), validators=[Optional()])
    currency = SelectField("Devise", choices=choices(CURRENCIES), default="MAD")
    currency_other = StringField("Autre devise", validators=[Optional(), Length(max=20)])
    mobility_requirements = TextAreaField("Télétravail / mobilité exigée", validators=[Optional(), Length(max=2000)])
    relocation_notes = TextAreaField("Relocalisation / international", validators=[Optional(), Length(max=2000)],
                                     render_kw={"placeholder": "ex. relocalisation en France, visa, package…"})
    cv_document_id = SelectField("Version du CV envoyée", coerce=int, default=0)
    cover_letter_document_id = SelectField("Lettre de motivation envoyée", coerce=int, default=0)
    referral = StringField("Recommandation / cooptation", validators=[Optional(), Length(max=250)])
    tech_assessment_required = BooleanField("Test technique demandé")
    tech_assessment_date = DateField("Date limite du test technique", validators=[Optional()])
    tech_assessment_time = TimeField("Heure limite du test", validators=[Optional()])
    interview_feedback = TextAreaField("Retours d’entretien", validators=[Optional(), Length(max=5000)])
    hr_feedback = TextAreaField("Retours RH", validators=[Optional(), Length(max=5000)])
    follow_up_date = DateField("Date de relance", validators=[Optional()])
    negotiation_status = SelectField("Négociation", choices=choices(NEGOTIATION_STATUSES), validators=[Optional()])
    offer_details = TextAreaField("Détails de l’offre", validators=[Optional(), Length(max=5000)])
    rejection_reason = TextAreaField("Motif de refus ou de retrait", validators=[Optional(), Length(max=3000)])


class ApplicationForm(BaseForm):
    title = StringField("Intitulé du poste", validators=[DataRequired(REQUIRED), Length(max=200)])
    organization = StringField("Organisation / entreprise / administration",
                               validators=[DataRequired(REQUIRED), Length(max=200)])
    sector = SelectField("Secteur", choices=choices(SECTORS), validators=[DataRequired(REQUIRED)])
    category = SelectField("Catégorie / type de contrat", choices=choices(CATEGORIES))
    specialty = StringField("Spécialité / domaine", validators=[Optional(), Length(max=150)])
    city = StringField("Ville", validators=[Optional(), Length(max=100)])
    country = StringField("Pays", default="Maroc", validators=[Optional(), Length(max=80)])
    work_mode = SelectField("Mode de travail", choices=choices(WORK_MODES), default="unknown")
    posting_url = url_field("Lien de l’offre")
    source = StringField("Plateforme / source", validators=[Optional(), Length(max=100)])
    contact_name = StringField("Contact / recruteur", validators=[Optional(), Length(max=150)])
    contact_email = StringField("E-mail du contact", validators=[
        Optional(), Length(max=150), Regexp(EMAIL_RE, message="Adresse e-mail invalide.")])
    contact_phone = StringField("Téléphone du contact", validators=[
        Optional(), Regexp(PHONE_RE, message="Numéro de téléphone invalide.")])
    reference = StringField("Référence de candidature", validators=[Optional(), Length(max=100)])
    description = TextAreaField("Description du poste", validators=[Optional(), Length(max=20000)])
    notes = TextAreaField("Notes personnelles", validators=[Optional(), Length(max=20000)])
    date_discovered = DateField("Date de découverte", validators=[Optional()])
    date_applied = DateField("Date d’envoi", validators=[Optional()])
    status = SelectField("Statut actuel", validators=[DataRequired(REQUIRED)])
    priority = SelectField("Priorité", choices=choices(PRIORITIES), coerce=int, default=2)
    next_action = StringField("Prochaine action", validators=[Optional(), Length(max=250)],
                              render_kw={"placeholder": "ex. Vérifier la liste des présélectionnés"})
    next_action_due = DateField("Échéance de la prochaine action", validators=[Optional()])
    force_status = BooleanField("Forcer le statut malgré un dossier incomplet")

    public_details = FormField(PublicDetailsForm)
    private_details = FormField(PrivateDetailsForm)

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        if self.next_action_due.data and not (self.next_action.data or "").strip():
            self.next_action.errors.append("Indiquez l’action correspondant à cette échéance.")
            ok = False
        if self.sector.data == "public":
            pub = self.public_details.form
            if pub.deadline_time.data and not pub.deadline_date.data:
                pub.deadline_time.errors.append("Indiquez aussi la date limite.")
                ok = False
            if pub.opening_date.data and pub.deadline_date.data and pub.opening_date.data > pub.deadline_date.data:
                pub.deadline_date.errors.append("La date limite précède la date d’ouverture.")
                ok = False
        else:
            priv = self.private_details.form
            if (priv.salary_min.data is not None and priv.salary_max.data is not None
                    and priv.salary_min.data > priv.salary_max.data):
                priv.salary_max.errors.append("Le maximum doit être supérieur ou égal au minimum.")
                ok = False
            if priv.tech_assessment_time.data and not priv.tech_assessment_date.data:
                priv.tech_assessment_time.errors.append("Indiquez aussi la date du test.")
                ok = False
            if priv.currency.data == "other" and not (priv.currency_other.data or "").strip():
                priv.currency_other.errors.append("Précisez la devise.")
                ok = False
        return ok


class QuickStatusForm(BaseForm):
    status = SelectField("Nouveau statut", validators=[DataRequired(REQUIRED)])
    force_status = BooleanField("Forcer malgré un dossier incomplet")


# --- Événements -------------------------------------------------------------------

class EventForm(BaseForm):
    application_id = SelectField("Candidature", coerce=int, validators=[DataRequired(REQUIRED)])
    kind = SelectField("Type d’étape", choices=choices(EVENT_KINDS))
    title = StringField("Intitulé (facultatif)", validators=[Optional(), Length(max=200)])
    event_date = DateField("Date", validators=[DataRequired(REQUIRED)])
    event_time = TimeField("Heure", validators=[Optional()])
    location = StringField("Lieu / lien de visioconférence", validators=[Optional(), Length(max=250)])
    details = TextAreaField("Matières, programme ou description", validators=[Optional(), Length(max=5000)])
    done = BooleanField("Étape terminée")
    outcome = TextAreaField("Résultat / retour", validators=[Optional(), Length(max=5000)])


# --- Documents ------------------------------------------------------------------

class DocumentForm(BaseForm):
    name = StringField("Nom du document", validators=[DataRequired(REQUIRED), Length(max=200)],
                       render_kw={"placeholder": "ex. CV Data Engineer"})
    category = SelectField("Catégorie", choices=choices(DOCUMENT_CATEGORIES))
    version = StringField("Version", default="1", validators=[DataRequired(REQUIRED), Length(max=30)])
    expires_on = DateField("Date d’expiration (facultatif)", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    file = FileField("Fichier", validators=[FileAllowed(DOC_EXTENSIONS, "Type de fichier non autorisé.")])


class DocumentEditForm(BaseForm):
    name = StringField("Nom du document", validators=[DataRequired(REQUIRED), Length(max=200)])
    category = SelectField("Catégorie", choices=choices(DOCUMENT_CATEGORIES))
    version = StringField("Version", validators=[DataRequired(REQUIRED), Length(max=30)])
    expires_on = DateField("Date d’expiration (facultatif)", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])


class NewVersionForm(BaseForm):
    version = StringField("Numéro de la nouvelle version", validators=[DataRequired(REQUIRED), Length(max=30)])
    notes = TextAreaField("Ce qui change", validators=[Optional(), Length(max=2000)])
    expires_on = DateField("Date d’expiration (facultatif)", validators=[Optional()])
    file = FileField("Fichier", validators=[FileRequired("Sélectionnez un fichier."),
                                            FileAllowed(DOC_EXTENSIONS, "Type de fichier non autorisé.")])


class AttachDocumentForm(BaseForm):
    document_id = SelectField("Document de la bibliothèque", coerce=int, validators=[DataRequired(REQUIRED)])
    purpose = StringField("Usage (facultatif)", validators=[Optional(), Length(max=150)],
                          render_kw={"placeholder": "ex. CV envoyé"})


class ChecklistItemForm(BaseForm):
    label = StringField("Pièce", validators=[DataRequired(REQUIRED), Length(max=200)])
    category = SelectField("Catégorie de document", choices=[("", "—")] + choices(DOCUMENT_CATEGORIES),
                           validators=[Optional()])
    required = BooleanField("Obligatoire", default=True)


class ChecklistLinkForm(BaseForm):
    document_id = SelectField("Document", coerce=int)


# --- Préparation ------------------------------------------------------------------

class PrepTopicForm(BaseForm):
    subject_id = SelectField("Matière / compétence", coerce=int, validators=[DataRequired(REQUIRED)])
    application_id = SelectField("Concours / candidature liée", coerce=int, default=0)
    topic = StringField("Thème à réviser", validators=[DataRequired(REQUIRED), Length(max=250)])
    priority = SelectField("Priorité", choices=choices(PRIORITIES), coerce=int, default=2)
    difficulty = SelectField("Difficulté", choices=choices(DIFFICULTIES), coerce=int, default=2)
    confidence = SelectField("Niveau de confiance", choices=choices(CONFIDENCE_LEVELS), coerce=int, default=1)
    status = SelectField("État de la révision", choices=choices(PREP_STATUSES), default="not_started")
    next_revision = DateField("Prochaine révision", validators=[Optional()])
    minutes_spent = IntegerField("Temps passé (minutes)", default=0,
                                 validators=[Optional(), NumberRange(min=0, max=1000000)])
    exam_weight = StringField("Poids à l’examen (si connu)", validators=[Optional(), Length(max=50)],
                              render_kw={"placeholder": "ex. coefficient 2"})
    notes = TextAreaField("Notes de révision", validators=[Optional(), Length(max=20000)])


class LogTimeForm(BaseForm):
    minutes = IntegerField("Minutes", validators=[DataRequired(REQUIRED), NumberRange(min=1, max=1440)])
    confidence = SelectField("Confiance après la séance", choices=[(0, "Inchangée")] + choices(CONFIDENCE_LEVELS),
                             coerce=int, default=0)


class SubjectForm(BaseForm):
    name = StringField("Matière", validators=[DataRequired(REQUIRED), Length(max=150)])
    group = StringField("Groupe", validators=[DataRequired(REQUIRED), Length(max=150)])


# --- Paramètres ---------------------------------------------------------------------

class ProfileForm(BaseForm):
    full_name = StringField("Nom complet", validators=[DataRequired(REQUIRED), Length(max=120)])
    headline = StringField("Titre professionnel", validators=[Optional(), Length(max=200)])
    degree = StringField("Diplôme principal", validators=[Optional(), Length(max=250)])
    degree_school = StringField("Établissement", validators=[Optional(), Length(max=150)])
    degree_year = StringField("Année", validators=[Optional(), Length(max=10)])
    previous_degree = StringField("Diplôme précédent", validators=[Optional(), Length(max=250)])
    previous_school = StringField("Établissement", validators=[Optional(), Length(max=150)])
    previous_year = StringField("Année", validators=[Optional(), Length(max=10)])
    domains = TextAreaField("Domaines techniques (séparés par des virgules)", validators=[Optional(), Length(max=2000)])
    location = StringField("Localisation", validators=[Optional(), Length(max=120)])
    target_cities = StringField("Villes ciblées (séparées par des virgules)", validators=[Optional(), Length(max=1000)])
    objective = TextAreaField("Objectif principal", validators=[Optional(), Length(max=2000)])
    email = StringField("E-mail", validators=[Optional(), Length(max=150), Regexp(EMAIL_RE, message="Adresse e-mail invalide.")])
    phone = StringField("Téléphone", validators=[Optional(), Regexp(PHONE_RE, message="Numéro de téléphone invalide.")])
    linkedin = url_field("Profil LinkedIn")
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=5000)])


class StatusForm(BaseForm):
    label = StringField("Libellé", validators=[DataRequired(REQUIRED), Length(max=80)])
    kind = SelectField("Signification (pour les statistiques)", choices=choices(STATUS_KINDS))
    position = IntegerField("Ordre", default=0, validators=[Optional(), NumberRange(min=0, max=1000)])
    requires_complete_dossier = BooleanField("Exige un dossier complet")


class TemplateItemForm(BaseForm):
    label = StringField("Pièce", validators=[DataRequired(REQUIRED), Length(max=200)])
    category = SelectField("Catégorie de document", choices=[("", "—")] + choices(DOCUMENT_CATEGORIES),
                           validators=[Optional()])
    required = BooleanField("Obligatoire", default=True)


class RestoreForm(BaseForm):
    file = FileField("Fichier de sauvegarde (.db)", validators=[FileRequired("Sélectionnez un fichier."),
                                                               FileAllowed(["db", "sqlite", "sqlite3"], "Fichier .db attendu.")])
    acknowledge = BooleanField("Je comprends que les données actuelles seront remplacées",
                               validators=[DataRequired("Vous devez cocher cette case.")])
    confirm_text = StringField("Tapez RESTAURER pour confirmer", validators=[DataRequired(REQUIRED)])

    def validate_confirm_text(self, field):
        if (field.data or "").strip() != "RESTAURER":
            raise ValidationError("Tapez exactement RESTAURER.")


class ImportForm(BaseForm):
    file = FileField("Fichier CSV", validators=[FileRequired("Sélectionnez un fichier."),
                                                FileAllowed(["csv", "txt"], "Fichier .csv attendu.")])


class ImportConfirmForm(BaseForm):
    token = HiddenField(validators=[DataRequired()])


class SavedFilterForm(BaseForm):
    name = StringField("Nom du filtre", validators=[DataRequired(REQUIRED), Length(max=100)])
    query = HiddenField()
    endpoint = HiddenField()


class ConfirmForm(BaseForm):
    """Formulaire vide servant à porter le jeton CSRF des actions destructives."""
