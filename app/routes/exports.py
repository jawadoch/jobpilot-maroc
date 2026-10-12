from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from sqlalchemy.orm import selectinload

from ..forms import ImportConfirmForm, ImportForm
from ..models import Application
from ..services import data_service
from ..utils import now_local
from .applications import build_query

bp = Blueprint("exports", __name__, url_prefix="/donnees")


def _download(content: bytes, filename: str, mimetype: str) -> Response:
    return Response(content, mimetype=mimetype,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _filtered_applications():
    """Respecte les filtres de la liste ; inclut les archives si archived=all."""
    args = request.args.to_dict()
    sector = args.pop("vue_secteur", None)
    return build_query(args, sector if sector in ("public", "private") else None).options(
        selectinload(Application.events), selectinload(Application.document_links),
    ).all()


@bp.route("/")
def index():
    return render_template("exports/index.html", import_form=ImportForm(),
                           total=Application.query.count())


@bp.route("/candidatures.csv")
def export_csv():
    stamp = f"{now_local():%Y%m%d-%H%M}"
    return _download(data_service.export_csv(_filtered_applications()),
                     f"jobpilot-candidatures-{stamp}.csv", "text/csv; charset=utf-8")


@bp.route("/candidatures.json")
def export_json():
    stamp = f"{now_local():%Y%m%d-%H%M}"
    return _download(data_service.export_json(_filtered_applications()),
                     f"jobpilot-candidatures-{stamp}.json", "application/json; charset=utf-8")


@bp.route("/export-complet.json")
def export_full_json():
    stamp = f"{now_local():%Y%m%d-%H%M}"
    apps = Application.query.order_by(Application.id).all()
    return _download(data_service.export_json(apps, full=True),
                     f"jobpilot-export-complet-{stamp}.json", "application/json; charset=utf-8")


@bp.route("/modele-import.csv")
def import_template():
    return _download(data_service.import_template_csv(), "jobpilot-modele-import.csv", "text/csv; charset=utf-8")


@bp.route("/import", methods=["POST"])
def import_preview():
    form = ImportForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error, "danger")
        return redirect(url_for(".index"))
    try:
        preview = data_service.parse_import_csv(form.file.data.read())
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for(".index"))
    if not preview["rows"]:
        flash("Aucune ligne de données trouvée dans le fichier.", "warning")
        return redirect(url_for(".index"))
    token = data_service.store_preview(preview)
    return render_template("exports/preview.html", preview=preview, confirm_form=ImportConfirmForm(token=token))


@bp.route("/import/confirmer", methods=["POST"])
def import_confirm():
    form = ImportConfirmForm()
    if not form.validate_on_submit():
        flash("Confirmation invalide.", "danger")
        return redirect(url_for(".index"))
    preview = data_service.load_preview(form.token.data)
    if preview is None:
        flash("Aperçu expiré ou introuvable : importez à nouveau le fichier.", "warning")
        return redirect(url_for(".index"))
    if request.form.get("action") == "annuler":
        data_service.discard_preview(form.token.data)
        flash("Import annulé : aucune donnée n’a été ajoutée.", "info")
        return redirect(url_for(".index"))
    created, skipped = data_service.commit_import(preview)
    data_service.discard_preview(form.token.data)
    flash(f"Import terminé : {created} candidature(s) créée(s), {skipped} ligne(s) ignorée(s) "
          "(erreurs ou doublons).", "success")
    return redirect(url_for("applications.index", sort="created"))
