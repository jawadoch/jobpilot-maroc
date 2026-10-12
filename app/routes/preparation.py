from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..constants import EXAM_KINDS, PREP_STATUSES, PRIORITIES
from ..extensions import db
from ..forms import ConfirmForm, LogTimeForm, PrepTopicForm, SubjectForm
from ..models import Application, ApplicationEvent, PrepSubject, PreparationTopic
from ..utils import safe_next, today_local

bp = Blueprint("preparation", __name__, url_prefix="/preparation")

VIEWS = {
    "": "Tous les sujets",
    "faibles": "Points faibles (confiance ≤ 2)",
    "examens": "Examens dans les 30 jours",
    "a_reviser": "Révisions dues",
    "prioritaires": "Priorité haute",
}


def _exam_application_ids(days=30):
    today = today_local()
    rows = (db.session.query(ApplicationEvent.application_id)
            .filter(ApplicationEvent.kind.in_(EXAM_KINDS), ApplicationEvent.done.is_(False),
                    ApplicationEvent.event_date >= today,
                    ApplicationEvent.event_date <= today + timedelta(days=days))
            .distinct().all())
    return {r[0] for r in rows}


def _progress(topics):
    total = len(topics)
    mastered = sum(1 for t in topics if t.status == "mastered")
    return {
        "total": total,
        "mastered": mastered,
        "percent": round(100 * mastered / total) if total else 0,
        "avg_confidence": round(sum(t.confidence for t in topics) / total, 1) if total else None,
        "minutes": sum(t.minutes_spent or 0 for t in topics),
        "weak": sum(1 for t in topics if t.is_weak),
    }


@bp.route("/")
def index():
    args = request.args
    view = args.get("vue", "")
    query = PreparationTopic.query.join(PrepSubject)
    if args.get("matiere", type=int):
        query = query.filter(PreparationTopic.subject_id == args.get("matiere", type=int))
    if args.get("groupe"):
        query = query.filter(PrepSubject.group == args["groupe"])
    if args.get("candidature", type=int):
        query = query.filter(PreparationTopic.application_id == args.get("candidature", type=int))
    if args.get("etat") in PREP_STATUSES:
        query = query.filter(PreparationTopic.status == args["etat"])
    if args.get("priorite") in ("1", "2", "3"):
        query = query.filter(PreparationTopic.priority == int(args["priorite"]))

    today = today_local()
    if view == "faibles":
        query = query.filter(PreparationTopic.confidence <= 2, PreparationTopic.status != "mastered")
    elif view == "examens":
        ids = _exam_application_ids()
        query = query.filter(PreparationTopic.application_id.in_(ids or {-1}))
    elif view == "a_reviser":
        query = query.filter(PreparationTopic.next_revision <= today, PreparationTopic.status != "mastered")
    elif view == "prioritaires":
        query = query.filter(PreparationTopic.priority == 3)

    topics = query.order_by(PreparationTopic.priority.desc(), PreparationTopic.confidence,
                            PreparationTopic.next_revision.is_(None), PreparationTopic.next_revision).all()

    all_topics = PreparationTopic.query.all()
    subjects = PrepSubject.query.order_by(PrepSubject.position, PrepSubject.name).all()
    groups = []
    for group in dict.fromkeys(s.group for s in subjects):
        group_topics = [t for t in all_topics if t.subject.group == group]
        groups.append((group, _progress(group_topics)))

    exam_events = (ApplicationEvent.query.join(Application)
                   .filter(ApplicationEvent.kind.in_(EXAM_KINDS), ApplicationEvent.done.is_(False),
                           ApplicationEvent.event_date >= today, Application.archived.is_(False))
                   .order_by(ApplicationEvent.event_date).limit(5).all())
    linked_apps = (Application.query.join(PreparationTopic).distinct().order_by(Application.title).all())
    return render_template(
        "preparation/index.html", topics=topics, overall=_progress(all_topics), groups=groups,
        subjects=subjects, views=VIEWS, view=view, args=args, statuses=PREP_STATUSES,
        priorities=PRIORITIES, exam_events=exam_events, linked_apps=linked_apps,
        log_form=LogTimeForm(), confirm_form=ConfirmForm(),
    )


def _prepare_form(form: PrepTopicForm):
    subjects = PrepSubject.query.order_by(PrepSubject.position, PrepSubject.name).all()
    form.subject_id.choices = [(s.id, f"{s.group} — {s.name}") for s in subjects]
    apps = Application.query.filter(Application.archived.is_(False)).order_by(Application.title).all()
    form.application_id.choices = [(0, "— Aucune (préparation générale) —")] + [
        (a.id, f"{a.title} — {a.organization}") for a in apps
    ]


def _save(form: PrepTopicForm, topic: PreparationTopic):
    form.populate_obj(topic)
    topic.application_id = topic.application_id or None
    topic.minutes_spent = topic.minutes_spent or 0
    topic.topic = topic.topic.strip()
    topic.exam_weight = (topic.exam_weight or "").strip() or None


@bp.route("/sujets/nouveau", methods=["GET", "POST"])
def create():
    form = PrepTopicForm()
    _prepare_form(form)
    if request.method == "GET":
        form.application_id.data = request.args.get("application_id", type=int) or 0
        if request.args.get("matiere", type=int):
            form.subject_id.data = request.args.get("matiere", type=int)
    if form.validate_on_submit():
        topic = PreparationTopic()
        _save(form, topic)
        db.session.add(topic)
        db.session.commit()
        flash("Sujet de révision ajouté.", "success")
        return redirect(url_for(".index"))
    return render_template("preparation/form.html", form=form, topic=None)


def _get(topic_id) -> PreparationTopic:
    topic = db.session.get(PreparationTopic, topic_id)
    if topic is None:
        abort(404)
    return topic


@bp.route("/sujets/<int:topic_id>/modifier", methods=["GET", "POST"])
def edit(topic_id):
    topic = _get(topic_id)
    form = PrepTopicForm(obj=topic)
    _prepare_form(form)
    if request.method == "GET":
        form.application_id.data = topic.application_id or 0
    if topic.application_id and topic.application_id not in {c[0] for c in form.application_id.choices}:
        form.application_id.choices.append((topic.application_id, topic.application.title))
    if form.validate_on_submit():
        _save(form, topic)
        db.session.commit()
        flash("Sujet mis à jour.", "success")
        return redirect(url_for(".index"))
    return render_template("preparation/form.html", form=form, topic=topic)


@bp.route("/sujets/<int:topic_id>/temps", methods=["POST"])
def log_time(topic_id):
    topic = _get(topic_id)
    form = LogTimeForm()
    if form.validate_on_submit():
        topic.minutes_spent = (topic.minutes_spent or 0) + form.minutes.data
        if form.confidence.data:
            topic.confidence = form.confidence.data
        if topic.status == "not_started":
            topic.status = "in_progress"
        db.session.commit()
        flash(f"{form.minutes.data} min ajoutées à « {topic.topic} ».", "success")
    else:
        flash("Durée invalide (1 à 1440 minutes).", "danger")
    return redirect(safe_next(request.form.get("next"), url_for(".index")))


@bp.route("/sujets/<int:topic_id>/supprimer", methods=["POST"])
def delete(topic_id):
    topic = _get(topic_id)
    db.session.delete(topic)
    db.session.commit()
    flash("Sujet supprimé.", "success")
    return redirect(url_for(".index"))


# --- Liste des matières (modifiable) ------------------------------------------------

@bp.route("/matieres", methods=["GET", "POST"])
def subjects():
    form = SubjectForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        if PrepSubject.query.filter(db.func.lower(PrepSubject.name) == name.lower()).first():
            flash("Cette matière existe déjà.", "warning")
        else:
            position = (db.session.query(db.func.max(PrepSubject.position)).scalar() or 0) + 1
            db.session.add(PrepSubject(name=name, group=form.group.data.strip(), position=position))
            db.session.commit()
            flash("Matière ajoutée.", "success")
        return redirect(url_for(".subjects"))
    subjects = PrepSubject.query.order_by(PrepSubject.position, PrepSubject.name).all()
    counts = dict(db.session.query(PreparationTopic.subject_id, db.func.count(PreparationTopic.id))
                  .group_by(PreparationTopic.subject_id).all())
    groups = list(dict.fromkeys(s.group for s in subjects))
    return render_template("preparation/subjects.html", form=form, subjects=subjects, counts=counts,
                           groups=groups, confirm_form=ConfirmForm())


@bp.route("/matieres/<int:subject_id>/modifier", methods=["POST"])
def rename_subject(subject_id):
    subject = db.session.get(PrepSubject, subject_id) or abort(404)
    name = (request.form.get("name") or "").strip()[:150]
    group = (request.form.get("group") or "").strip()[:150]
    if not name or not group:
        flash("Le nom et le groupe sont obligatoires.", "danger")
    elif PrepSubject.query.filter(db.func.lower(PrepSubject.name) == name.lower(), PrepSubject.id != subject.id).first():
        flash("Une autre matière porte déjà ce nom.", "warning")
    else:
        subject.name, subject.group = name, group
        db.session.commit()
        flash("Matière mise à jour.", "success")
    return redirect(url_for(".subjects"))


@bp.route("/matieres/<int:subject_id>/supprimer", methods=["POST"])
def delete_subject(subject_id):
    subject = db.session.get(PrepSubject, subject_id) or abort(404)
    if subject.topics:
        flash("Impossible de supprimer une matière qui contient des sujets de révision.", "danger")
    else:
        db.session.delete(subject)
        db.session.commit()
        flash("Matière supprimée.", "success")
    return redirect(url_for(".subjects"))
