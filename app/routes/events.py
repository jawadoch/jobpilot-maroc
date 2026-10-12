import calendar
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..constants import EVENT_KINDS, EXAM_KINDS, MONTHS_FR, WEEKDAYS_FR_SHORT
from ..extensions import db
from ..forms import ConfirmForm, EventForm
from ..models import Application, ApplicationEvent, log_activity
from ..services.deadline_service import collect_agenda, group_by_day, refresh_application
from ..utils import parse_date, safe_next, today_local

bp = Blueprint("events", __name__, url_prefix="/calendrier")

RANGES = {
    "upcoming": "À venir (et en retard)",
    "7": "7 prochains jours",
    "30": "30 prochains jours",
    "past": "Passés",
    "all": "Tout",
}


@bp.route("/")
def agenda():
    view = request.args.get("vue", "liste")
    today = today_local()
    kind = request.args.get("type")
    kinds = None
    if kind == "exams":
        kinds = EXAM_KINDS
    elif kind in EVENT_KINDS or kind == "action":
        kinds = {kind}
    sector = request.args.get("secteur") if request.args.get("secteur") in ("public", "private") else None
    include_closed = request.args.get("cloturees") == "1"
    common = dict(kinds=kinds, sector=sector, active_only=not include_closed)
    ctx = dict(view=view, kind=kind, sector=sector, include_closed=include_closed,
               event_kinds=EVENT_KINDS, confirm_form=ConfirmForm())

    if view == "semaine":
        ref = parse_date(request.args.get("date")) or today
        start = ref - timedelta(days=ref.weekday())
        days = [start + timedelta(days=i) for i in range(7)]
        items = collect_agenda(start, days[-1], **common)
        ctx.update(days=days, by_day=dict(group_by_day(items)), prev=start - timedelta(days=7),
                   next=start + timedelta(days=7), weekdays=WEEKDAYS_FR_SHORT)
        return render_template("events/week.html", **ctx)

    if view == "mois":
        ref = parse_date(request.args.get("date")) or today
        first = ref.replace(day=1)
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month)
        items = collect_agenda(weeks[0][0], weeks[-1][-1], **common)
        prev_month = (first - timedelta(days=1)).replace(day=1)
        next_month = (first + timedelta(days=32)).replace(day=1)
        ctx.update(weeks=weeks, by_day=dict(group_by_day(items)), month=first,
                   month_label=f"{MONTHS_FR[first.month - 1].capitalize()} {first.year}",
                   prev=prev_month, next=next_month, weekdays=WEEKDAYS_FR_SHORT)
        return render_template("events/month.html", **ctx)

    rng = request.args.get("periode", "upcoming")
    if rng == "7":
        items = collect_agenda(None, today + timedelta(days=7), include_done=False, **common)
    elif rng == "30":
        items = collect_agenda(None, today + timedelta(days=30), include_done=False, **common)
    elif rng == "past":
        items = list(reversed(collect_agenda(None, today - timedelta(days=1), **common)))
    elif rng == "all":
        items = collect_agenda(**common)
    else:
        rng = "upcoming"
        items = collect_agenda(include_done=False, **common)
    ctx.update(groups=group_by_day(items), rng=rng, ranges=RANGES, count=len(items))
    return render_template("events/agenda.html", **ctx)


@bp.route("/entretiens-examens")
def exams():
    today = today_local()
    upcoming = collect_agenda(include_done=False, kinds=EXAM_KINDS, include_actions=False)
    past = [i for i in collect_agenda(None, today, kinds=EXAM_KINDS, include_actions=False,
                                      include_archived=True)
            if i.done or i.day < today]
    past.reverse()
    return render_template("events/exams.html", upcoming=upcoming, past=past[:50], confirm_form=ConfirmForm())


def _application_choices():
    apps = Application.query.filter(Application.archived.is_(False)).order_by(Application.title).all()
    return [(a.id, f"{a.title} — {a.organization}") for a in apps]


def _redirect_after(event_or_app_id):
    target = request.form.get("next") or request.args.get("next")
    return redirect(safe_next(target, url_for("applications.detail", app_id=event_or_app_id, onglet="etapes")))


@bp.route("/evenements/nouveau", methods=["GET", "POST"])
def create():
    form = EventForm()
    form.application_id.choices = _application_choices()
    if request.method == "GET":
        form.application_id.data = request.args.get("application_id", type=int)
        if request.args.get("type") in EVENT_KINDS:
            form.kind.data = request.args["type"]
    if form.validate_on_submit():
        app = db.session.get(Application, form.application_id.data) or abort(404)
        event = ApplicationEvent()
        form.populate_obj(event)
        event.title = (event.title or "").strip() or None
        app.events.append(event)
        refresh_application(app)
        log_activity("event", f"Étape ajoutée : {event.display_title} ({event.event_date:%d/%m/%Y})", app)
        db.session.commit()
        flash("Étape ajoutée au calendrier.", "success")
        return _redirect_after(app.id)
    return render_template("events/form.html", form=form, event=None)


def _get_event(event_id) -> ApplicationEvent:
    event = db.session.get(ApplicationEvent, event_id)
    if event is None:
        abort(404)
    return event


@bp.route("/evenements/<int:event_id>/modifier", methods=["GET", "POST"])
def edit(event_id):
    event = _get_event(event_id)
    form = EventForm(obj=event)
    form.application_id.choices = _application_choices()
    if event.application_id not in {c[0] for c in form.application_id.choices}:
        form.application_id.choices.append((event.application_id, event.application.title))
    if event.auto_key:
        # date / type / candidature pilotés par la fiche candidature
        form.application_id.data = event.application_id
        form.kind.data = event.kind
        form.event_date.data = event.event_date
        form.event_time.data = event.event_time
    if form.validate_on_submit():
        app = event.application
        if event.auto_key:
            event.location = form.location.data or None
            event.details = form.details.data or None
            event.done = form.done.data
            event.outcome = form.outcome.data or None
        else:
            new_app = db.session.get(Application, form.application_id.data) or abort(404)
            form.populate_obj(event)
            event.title = (event.title or "").strip() or None
            if new_app.id != app.id:
                event.application = new_app
                refresh_application(new_app)
        refresh_application(app)
        log_activity("event", f"Étape modifiée : {event.display_title}", event.application)
        db.session.commit()
        flash("Étape mise à jour.", "success")
        return _redirect_after(event.application_id)
    return render_template("events/form.html", form=form, event=event)


@bp.route("/evenements/<int:event_id>/terminer", methods=["POST"])
def toggle_done(event_id):
    event = _get_event(event_id)
    event.done = not event.done
    refresh_application(event.application)
    log_activity("event", f"Étape « {event.display_title} » {'terminée' if event.done else 'rouverte'}", event.application)
    db.session.commit()
    flash("Étape marquée comme terminée." if event.done else "Étape rouverte.", "success")
    return _redirect_after(event.application_id)


@bp.route("/evenements/<int:event_id>/supprimer", methods=["POST"])
def delete(event_id):
    event = _get_event(event_id)
    app = event.application
    if event.auto_key:
        flash("Cette échéance provient de la fiche candidature : effacez la date correspondante dans la fiche pour la retirer.", "warning")
        return _redirect_after(app.id)
    app.events.remove(event)
    refresh_application(app)
    log_activity("event", f"Étape supprimée : {event.display_title}", app)
    db.session.commit()
    flash("Étape supprimée.", "success")
    return _redirect_after(app.id)
