from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from sqlalchemy import or_

from ..constants import DOCUMENT_CATEGORIES
from ..extensions import db
from ..forms import ConfirmForm, DocumentEditForm, DocumentForm, NewVersionForm
from ..models import ChecklistItem, Document, PrivateJobDetails
from ..services.document_service import delete_stored_file, save_upload, stored_path

bp = Blueprint("documents", __name__, url_prefix="/documents")


def _get(doc_id) -> Document:
    doc = db.session.get(Document, doc_id)
    if doc is None:
        abort(404)
    return doc


@bp.route("/")
def index():
    category = request.args.get("categorie")
    term = (request.args.get("q") or "").strip()
    query = Document.query
    if category in DOCUMENT_CATEGORIES:
        query = query.filter(Document.category == category)
    if term:
        like = f"%{term}%"
        query = query.filter(or_(Document.name.ilike(like), Document.notes.ilike(like),
                                 Document.original_filename.ilike(like)))
    docs = query.order_by(Document.category, Document.name, Document.uploaded_at.desc()).all()
    groups = {}
    for doc in docs:
        groups.setdefault(doc.category, []).append(doc)
    ordered = [(code, DOCUMENT_CATEGORIES[code], groups[code]) for code in DOCUMENT_CATEGORIES if code in groups]
    counts = dict(db.session.query(Document.category, db.func.count(Document.id)).group_by(Document.category).all())
    return render_template("documents/index.html", groups=ordered, counts=counts, category=category,
                           term=term, total=len(docs), confirm_form=ConfirmForm())


@bp.route("/ajouter", methods=["GET", "POST"])
def create():
    form = DocumentForm()
    if request.method == "GET" and request.args.get("categorie") in DOCUMENT_CATEGORIES:
        form.category.data = request.args["categorie"]
    if form.validate_on_submit():
        doc = Document(name=form.name.data.strip(), category=form.category.data, version=form.version.data.strip(),
                       notes=form.notes.data or None, expires_on=form.expires_on.data)
        if form.file.data and form.file.data.filename:
            try:
                for key, value in save_upload(form.file.data).items():
                    setattr(doc, key, value)
            except ValueError as exc:
                form.file.errors.append(str(exc))
                return render_template("documents/form.html", form=form, doc=None, mode="create")
        db.session.add(doc)
        db.session.commit()
        flash("Document ajouté à la bibliothèque.", "success")
        return redirect(url_for(".detail", doc_id=doc.id))
    return render_template("documents/form.html", form=form, doc=None, mode="create")


@bp.route("/<int:doc_id>")
def detail(doc_id):
    doc = _get(doc_id)
    versions = []
    current = doc
    seen = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        versions.append(current)
        current = current.previous_version
    return render_template("documents/detail.html", doc=doc, versions=versions,
                           newer=doc.newer_versions, confirm_form=ConfirmForm(),
                           file_missing=doc.has_file and stored_path(doc.stored_filename) is None)


@bp.route("/<int:doc_id>/modifier", methods=["GET", "POST"])
def edit(doc_id):
    doc = _get(doc_id)
    form = DocumentEditForm(obj=doc)
    if form.validate_on_submit():
        form.populate_obj(doc)
        doc.notes = doc.notes or None
        db.session.commit()
        flash("Document mis à jour.", "success")
        return redirect(url_for(".detail", doc_id=doc.id))
    return render_template("documents/form.html", form=form, doc=doc, mode="edit")


@bp.route("/<int:doc_id>/nouvelle-version", methods=["GET", "POST"])
def new_version(doc_id):
    previous = _get(doc_id)
    form = NewVersionForm()
    if request.method == "GET":
        form.version.data = _next_version(previous.version)
    if form.validate_on_submit():
        try:
            stored = save_upload(form.file.data)
        except ValueError as exc:
            form.file.errors.append(str(exc))
            return render_template("documents/form.html", form=form, doc=previous, mode="version")
        doc = Document(name=previous.name, category=previous.category, version=form.version.data.strip(),
                       notes=form.notes.data or None, expires_on=form.expires_on.data,
                       previous_version=previous, **stored)
        db.session.add(doc)
        db.session.commit()
        flash("Nouvelle version enregistrée. L’ancienne version est conservée.", "success")
        return redirect(url_for(".detail", doc_id=doc.id))
    return render_template("documents/form.html", form=form, doc=previous, mode="version")


def _next_version(version: str) -> str:
    try:
        return str(int(version) + 1)
    except (TypeError, ValueError):
        return f"{version}-2"


@bp.route("/<int:doc_id>/telecharger")
def download(doc_id):
    doc = _get(doc_id)
    path = stored_path(doc.stored_filename)
    if path is None:
        flash("Aucun fichier disponible pour ce document (ou fichier introuvable dans le dossier uploads).", "warning")
        return redirect(url_for(".detail", doc_id=doc.id))
    download_name = doc.original_filename or f"document.{doc.extension or 'bin'}"
    return send_file(path, mimetype=doc.mime_type or "application/octet-stream",
                     as_attachment=True, download_name=download_name, max_age=0)


@bp.route("/<int:doc_id>/supprimer", methods=["POST"])
def delete(doc_id):
    doc = _get(doc_id)
    name = doc.display_name
    ChecklistItem.query.filter_by(document_id=doc.id).update({"document_id": None})
    PrivateJobDetails.query.filter_by(cv_document_id=doc.id).update({"cv_document_id": None})
    PrivateJobDetails.query.filter_by(cover_letter_document_id=doc.id).update({"cover_letter_document_id": None})
    stored = doc.stored_filename
    db.session.delete(doc)
    db.session.commit()
    delete_stored_file(stored)
    flash(f"Document « {name} » supprimé.", "success")
    return redirect(url_for(".index"))
