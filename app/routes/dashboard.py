from datetime import timedelta

from flask import Blueprint, render_template

from ..models import ActivityLog, Application
from ..services import statistics
from ..services.deadline_service import collect_agenda, urgent_items
from ..utils import today_local

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    apps = statistics.load_applications()
    active = [a for a in apps if a.is_active]
    today = today_local()
    stats = statistics.dashboard_stats(apps)
    urgent = urgent_items(applications=active)
    # Événements uniquement : les « prochaines actions » figurent déjà dans les actions urgentes
    upcoming = collect_agenda(today, today + timedelta(days=30), include_done=False, applications=active,
                              include_actions=False)
    upcoming_7 = [i for i in upcoming if i.day <= today + timedelta(days=7)]
    upcoming_30 = [i for i in upcoming if i.day > today + timedelta(days=7)]
    stats["requiring_action"] = len({i.application.id for i in urgent})
    recent_apps = (Application.query.order_by(Application.updated_at.desc()).limit(8).all())
    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(8).all()
    return render_template(
        "dashboard/index.html",
        stats=stats,
        urgent=urgent,
        upcoming_7=upcoming_7,
        upcoming_30=upcoming_30,
        recent_apps=recent_apps,
        recent_logs=recent_logs,
        charts=statistics.chart_data(apps),
    )


@bp.route("/statistiques")
def stats():
    return render_template("dashboard/stats.html", s=statistics.detailed_stats())
