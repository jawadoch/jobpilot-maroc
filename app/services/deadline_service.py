"""Échéances, agenda, niveaux d'alerte et synchronisation des événements automatiques."""
from dataclasses import dataclass, field
from datetime import date, time, timedelta

from markupsafe import Markup, escape
from sqlalchemy.orm import selectinload

from ..constants import EVENT_ICONS, EVENT_KINDS, EXAM_KINDS
from ..extensions import db
from ..models import Application, ApplicationEvent, Status
from ..utils import today_local

# --- Niveaux d'alerte ----------------------------------------------------------

LEVELS = {
    "overdue": ("En retard", "text-bg-danger", "bi-exclamation-octagon"),
    "today": ("Aujourd’hui", "text-bg-warning", "bi-alarm"),
    "soon3": ("≤ 3 jours", "bg-warning-subtle text-warning-emphasis border border-warning-subtle", "bi-hourglass-split"),
    "soon7": ("≤ 7 jours", "bg-info-subtle text-info-emphasis", "bi-hourglass"),
    "upcoming": ("À venir", "bg-light text-secondary border", "bi-calendar"),
    "done": ("Terminé", "bg-success-subtle text-success-emphasis", "bi-check2"),
}


def deadline_level(day: date | None, done: bool = False, today: date | None = None) -> str | None:
    if day is None:
        return None
    if done:
        return "done"
    today = today or today_local()
    delta = (day - today).days
    if delta < 0:
        return "overdue"
    if delta == 0:
        return "today"
    if delta <= 3:
        return "soon3"
    if delta <= 7:
        return "soon7"
    return "upcoming"


def deadline_badge(day, done=False, show_days=True) -> Markup:
    level = deadline_level(day, done)
    if level is None:
        return Markup("")
    label, css, icon = LEVELS[level]
    if show_days and level in ("soon3", "soon7", "upcoming"):
        days = (day - today_local()).days
        label = f"J-{days}"
    elif show_days and level == "overdue":
        label = f"En retard ({(today_local() - day).days} j)"
    return Markup(
        f'<span class="badge {css}" title="{escape(LEVELS[level][0])}">'
        f'<i class="bi {icon}" aria-hidden="true"></i> {escape(label)}</span>'
    )


# --- Agenda --------------------------------------------------------------------

@dataclass
class AgendaItem:
    day: date
    time: time | None
    kind: str
    title: str
    application: Application
    event: ApplicationEvent | None = None
    done: bool = False
    location: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def kind_label(self):
        if self.kind == "action":
            return "Prochaine action"
        if self.kind == "dossier":
            return "Dossier incomplet"
        return EVENT_KINDS.get(self.kind, "Autre")

    @property
    def icon(self):
        return EVENT_ICONS.get(self.kind, "bi-calendar-event")

    @property
    def level(self):
        return deadline_level(self.day, self.done)

    @property
    def is_exam(self):
        return self.kind in EXAM_KINDS

    @property
    def sort_key(self):
        return (self.day, self.time or time(23, 59), self.application.id)


def _application_query(active_only: bool, include_archived: bool):
    query = Application.query.options(
        selectinload(Application.events),
        selectinload(Application.checklist_items),
    )
    if not include_archived:
        query = query.filter(Application.archived.is_(False))
    apps = query.all()
    if active_only:
        apps = [a for a in apps if a.is_active]
    return apps


def collect_agenda(start: date | None = None, end: date | None = None, *, include_done=True,
                   active_only=False, include_archived=False, kinds=None, sector=None,
                   include_actions=True, applications=None) -> list[AgendaItem]:
    """Rassemble événements + prochaines actions, triés par date."""
    apps = applications if applications is not None else _application_query(active_only, include_archived)
    items: list[AgendaItem] = []
    for app in apps:
        if sector and app.sector != sector:
            continue
        for ev in app.events:
            if not include_done and ev.done:
                continue
            items.append(AgendaItem(ev.event_date, ev.event_time, ev.kind, ev.display_title, app,
                                    event=ev, done=ev.done, location=ev.location))
        if include_actions and app.next_action_due and app.next_action:
            items.append(AgendaItem(app.next_action_due, None, "action", app.next_action, app,
                                    done=False))
    if kinds:
        items = [i for i in items if i.kind in kinds]
    if start:
        items = [i for i in items if i.day >= start]
    if end:
        items = [i for i in items if i.day <= end]
    items.sort(key=lambda i: i.sort_key)
    return items


def urgent_items(days: int = 3, dossier_window: int = 14, applications=None) -> list[AgendaItem]:
    """Actions en retard, du jour ou proches + dossiers incomplets avant une date limite."""
    today = today_local()
    apps = applications if applications is not None else _application_query(True, False)
    items = collect_agenda(end=today + timedelta(days=days), include_done=False, applications=apps)
    for app in apps:
        if not app.status_obj or app.status_obj.kind != "preparation":
            continue
        summary = app.checklist_summary
        if not summary["missing"]:
            continue
        deadline = next((e for e in app.pending_events if e.kind == "deadline"), None)
        if deadline is None or deadline.event_date > today + timedelta(days=dossier_window):
            continue
        n = len(summary["missing"])
        items.append(AgendaItem(
            deadline.event_date, deadline.event_time, "dossier",
            f"{n} pièce{'s' if n > 1 else ''} obligatoire{'s' if n > 1 else ''} manquante{'s' if n > 1 else ''} : "
            + ", ".join(i.label for i in summary["missing"][:3]) + ("…" if n > 3 else ""),
            app,
        ))
    items.sort(key=lambda i: i.sort_key)
    return items


def group_by_day(items: list[AgendaItem]):
    groups: dict[date, list[AgendaItem]] = {}
    for item in items:
        groups.setdefault(item.day, []).append(item)
    return list(groups.items())


# --- Événements automatiques -----------------------------------------------------

def _auto_specs(app: Application):
    """(auto_key, kind, titre, date, heure) des événements tirés de la fiche."""
    specs = []
    if app.sector == "public" and app.public_details:
        d = app.public_details
        specs += [
            ("public_deadline", "deadline", "Date limite de dépôt du dossier", d.deadline_date, d.deadline_time),
            ("public_shortlist", "shortlist", "Publication de la liste des présélectionnés", d.shortlist_date, None),
            ("public_results", "results", "Publication des résultats", d.results_date, None),
        ]
    if app.sector == "private" and app.private_details:
        p = app.private_details
        specs += [
            ("private_assessment", "test", "Test technique à rendre",
             p.tech_assessment_date if p.tech_assessment_required or p.tech_assessment_date else None,
             p.tech_assessment_time),
            ("private_followup", "followup", "Relancer le recruteur", p.follow_up_date, None),
        ]
    return specs


def sync_auto_events(app: Application):
    """Crée / met à jour / supprime les événements dérivés des champs de la fiche."""
    specs = _auto_specs(app)
    wanted = {key for key, *_ in specs}
    by_key = {ev.auto_key: ev for ev in app.events if ev.auto_key}

    for key, kind, title, day, at in specs:
        ev = by_key.get(key)
        if day is None:
            if ev is not None:
                app.events.remove(ev)
            continue
        if ev is None:
            ev = ApplicationEvent(auto_key=key, kind=kind, title=title, event_date=day, event_time=at)
            app.events.append(ev)
        else:
            if ev.event_date != day or ev.event_time != at:
                ev.done = False
            ev.event_date, ev.event_time = day, at

    for key, ev in by_key.items():
        if key not in wanted and ev in app.events:
            app.events.remove(ev)

    # Une fois la candidature envoyée, la date limite de dépôt est considérée comme traitée
    if app.status_obj and app.status_obj.kind not in ("preparation",):
        for ev in app.events:
            if ev.auto_key == "public_deadline":
                ev.done = True
    # Résultat du concours connu → publication des résultats traitée
    if app.sector == "public" and app.public_details and app.public_details.result in ("admitted", "failed", "waiting"):
        for ev in app.events:
            if ev.auto_key == "public_results":
                ev.done = True


def refresh_next_due(app: Application):
    candidates = [ev.event_date for ev in app.events if not ev.done]
    if app.next_action_due and app.next_action:
        candidates.append(app.next_action_due)
    app.next_due_date = min(candidates) if candidates else None


def refresh_application(app: Application):
    """À appeler après toute modification d'une candidature ou de ses événements."""
    if app.status and (app.status_obj is None or app.status_obj.code != app.status):
        app.status_obj = Status.query.filter_by(code=app.status).first()
    db.session.flush()
    sync_auto_events(app)
    refresh_next_due(app)
