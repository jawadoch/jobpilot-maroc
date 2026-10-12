from datetime import timedelta
from urllib.parse import urlencode

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from ..constants import CATEGORIES, PRIORITIES, SECTORS, SOURCES
from ..extensions import db
from ..forms import (
    ApplicationForm,
    AttachDocumentForm,
    ChecklistItemForm,
    ConfirmForm,
    QuickStatusForm,
    SavedFilterForm,
)
from ..models import (
    ActivityLog,
    Application,
    ApplicationDocument,
    ChecklistItem,
    Document,
    PublicCompetitionDetails,
    SavedFilter,
    Status,
    log_activity,
)
from ..services.application_service import (
    apply_checklist_template,
    duplicate_application,
    ensure_details,
    find_duplicate,
    status_change_blocked,
)
from ..services.deadline_service import refresh_application
from ..utils import safe_next, today_local, utcnow

bp = Blueprint("applications", __name__, url_prefix="/candidatures")

GENERAL_FIELDS = [
    "title", "organization", "sector", "category", "specialty", "city", "country", "work_mode",
    "posting_url", "source", "contact_name", "contact_email", "contact_phone", "reference",
    "description", "notes", "date_discovered", "date_applied", "priority", "next_action", "next_action_due",
]
LIST_ENDPOINTS = {
    "applications.index": "Toutes les candidatures",
    "applications.public_list": "Concours publics",
    "applications.private_list": "Offres du secteur privé",
}
SORTS = {
    "deadline": "Échéance la plus proche",
    "updated": "Dernière mise à jour",
    "created": "Date d’ajout",
    "priority": "Priorité",
}
DEADLINE_FILTERS = {
    "overdue": "En retard",
    "today": "Aujourd’hui",
    "7": "Dans les 7 jours",
    "30": "Dans les 30 jours",
    "none": "Sans échéance",
}
FILTER_KEYS = ("q", "sector", "status", "category", "city", "priority", "deadline", "archived", "sort", "group")


def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def get_application(app_id: int) -> Application:
    app = db.session.get(Application, app_id)
    if app is None:
        abort(404)
    return app


# --- Liste, recherche et filtres ----------------------------------------------------

def build_query(args, forced_sector=None):
    query = Application.query.options(
        selectinload(Application.checklist_items), selectinload(Application.public_details),
        selectinload(Application.private_details),
    )
    archived = args.get("archived", "")
    if archived == "only":
        query = query.filter(Application.archived.is_(True))
    elif archived != "all":
        query = query.filter(Application.archived.is_(False))

    term = (args.get("q") or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(
            Application.title.ilike(like),
            Application.organization.ilike(like),
            Application.city.ilike(like),
            Application.reference.ilike(like),
            Application.specialty.ilike(like),
            Application.public_details.has(PublicCompetitionDetails.competition_code.ilike(like)),
            Application.public_details.has(PublicCompetitionDetails.administration.ilike(like)),
        ))
    sector = forced_sector or args.get("sector")
    if sector in SECTORS:
        query = query.filter(Application.sector == sector)
    if args.get("status"):
        query = query.filter(Application.status == args["status"])
    if args.get("category") in CATEGORIES:
        query = query.filter(Application.category == args["category"])
    if args.get("city"):
        query = query.filter(Application.city.ilike(args["city"]))
    if args.get("priority") in ("1", "2", "3"):
        query = query.filter(Application.priority == int(args["priority"]))

    today = today_local()
    deadline = args.get("deadline")
    if deadline == "overdue":
        query = query.filter(Application.next_due_date < today)
    elif deadline == "today":
        query = query.filter(Application.next_due_date == today)
    elif deadline in ("7", "30"):
        query = query.filter(Application.next_due_date >= today,
                             Application.next_due_date <= today + timedelta(days=int(deadline)))
    elif deadline == "none":
        query = query.filter(Application.next_due_date.is_(None))

    if args.get("group") == "status":
        query = query.join(Status, Application.status == Status.code)
        order = [Status.position]
    else:
        order = []
    sort = args.get("sort") or "deadline"
    if sort == "updated":
        order += [Application.updated_at.desc()]
    elif sort == "created":
        order += [Application.created_at.desc()]
    elif sort == "priority":
        order += [Application.priority.desc(), Application.next_due_date.is_(None), Application.next_due_date]
    else:
        order += [Application.next_due_date.is_(None), Application.next_due_date, Application.priority.desc()]
    return query.order_by(*order, Application.id.desc())


def render_list(mode: str, endpoint: str):
    args = request.args
    forced_sector = mode if mode in SECTORS else None
    pagination = build_query(args, forced_sector).paginate(
        per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False)
    cities = sorted({c for (c,) in db.session.query(Application.city).distinct() if c}, key=str.lower)
    active_filters = {k: v for k, v in args.items() if k in FILTER_KEYS and v}
    save_form = SavedFilterForm(query=urlencode(active_filters), endpoint=endpoint)
    return render_template(
        "applications/list.html",
        mode=mode,
        endpoint=endpoint,
        page_title=LIST_ENDPOINTS[endpoint],
        pagination=pagination,
        statuses=Status.query.order_by(Status.position).all(),
        cities=cities,
        args=args,
        active_filters=active_filters,
        sorts=SORTS,
        deadline_filters=DEADLINE_FILTERS,
        saved_filters=SavedFilter.query.filter_by(endpoint=endpoint).order_by(SavedFilter.name).all(),
        save_form=save_form,
        confirm_form=ConfirmForm(),
        priorities=PRIORITIES,
    )


@bp.route("/")
def index():
    return render_list("all", "applications.index")


@bp.route("/concours-publics")
def public_list():
    return render_list("public", "applications.public_list")


@bp.route("/secteur-prive")
def private_list():
    return render_list("private", "applications.private_list")


@bp.route("/filtres", methods=["POST"])
def save_filter():
    form = SavedFilterForm()
    endpoint = form.endpoint.data if form.endpoint.data in LIST_ENDPOINTS else "applications.index"
    if form.validate_on_submit():
        query = (form.query.data or "")[:1000]
        db.session.add(SavedFilter(name=form.name.data.strip(), endpoint=endpoint, query_string=query))
        db.session.commit()
        flash("Filtre enregistré.", "success")
    else:
        flash("Indiquez un nom pour le filtre.", "danger")
    return redirect(url_for(endpoint) + (f"?{form.query.data}" if form.query.data else ""))


@bp.route("/filtres/<int:filter_id>/supprimer", methods=["POST"])
def delete_filter(filter_id):
    saved = db.session.get(SavedFilter, filter_id) or abort(404)
    endpoint = saved.endpoint
    db.session.delete(saved)
    db.session.commit()
    flash("Filtre supprimé.", "success")
    return redirect(url_for(endpoint))


# --- Création / modification ----------------------------------------------------------

def _prepare_form(form: ApplicationForm):
    form.status.choices = [(s.code, s.label) for s in Status.query.order_by(Status.position)]
    docs = Document.query.order_by(Document.category, Document.name, Document.id).all()
    docs.sort(key=lambda d: (d.category not in ("cv", "lettre_motivation"), d.category, d.name.lower()))
    doc_choices = [(d.id, f"{d.category_label} — {d.display_name}") for d in docs]
    form.private_details.cv_document_id.choices = [(0, "— Non précisé —")] + doc_choices
    form.private_details.cover_letter_document_id.choices = [(0, "— Non précisée —")] + doc_choices


def _form_context(form, app=None):
    profile_cities = []
    from ..services.setup_service import get_profile

    profile = get_profile()
    profile_cities = profile.city_list
    known_cities = {c for (c,) in db.session.query(Application.city).distinct() if c}
    return {
        "form": form,
        "application": app,
        "city_suggestions": sorted(set(profile_cities) | known_cities, key=str.lower),
        "specialty_suggestions": profile.domain_list,
        "source_suggestions": SOURCES,
    }


def _save_application(form: ApplicationForm, app: Application, is_new: bool) -> bool:
    """Copie le formulaire dans le modèle ; renvoie False si le statut est bloqué."""
    for name in GENERAL_FIELDS:
        setattr(app, name, _clean(getattr(form, name).data))
    app.country = app.country or "Maroc"
    ensure_details(app)
    if app.sector == "public":
        form.public_details.form.populate_obj(app.public_details)
        for attr in ("administration", "competition_title", "competition_code", "grade", "scale"):
            setattr(app.public_details, attr, _clean(getattr(app.public_details, attr)))
        app.public_details.submission_method = app.public_details.submission_method or None
    else:
        details = app.private_details
        form.private_details.form.populate_obj(details)
        details.cv_document_id = details.cv_document_id or None
        details.cover_letter_document_id = details.cover_letter_document_id or None
        details.salary_frequency = details.salary_frequency or None
        details.negotiation_status = details.negotiation_status or None
    if is_new and app.sector == "public" and not app.checklist_items:
        apply_checklist_template(app)

    new_status = form.status.data
    blocked = status_change_blocked(app, new_status)
    if blocked and not form.force_status.data:
        form.status.errors = list(form.status.errors) + [blocked]
        return False
    if blocked:
        flash("Statut forcé alors que des pièces obligatoires manquent. Pensez à compléter le dossier.", "warning")
    old_status = app.status
    app.status = new_status
    new_obj = Status.query.filter_by(code=new_status).first()
    if new_obj and new_obj.kind == "sent" and not app.date_applied:
        app.date_applied = today_local()
    if is_new:
        db.session.add(app)
    refresh_application(app)
    if is_new:
        log_activity("create", "Candidature créée", app)
    else:
        log_activity("update", "Candidature modifiée", app)
    if old_status and old_status != new_status and new_obj:
        log_activity("status", f"Statut : {new_obj.label}" + (" (forcé, dossier incomplet)" if blocked else ""), app)
    return True


@bp.route("/nouvelle", methods=["GET", "POST"])
def create():
    form = ApplicationForm()
    _prepare_form(form)
    if request.method == "GET":
        sector = request.args.get("sector")
        if sector in SECTORS:
            form.sector.data = sector
            form.category.data = "concours" if sector == "public" else "cdi"
        form.date_discovered.data = today_local()
        form.status.data = form.status.choices[0][0] if form.status.choices else None
    if form.validate_on_submit():
        duplicate = find_duplicate(form.title.data, form.organization.data, form.reference.data)
        if duplicate and not request.form.get("allow_duplicate"):
            flash(
                f"Une candidature identique existe déjà (#{duplicate.id} — {duplicate.title}). "
                "Cochez « Créer quand même » pour confirmer.", "warning",
            )
            return render_template("applications/form.html", duplicate=duplicate, **_form_context(form))
        app = Application()
        if _save_application(form, app, is_new=True):
            db.session.commit()
            flash("Candidature créée.", "success")
            return redirect(url_for(".detail", app_id=app.id))
        db.session.rollback()
    elif form.is_submitted():
        flash("Le formulaire contient des erreurs : vérifiez les champs signalés.", "danger")
    return render_template("applications/form.html", **_form_context(form))


@bp.route("/<int:app_id>/modifier", methods=["GET", "POST"])
def edit(app_id):
    app = get_application(app_id)
    form = ApplicationForm(obj=app)
    _prepare_form(form)
    if request.method == "GET" and app.private_details:
        form.private_details.cv_document_id.data = app.private_details.cv_document_id or 0
        form.private_details.cover_letter_document_id.data = app.private_details.cover_letter_document_id or 0
    if form.validate_on_submit():
        if _save_application(form, app, is_new=False):
            db.session.commit()
            flash("Modifications enregistrées.", "success")
            return redirect(url_for(".detail", app_id=app.id))
        db.session.rollback()
        app = get_application(app_id)
    elif form.is_submitted():
        flash("Le formulaire contient des erreurs : vérifiez les champs signalés.", "danger")
    return render_template("applications/form.html", **_form_context(form, app))


# --- Fiche détaillée ---------------------------------------------------------------------

@bp.route("/<int:app_id>")
def detail(app_id):
    app = get_application(app_id)
    all_docs = Document.query.order_by(Document.category, Document.name).all()
    attached_ids = {link.document_id for link in app.document_links}
    by_category = {}
    for doc in all_docs:
        by_category.setdefault(doc.category, []).append(doc)

    checklist_rows = []
    for item in app.checklist_items:
        candidates = by_category.get(item.category, []) if item.category else []
        if item.done:
            state = "done"
        elif item.document_id:
            state = "attached"
        elif candidates:
            state = "available"
        else:
            state = "missing"
        checklist_rows.append({"item": item, "state": state, "candidates": candidates})

    attach_form = AttachDocumentForm()
    attach_form.document_id.choices = [
        (d.id, f"{d.category_label} — {d.display_name}") for d in all_docs if d.id not in attached_ids
    ]
    status_form = QuickStatusForm(status=app.status)
    status_form.status.choices = [(s.code, s.label) for s in Status.query.order_by(Status.position)]
    logs = ActivityLog.query.filter_by(application_id=app.id).order_by(ActivityLog.created_at.desc()).limit(30).all()
    return render_template(
        "applications/detail.html",
        app=app,
        checklist_rows=checklist_rows,
        all_docs=all_docs,
        attach_form=attach_form,
        checklist_form=ChecklistItemForm(),
        status_form=status_form,
        confirm_form=ConfirmForm(),
        logs=logs,
        tab=request.args.get("onglet", "apercu"),
    )


@bp.route("/<int:app_id>/statut", methods=["POST"])
def change_status(app_id):
    app = get_application(app_id)
    form = QuickStatusForm()
    form.status.choices = [(s.code, s.label) for s in Status.query.order_by(Status.position)]
    if not form.validate_on_submit():
        flash("Statut invalide.", "danger")
        return redirect(url_for(".detail", app_id=app.id))
    blocked = status_change_blocked(app, form.status.data)
    if blocked and not form.force_status.data:
        flash(blocked, "danger")
        return redirect(url_for(".detail", app_id=app.id, onglet="dossier"))
    new_obj = Status.query.filter_by(code=form.status.data).first()
    app.status = new_obj.code
    app.status_obj = new_obj
    if new_obj.kind == "sent" and not app.date_applied:
        app.date_applied = today_local()
        flash("Date d’envoi renseignée automatiquement (aujourd’hui).", "info")
    refresh_application(app)
    log_activity("status", f"Statut : {new_obj.label}" + (" (forcé, dossier incomplet)" if blocked else ""), app)
    db.session.commit()
    if blocked:
        flash("Statut forcé alors que des pièces obligatoires manquent.", "warning")
    else:
        flash(f"Statut mis à jour : {new_obj.label}.", "success")
    return redirect(url_for(".detail", app_id=app.id))


@bp.route("/<int:app_id>/dupliquer", methods=["POST"])
def duplicate(app_id):
    app = get_application(app_id)
    copy = duplicate_application(app)
    db.session.commit()
    flash("Candidature dupliquée. Vérifiez et adaptez la copie.", "success")
    return redirect(url_for(".edit", app_id=copy.id))


@bp.route("/<int:app_id>/archiver", methods=["POST"])
def toggle_archive(app_id):
    app = get_application(app_id)
    app.archived = not app.archived
    log_activity("archive", "Candidature archivée" if app.archived else "Candidature désarchivée", app)
    db.session.commit()
    flash("Candidature archivée." if app.archived else "Candidature restaurée depuis les archives.", "success")
    return redirect(safe_next(request.form.get("next"), url_for(".detail", app_id=app.id)))


@bp.route("/<int:app_id>/supprimer", methods=["POST"])
def delete(app_id):
    app = get_application(app_id)
    title = app.title
    log_activity("delete", f"Candidature supprimée : {title}")
    db.session.delete(app)
    db.session.commit()
    flash(f"Candidature « {title} » supprimée définitivement.", "success")
    return redirect(url_for(".index"))


# --- Checklist du dossier ------------------------------------------------------------------

def _touch(app):
    app.updated_at = utcnow()


@bp.route("/<int:app_id>/checklist", methods=["POST"])
def add_checklist_item(app_id):
    app = get_application(app_id)
    form = ChecklistItemForm()
    if form.validate_on_submit():
        position = max((i.position for i in app.checklist_items), default=-1) + 1
        app.checklist_items.append(ChecklistItem(
            label=form.label.data.strip(), category=form.category.data or None,
            required=form.required.data, position=position,
        ))
        _touch(app)
        db.session.commit()
        flash("Pièce ajoutée à la checklist.", "success")
    else:
        flash("Indiquez le nom de la pièce.", "danger")
    return redirect(url_for(".detail", app_id=app.id, onglet="dossier"))


@bp.route("/<int:app_id>/checklist/modele", methods=["POST"])
def apply_template(app_id):
    app = get_application(app_id)
    added = apply_checklist_template(app)
    _touch(app)
    db.session.commit()
    flash(f"{added} pièce(s) ajoutée(s) depuis le modèle." if added else "La checklist contient déjà toutes les pièces du modèle.",
          "success" if added else "info")
    return redirect(url_for(".detail", app_id=app.id, onglet="dossier"))


def _get_item(app, item_id) -> ChecklistItem:
    item = db.session.get(ChecklistItem, item_id)
    if item is None or item.application_id != app.id:
        abort(404)
    return item


@bp.route("/<int:app_id>/checklist/<int:item_id>/basculer", methods=["POST"])
def toggle_checklist_item(app_id, item_id):
    app = get_application(app_id)
    item = _get_item(app, item_id)
    field = request.form.get("field", "done")
    if field == "required":
        item.required = not item.required
    else:
        item.done = not item.done
        log_activity("checklist", f"Pièce « {item.label} » {'complétée' if item.done else 'marquée à faire'}", app)
    _touch(app)
    db.session.commit()
    return redirect(url_for(".detail", app_id=app.id, onglet="dossier"))


@bp.route("/<int:app_id>/checklist/<int:item_id>/lier", methods=["POST"])
def link_checklist_item(app_id, item_id):
    app = get_application(app_id)
    item = _get_item(app, item_id)
    doc_id = request.form.get("document_id", type=int) or 0
    if doc_id == 0:
        item.document_id = None
        flash("Document retiré de la pièce.", "info")
    else:
        doc = db.session.get(Document, doc_id) or abort(404)
        item.document_id = doc.id
        item.done = True
        if not any(link.document_id == doc.id for link in app.document_links):
            app.document_links.append(ApplicationDocument(document=doc, purpose=item.label))
        log_activity("checklist", f"Document « {doc.display_name} » associé à « {item.label} »", app)
        flash("Document associé ; la pièce est marquée comme complétée.", "success")
    _touch(app)
    db.session.commit()
    return redirect(url_for(".detail", app_id=app.id, onglet="dossier"))


@bp.route("/<int:app_id>/checklist/<int:item_id>/supprimer", methods=["POST"])
def delete_checklist_item(app_id, item_id):
    app = get_application(app_id)
    item = _get_item(app, item_id)
    app.checklist_items.remove(item)
    _touch(app)
    db.session.commit()
    flash("Pièce retirée de la checklist.", "success")
    return redirect(url_for(".detail", app_id=app.id, onglet="dossier"))


# --- Documents rattachés ----------------------------------------------------------------------

@bp.route("/<int:app_id>/documents", methods=["POST"])
def attach_document(app_id):
    app = get_application(app_id)
    form = AttachDocumentForm()
    form.document_id.choices = [(d.id, d.name) for d in Document.query.all()]
    if form.validate_on_submit():
        if any(link.document_id == form.document_id.data for link in app.document_links):
            flash("Ce document est déjà rattaché.", "info")
        else:
            doc = db.session.get(Document, form.document_id.data)
            app.document_links.append(ApplicationDocument(document=doc, purpose=_clean(form.purpose.data)))
            log_activity("document", f"Document rattaché : {doc.display_name}", app)
            _touch(app)
            db.session.commit()
            flash("Document rattaché.", "success")
    else:
        flash("Sélectionnez un document.", "danger")
    return redirect(url_for(".detail", app_id=app.id, onglet="dossier"))


@bp.route("/<int:app_id>/documents/<int:doc_id>/detacher", methods=["POST"])
def detach_document(app_id, doc_id):
    app = get_application(app_id)
    link = db.session.get(ApplicationDocument, (app.id, doc_id)) or abort(404)
    for item in app.checklist_items:
        if item.document_id == doc_id:
            item.document_id = None
    db.session.delete(link)
    log_activity("document", "Document détaché", app)
    _touch(app)
    db.session.commit()
    flash("Document détaché de la candidature (il reste dans la bibliothèque).", "success")
    return redirect(url_for(".detail", app_id=app.id, onglet="dossier"))
