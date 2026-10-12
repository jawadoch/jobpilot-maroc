from datetime import date, timedelta

from app.extensions import db
from app.models import ActivityLog, Application, ApplicationEvent, PreparationTopic, PrepSubject
from app.utils import today_local

from .conftest import private_payload, public_payload


def get_app(title):
    return Application.query.filter_by(title=title).one()


def test_pages_render_on_empty_database(client):
    for url in ["/", "/statistiques", "/candidatures/", "/candidatures/concours-publics",
                "/candidatures/secteur-prive", "/calendrier/", "/calendrier/?vue=semaine",
                "/calendrier/?vue=mois", "/calendrier/entretiens-examens", "/documents/",
                "/preparation/", "/parametres/", "/parametres/sauvegarde", "/donnees/"]:
        response = client.get(url)
        assert response.status_code == 200, url
        assert "lang=\"fr\"" in response.get_data(as_text=True)


def test_create_public_application_with_details_checklist_and_deadline_event(client, ctx):
    response = client.post("/candidatures/nouvelle", data=public_payload(), follow_redirects=True)
    assert response.status_code == 200
    assert "Candidature créée" in response.get_data(as_text=True)

    app = get_app("Ingénieur d’État — Informatique")
    assert app.public_details.competition_code == "CODE-1"
    assert app.public_details.scale == "Échelle 11"
    # le modèle de checklist est appliqué aux nouveaux concours
    assert len(app.checklist_items) >= 5
    # la date limite devient une étape synchronisée du calendrier
    deadline = [e for e in app.events if e.auto_key == "public_deadline"]
    assert len(deadline) == 1 and deadline[0].event_date == date(2030, 1, 15)
    assert app.next_due_date == date(2030, 1, 15)
    # aucun écrit/oral n'est supposé
    assert not [e for e in app.events if e.kind in ("written", "oral")]


def test_create_private_application_without_salary(client, ctx):
    client.post("/candidatures/nouvelle", data=private_payload(), follow_redirects=True)
    app = get_app("Data Engineer")
    assert app.private_details is not None
    assert app.private_details.salary_min is None and app.private_details.salary_expectation is None
    assert app.public_details is None


def test_validation_errors_are_french(client, ctx):
    response = client.post("/candidatures/nouvelle", data=public_payload(title="",
                           **{"public_details-deadline_date": "pas-une-date"}))
    html = response.get_data(as_text=True)
    assert "Ce champ est obligatoire." in html
    assert "date valide" in html
    assert Application.query.count() == 0


def test_private_salary_min_greater_than_max_rejected(client, ctx):
    response = client.post("/candidatures/nouvelle", data=private_payload(**{
        "private_details-salary_min": "20000", "private_details-salary_max": "10000"}))
    assert "supérieur ou égal" in response.get_data(as_text=True)
    assert Application.query.count() == 0


def test_duplicate_detection_on_create(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    response = client.post("/candidatures/nouvelle", data=public_payload(title="ingenieur d'etat — informatique "))
    assert "existe déjà" in response.get_data(as_text=True)
    assert Application.query.count() == 1
    client.post("/candidatures/nouvelle", data=public_payload(allow_duplicate="1"))
    assert Application.query.count() == 2


def test_edit_search_filter_archive_and_delete(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    client.post("/candidatures/nouvelle", data=private_payload())
    app = get_app("Data Engineer")

    response = client.post(f"/candidatures/{app.id}/modifier", data=private_payload(
        city="Fès", next_action="Relancer le recruteur", next_action_due=(today_local() + timedelta(days=2)).isoformat()),
        follow_redirects=True)
    assert "Modifications enregistrées" in response.get_data(as_text=True)
    db.session.expire_all()
    assert app.city == "Fès"
    assert app.next_due_date == today_local() + timedelta(days=2)

    html = client.get("/candidatures/?q=Fès").get_data(as_text=True)
    assert "Data Engineer" in html and "Ingénieur d’État — Informatique" not in html
    html = client.get("/candidatures/?sector=public").get_data(as_text=True)
    assert "Ingénieur d’État — Informatique" in html and "Data Engineer" not in html
    html = client.get("/candidatures/?deadline=7").get_data(as_text=True)
    assert "Data Engineer" in html
    html = client.get("/candidatures/?q=CODE-1").get_data(as_text=True)
    assert "Ingénieur d’État — Informatique" in html
    assert client.get("/candidatures/?sort=priority&group=status").status_code == 200

    client.post(f"/candidatures/{app.id}/archiver")
    db.session.expire_all()
    assert app.archived
    assert "Data Engineer" not in client.get("/candidatures/").get_data(as_text=True)
    assert "Data Engineer" in client.get("/candidatures/?archived=only").get_data(as_text=True)

    client.post(f"/candidatures/{app.id}/supprimer")
    assert Application.query.filter_by(title="Data Engineer").count() == 0
    assert ActivityLog.query.filter(ActivityLog.message.like("%supprimée%")).count() == 1


def test_duplicate_application(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    app = get_app("Ingénieur d’État — Informatique")
    client.post(f"/candidatures/{app.id}/dupliquer")
    copy = get_app("Ingénieur d’État — Informatique (copie)")
    assert copy.public_details.competition_code == "CODE-1"
    assert len(copy.checklist_items) == len(app.checklist_items)
    assert all(not item.done for item in copy.checklist_items)


def test_ready_status_blocked_when_dossier_incomplete_and_override(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    app = get_app("Ingénieur d’État — Informatique")
    assert app.checklist_summary["missing"]

    client.post(f"/candidatures/{app.id}/statut", data={"status": "prete"})
    db.session.expire_all()
    assert app.status == "a_examiner"

    response = client.post(f"/candidatures/{app.id}/modifier", data=public_payload(status="prete"))
    assert "pièces obligatoires manquantes" in response.get_data(as_text=True)
    db.session.expire_all()
    assert app.status == "a_examiner"

    client.post(f"/candidatures/{app.id}/statut", data={"status": "prete", "force_status": "y"})
    db.session.expire_all()
    assert app.status == "prete"

    # dossier complet → plus de blocage
    for item in app.checklist_items:
        if item.required and not item.done:
            client.post(f"/candidatures/{app.id}/checklist/{item.id}/basculer")
    db.session.expire_all()
    assert app.checklist_summary["ready"] and app.checklist_summary["percent"] == 100
    client.post(f"/candidatures/{app.id}/statut", data={"status": "envoyee"})
    db.session.expire_all()
    assert app.status == "envoyee"
    assert app.date_applied == today_local()
    # la date limite est considérée traitée une fois la candidature envoyée
    assert all(e.done for e in app.events if e.auto_key == "public_deadline")


def test_checklist_add_toggle_required_delete_and_template(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    app = get_app("Ingénieur d’État — Informatique")
    before = len(app.checklist_items)
    client.post(f"/candidatures/{app.id}/checklist", data={"label": "Attestation d’équivalence", "required": "y"})
    db.session.expire_all()
    assert len(app.checklist_items) == before + 1
    item = app.checklist_items[-1]
    client.post(f"/candidatures/{app.id}/checklist/{item.id}/basculer", data={"field": "required"})
    db.session.expire_all()
    assert not item.required
    client.post(f"/candidatures/{app.id}/checklist/{item.id}/supprimer")
    db.session.expire_all()
    assert len(app.checklist_items) == before
    client.post(f"/candidatures/{app.id}/checklist/modele")
    db.session.expire_all()
    assert len(app.checklist_items) == before  # pas de doublons


def test_multi_stage_events_and_completion(client, ctx):
    client.post("/candidatures/nouvelle", data=public_payload())
    app = get_app("Ingénieur d’État — Informatique")
    day1 = (today_local() + timedelta(days=10)).isoformat()
    day2 = (today_local() + timedelta(days=20)).isoformat()
    client.post("/calendrier/evenements/nouveau", data={"application_id": app.id, "kind": "written",
                "event_date": day1, "event_time": "09:00", "location": "Rabat", "details": "SQL, Big Data"})
    client.post("/calendrier/evenements/nouveau", data={"application_id": app.id, "kind": "oral", "event_date": day2})
    db.session.expire_all()
    kinds = sorted(e.kind for e in app.events)
    assert kinds == ["deadline", "oral", "written"]
    written = next(e for e in app.events if e.kind == "written")
    assert app.next_due_date == written.event_date  # plus proche que la date limite 2030

    client.post(f"/calendrier/evenements/{written.id}/terminer")
    db.session.expire_all()
    assert written.done
    assert app.next_due_date == next(e for e in app.events if e.kind == "oral").event_date

    html = client.get("/calendrier/entretiens-examens").get_data(as_text=True)
    assert "Épreuve orale" in html
    assert client.get(f"/calendrier/?vue=mois&date={day2}").status_code == 200

    # un événement synchronisé ne peut pas être supprimé directement
    deadline = next(e for e in app.events if e.auto_key)
    client.post(f"/calendrier/evenements/{deadline.id}/supprimer")
    assert db.session.get(ApplicationEvent, deadline.id) is not None


def test_dashboard_reflects_records(client, ctx):
    html = client.get("/").get_data(as_text=True)
    assert "Rien d’urgent" in html
    overdue = (today_local() - timedelta(days=1)).isoformat()
    client.post("/candidatures/nouvelle", data=private_payload(next_action="Relancer RH", next_action_due=overdue))
    html = client.get("/").get_data(as_text=True)
    assert "Relancer RH" in html
    assert "En retard" in html


def test_preparation_topic_crud_and_weak_filter(client, ctx):
    subject = PrepSubject.query.filter_by(name="SQL avancé").one()
    client.post("/preparation/sujets/nouveau", data={"subject_id": subject.id, "application_id": 0,
                "topic": "Fenêtrage", "priority": 3, "difficulty": 2, "confidence": 1, "status": "not_started",
                "minutes_spent": 0})
    client.post("/preparation/sujets/nouveau", data={"subject_id": subject.id, "application_id": 0,
                "topic": "Index B-tree", "priority": 1, "difficulty": 1, "confidence": 5, "status": "mastered",
                "minutes_spent": 30})
    assert PreparationTopic.query.count() == 2
    html = client.get("/preparation/?vue=faibles").get_data(as_text=True)
    assert "Fenêtrage" in html and "Index B-tree" not in html
    topic = PreparationTopic.query.filter_by(topic="Fenêtrage").one()
    client.post(f"/preparation/sujets/{topic.id}/temps", data={"minutes": 45, "confidence": 3})
    db.session.expire_all()
    assert topic.minutes_spent == 45 and topic.confidence == 3 and topic.status == "in_progress"
    client.post(f"/preparation/sujets/{topic.id}/supprimer")
    assert PreparationTopic.query.count() == 1


def test_seed_and_purge_demo_data_keeps_real_data(client, ctx):
    client.post("/candidatures/nouvelle", data=private_payload(title="Ma vraie candidature"))
    client.post("/parametres/donnees-exemple/ajouter")
    samples = Application.query.filter_by(is_sample=True).all()
    assert len(samples) >= 5 and all(a.title.startswith("[EXEMPLE]") for a in samples)
    # le dossier incomplet d'exemple apparaît dans les actions urgentes
    assert "Demande manuscrite signée" in client.get("/").get_data(as_text=True)
    client.post("/parametres/donnees-exemple/supprimer")
    assert Application.query.filter_by(is_sample=True).count() == 0
    assert Application.query.filter_by(title="Ma vraie candidature").count() == 1
