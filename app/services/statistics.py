"""Statistiques calculées à partir des enregistrements réels.

Définitions (affichées aussi dans l'interface) :
- Candidature « envoyée » : statut de type envoyée, réponse, offre, acceptée, refus
  ou sans réponse/clôturée (les candidatures retirées et celles encore en
  préparation sont exclues).
- Taux de réponse = candidatures ayant reçu une suite (présélection, convocation,
  test, entretien, liste d’attente, offre, acceptation ou refus) ÷ candidatures envoyées.
"""
from collections import Counter, OrderedDict
from datetime import timedelta

from sqlalchemy.orm import selectinload

from ..constants import (
    CATEGORIES,
    COMPETITION_RESULTS,
    EXAM_KINDS,
    MONTHS_FR_SHORT,
    PREP_STATUSES,
    RESPONSE_KINDS,
    SECTORS,
    SUBMITTED_KINDS,
)
from ..models import Application, PreparationTopic, Status
from ..utils import today_local


def _rate(numerator: int, denominator: int):
    return round(100 * numerator / denominator, 1) if denominator else None


def _kind(app):
    return app.status_obj.kind if app.status_obj else "preparation"


def response_rate(apps):
    submitted = [a for a in apps if _kind(a) in SUBMITTED_KINDS]
    responded = [a for a in submitted if _kind(a) in RESPONSE_KINDS]
    return {"submitted": len(submitted), "responded": len(responded),
            "rate": _rate(len(responded), len(submitted))}


def last_months(n=12, today=None):
    today = today or today_local()
    year, month = today.year, today.month
    months = []
    for _ in range(n):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


def load_applications():
    return Application.query.options(
        selectinload(Application.events),
        selectinload(Application.checklist_items),
        selectinload(Application.public_details),
    ).all()


def dashboard_stats(apps=None):
    apps = load_applications() if apps is None else apps
    today = today_local()
    horizon = today + timedelta(days=30)
    live = [a for a in apps if a.is_active]

    upcoming_deadlines = sum(
        1 for a in live for e in a.events
        if e.kind == "deadline" and not e.done and today <= e.event_date <= horizon
    )
    upcoming_exams = sum(
        1 for a in live for e in a.events
        if e.kind in EXAM_KINDS and not e.done and today <= e.event_date <= horizon
    )
    rr = response_rate(apps)
    return {
        "total": len(apps),
        "archived": sum(1 for a in apps if a.archived),
        "active": len(live),
        "public": sum(1 for a in apps if a.sector == "public"),
        "private": sum(1 for a in apps if a.sector == "private"),
        "upcoming_deadlines": upcoming_deadlines,
        "upcoming_exams": upcoming_exams,
        "offers": sum(1 for a in apps if _kind(a) in ("offer", "accepted")),
        "rejections": sum(1 for a in apps if _kind(a) == "rejected"),
        "response": rr,
    }


def chart_data(apps=None):
    apps = load_applications() if apps is None else apps
    statuses = Status.query.order_by(Status.position).all()
    status_counts = Counter(a.status for a in apps)

    months = last_months(12)
    monthly = OrderedDict(((y, m), {"public": 0, "private": 0}) for y, m in months)
    for a in apps:
        if a.date_applied:
            key = (a.date_applied.year, a.date_applied.month)
            if key in monthly:
                monthly[key][a.sector] += 1

    by_sector_rate = {}
    for sector in SECTORS:
        by_sector_rate[sector] = response_rate([a for a in apps if a.sector == sector])

    return {
        "sector": {
            "labels": [SECTORS["public"], SECTORS["private"]],
            "values": [sum(1 for a in apps if a.sector == s) for s in ("public", "private")],
        },
        "status": {
            "labels": [s.label for s in statuses if status_counts.get(s.code)],
            "values": [status_counts[s.code] for s in statuses if status_counts.get(s.code)],
        },
        "monthly": {
            "labels": [f"{MONTHS_FR_SHORT[m - 1]} {str(y)[2:]}" for y, m in months],
            "public": [v["public"] for v in monthly.values()],
            "private": [v["private"] for v in monthly.values()],
        },
        "response": {
            "labels": [SECTORS["public"], SECTORS["private"]],
            "rates": [by_sector_rate[s]["rate"] for s in ("public", "private")],
            "submitted": [by_sector_rate[s]["submitted"] for s in ("public", "private")],
            "responded": [by_sector_rate[s]["responded"] for s in ("public", "private")],
        },
    }


def detailed_stats():
    apps = load_applications()
    statuses = Status.query.order_by(Status.position).all()
    status_counts = Counter(a.status for a in apps)
    category_counts = Counter(a.category for a in apps)
    city_counts = Counter((a.city or "Non précisée") for a in apps)
    source_counts = Counter((a.source or "Non précisée") for a in apps)
    results = Counter(
        a.public_details.result for a in apps if a.sector == "public" and a.public_details
    )
    topics = PreparationTopic.query.all()
    prep_counts = Counter(t.status for t in topics)
    return {
        "dashboard": dashboard_stats(apps),
        "charts": chart_data(apps),
        "by_status": [(s, status_counts.get(s.code, 0)) for s in statuses],
        "by_category": [(CATEGORIES[k], category_counts.get(k, 0)) for k in CATEGORIES if category_counts.get(k)],
        "by_city": city_counts.most_common(10),
        "by_source": source_counts.most_common(10),
        "competition_results": [(COMPETITION_RESULTS[k], results.get(k, 0)) for k in COMPETITION_RESULTS],
        "response_by_sector": {s: response_rate([a for a in apps if a.sector == s]) for s in SECTORS},
        "prep": {
            "total": len(topics),
            "by_status": [(PREP_STATUSES[k], prep_counts.get(k, 0)) for k in PREP_STATUSES],
            "minutes": sum(t.minutes_spent or 0 for t in topics),
            "avg_confidence": round(sum(t.confidence for t in topics) / len(topics), 1) if topics else None,
        },
    }
