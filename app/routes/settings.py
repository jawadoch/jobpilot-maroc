import re
import tempfile
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for

from ..constants import STATUS_KINDS
from ..extensions import db
from ..forms import ConfirmForm, ProfileForm, RestoreForm, StatusForm, TemplateItemForm
from ..models import Application, ChecklistTemplateItem, Status, log_activity
from ..services import backup_service
from ..services.application_service import normalize
from ..services.seed_service import has_demo_data, purge_demo, seed_demo
from ..services.setup_service import get_profile, init_database
from ..utils import now_local

bp = Blueprint("settings", __name__, url_prefix="/parametres")


@bp.route("/", methods=["GET", "POST"])
def profile():
    profile = get_profile()
    form = ProfileForm(obj=profile)
    if form.validate_on_submit():
        form.populate_obj(profile)
        for field in form:
            if field.name != "csrf_token" and isinstance(getattr(profile, field.name, None), str):
                setattr(profile, field.name, getattr(profile, field.name).strip() or None)
        profile.full_name = profile.full_name or "—"
        db.session.commit()
        flash("Profil enregistré.", "success")
        return redirect(url_for(".profile"))
    return render_template("settings/profile.html", form=form, profile=profile)


# --- Statuts --------------------------------------------------------------------------

@bp.route("/statuts", methods=["GET", "POST"])
def statuses():
    form = StatusForm()
    if form.validate_on_submit():
        base = re.sub(r"[^a-z0-9]+", "_", normalize(form.label.data)).strip("_")[:30] or "statut"
        code, n = base, 2
        while Status.query.filter_by(code=code).first():
            code, n = f"{base}_{n}", n + 1
        db.session.add(Status(code=code, label=form.label.data.strip(), kind=form.kind.data,
                              position=form.position.data or 0,
                              requires_complete_dossier=form.requires_complete_dossier.data))
        db.session.commit()
        flash("Statut ajouté.", "success")
        return redirect(url_for(".statuses"))
    items = Status.query.order_by(Status.position, Status.id).all()
    usage = dict(db.session.query(Application.status, db.func.count(Application.id)).group_by(Application.status).all())
    if request.method == "GET":
        form.position.data = (max((s.position for s in items), default=0) + 1)
    return render_template("settings/statuses.html", form=form, items=items, usage=usage,
                           kinds=STATUS_KINDS, confirm_form=ConfirmForm())


@bp.route("/statuts/<int:status_id>", methods=["POST"])
def update_status(status_id):
    status = db.session.get(Status, status_id) or abort(404)
    form = StatusForm()
    if form.validate_on_submit():
        status.label = form.label.data.strip()
        status.kind = form.kind.data
        status.position = form.position.data or 0
        status.requires_complete_dossier = form.requires_complete_dossier.data
        db.session.commit()
        flash(f"Statut « {status.label} » mis à jour.", "success")
    else:
        flash("Données invalides pour le statut.", "danger")
    return redirect(url_for(".statuses"))


@bp.route("/statuts/<int:status_id>/supprimer", methods=["POST"])
def delete_status(status_id):
    status = db.session.get(Status, status_id) or abort(404)
    used = Application.query.filter_by(status=status.code).count()
    if used:
        flash(f"Impossible : {used} candidature(s) utilisent ce statut. Changez-les d’abord.", "danger")
    elif Status.query.count() <= 1:
        flash("Il doit rester au moins un statut.", "danger")
    else:
        db.session.delete(status)
        db.session.commit()
        flash("Statut supprimé.", "success")
    return redirect(url_for(".statuses"))


# --- Modèle de checklist -------------------------------------------------------------------

@bp.route("/checklist-modele", methods=["GET", "POST"])
def checklist_template():
    form = TemplateItemForm()
    if form.validate_on_submit():
        position = (db.session.query(db.func.max(ChecklistTemplateItem.position)).scalar() or 0) + 1
        db.session.add(ChecklistTemplateItem(label=form.label.data.strip(), category=form.category.data or None,
                                             required=form.required.data, position=position))
        db.session.commit()
        flash("Pièce ajoutée au modèle.", "success")
        return redirect(url_for(".checklist_template"))
    items = ChecklistTemplateItem.query.order_by(ChecklistTemplateItem.position).all()
    return render_template("settings/checklist_template.html", form=form, items=items, confirm_form=ConfirmForm())


@bp.route("/checklist-modele/<int:item_id>/basculer", methods=["POST"])
def toggle_template_item(item_id):
    item = db.session.get(ChecklistTemplateItem, item_id) or abort(404)
    item.required = not item.required
    db.session.commit()
    return redirect(url_for(".checklist_template"))


@bp.route("/checklist-modele/<int:item_id>/supprimer", methods=["POST"])
def delete_template_item(item_id):
    item = db.session.get(ChecklistTemplateItem, item_id) or abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Pièce retirée du modèle (les checklists existantes ne sont pas modifiées).", "success")
    return redirect(url_for(".checklist_template"))


# --- Sauvegarde / restauration --------------------------------------------------------------

@bp.route("/sauvegarde")
def backup():
    backups = backup_service.list_backups()
    return render_template("settings/backup.html", backups=backups, restore_form=RestoreForm(),
                           confirm_form=ConfirmForm(),
                           db_path=current_app.config["DATABASE_PATH"],
                           upload_path=current_app.config["UPLOAD_FOLDER"],
                           backup_path=current_app.config["BACKUP_FOLDER"])


@bp.route("/sauvegarde/creer", methods=["POST"])
def create_backup():
    path = backup_service.create_backup("manuelle")
    return send_file(path, as_attachment=True, download_name=path.name, mimetype="application/x-sqlite3")


@bp.route("/sauvegarde/<name>")
def download_backup(name):
    path = backup_service.resolve_backup(name)
    if path is None:
        abort(404)
    return send_file(path, as_attachment=True, download_name=path.name, mimetype="application/x-sqlite3")


@bp.route("/sauvegarde/documents.zip")
def download_uploads():
    archive = backup_service.uploads_zip()
    name = f"jobpilot-documents-{now_local():%Y%m%d-%H%M%S}.zip"
    return send_file(archive, as_attachment=True, download_name=name, mimetype="application/zip")


@bp.route("/sauvegarde/restaurer", methods=["POST"])
def restore():
    form = RestoreForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error, "danger")
        return redirect(url_for(".backup"))
    with tempfile.TemporaryDirectory() as tmp:
        uploaded = Path(tmp) / "restore.db"
        form.file.data.save(uploaded)
        try:
            safety = backup_service.restore_backup(uploaded)
        except ValueError as exc:
            flash(f"Restauration annulée : {exc} La base actuelle n’a pas été modifiée.", "danger")
            return redirect(url_for(".backup"))
    init_database()
    log_activity("restore", f"Base restaurée depuis une sauvegarde (copie de sécurité : {safety.name})")
    db.session.commit()
    flash(f"Base restaurée. L’ancienne base a été sauvegardée sous « {safety.name} ». "
          "Pensez à restaurer aussi le dossier uploads si nécessaire.", "success")
    return redirect(url_for(".backup"))


# --- Données d'exemple ------------------------------------------------------------------

@bp.route("/donnees-exemple")
def demo():
    return render_template("settings/demo.html", has_demo=has_demo_data(), confirm_form=ConfirmForm())


@bp.route("/donnees-exemple/ajouter", methods=["POST"])
def demo_seed():
    count = seed_demo()
    flash(f"{count} candidatures d’exemple (fictives) ajoutées." if count
          else "Les données d’exemple sont déjà présentes.", "success" if count else "info")
    return redirect(url_for(".demo"))


@bp.route("/donnees-exemple/supprimer", methods=["POST"])
def demo_purge():
    result = purge_demo()
    flash(f"Données d’exemple supprimées : {result['applications']} candidature(s), "
          f"{result['documents']} document(s), {result['topics']} sujet(s). Vos données réelles sont intactes.", "success")
    return redirect(url_for(".demo"))
