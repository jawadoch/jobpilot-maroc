"""Données d'exemple FICTIVES, optionnelles et clairement étiquetées.

Tous les enregistrements créés ici ont is_sample=True et un titre préfixé par
« [EXEMPLE] ». Les organisations, références et dates sont inventées (dates
calculées par rapport à aujourd'hui) : elles ne représentent ni de vraies
candidatures ni de vraies échéances. purge_demo() les supprime toutes.
"""
from datetime import time, timedelta

from ..extensions import db
from ..models import (
    ActivityLog,
    Application,
    ApplicationDocument,
    ApplicationEvent,
    ChecklistItem,
    Document,
    PrepSubject,
    PreparationTopic,
    PrivateJobDetails,
    PublicCompetitionDetails,
    log_activity,
)
from ..utils import today_local
from .application_service import apply_checklist_template
from .deadline_service import refresh_application
from .document_service import delete_stored_file

PREFIX = "[EXEMPLE] "


def has_demo_data() -> bool:
    return Application.query.filter_by(is_sample=True).count() > 0


def _doc(name, category, version="1", notes=None):
    doc = Document(name=PREFIX + name, category=category, version=version, is_sample=True,
                   notes=notes or "Document fictif sans fichier (données d’exemple).")
    db.session.add(doc)
    return doc


def _subject(name):
    return PrepSubject.query.filter_by(name=name).first()


def seed_demo() -> int:
    if has_demo_data():
        return 0
    today = today_local()
    d = lambda n: today + timedelta(days=n)  # noqa: E731

    cv_de = _doc("CV Data Engineer", "cv", "3")
    cv_ds = _doc("CV Data Scientist / IA", "cv", "2")
    _doc("CV BI / Data Analyst", "cv", "1")
    cv_pub = _doc("CV Ingénieur d’État — secteur public", "cv", "2")
    cin = _doc("CIN (copie)", "cin", "1")
    diplome = _doc("Diplôme d’ingénieur (copie certifiée)", "diplome_ingenieur", "1")
    lm = _doc("Lettre de motivation — Data Engineer", "lettre_motivation", "1")
    db.session.flush()

    apps = []

    # 1. Concours Ingénieur d'État dans un ministère — dossier incomplet
    a1 = Application(
        title=PREFIX + "Ingénieur d’État 1er grade — Informatique et données",
        organization="Ministère fictif de la Transition numérique (exemple)",
        sector="public", category="concours", specialty="Informatique / Big Data",
        city="Rabat", work_mode="onsite", source="emploi-public.ma",
        reference="EX-2026-INF-01", status="dossier_en_cours", priority=3,
        date_discovered=d(-6), next_action="Faire signer et légaliser la demande manuscrite",
        next_action_due=d(1), is_sample=True,
        description="Annonce fictive servant d’exemple.",
    )
    a1.public_details = PublicCompetitionDetails(
        administration="Ministère fictif de la Transition numérique",
        competition_title="Concours de recrutement d’ingénieurs d’État (exemple)",
        competition_code="EX-2026-INF-01", grade="Ingénieur d’État de 1er grade", scale="Échelle 11",
        specialty="Informatique", vacancies=3, region="Rabat-Salé-Kénitra",
        submission_method="online", opening_date=d(-10), deadline_date=d(5), deadline_time=time(16, 30),
        eligibility="Diplôme d’ingénieur d’État ; âge maximum selon l’annonce (exemple).",
        required_diploma="Diplôme d’ingénieur d’État en informatique ou équivalent",
        result="pending",
    )
    apply_checklist_template(a1)
    a1.events.append(ApplicationEvent(kind="written", title="Épreuve écrite (exemple)", event_date=d(25),
                                      event_time=time(9, 0), location="Rabat — lieu à confirmer",
                                      details="Matières : SQL, Big Data, culture générale (exemple)"))
    apps.append(a1)

    # 2. Recrutement à une université publique — envoyé, écrit à venir
    a2 = Application(
        title=PREFIX + "Ingénieur d’État — Data et systèmes d’information",
        organization="Université publique fictive (exemple)",
        sector="public", category="concours", specialty="Systèmes d’information",
        city="Fès", work_mode="onsite", source="Site officiel", reference="EX-UNIV-2026-07",
        status="convocation", priority=3, date_discovered=d(-40), date_applied=d(-30),
        next_action="Réviser la modélisation dimensionnelle", next_action_due=d(4), is_sample=True,
    )
    a2.public_details = PublicCompetitionDetails(
        administration="Université publique fictive", competition_title="Recrutement d’un ingénieur d’État (exemple)",
        competition_code="EX-UNIV-2026-07", grade="Ingénieur d’État de 1er grade", scale="Échelle 11",
        vacancies=1, region="Fès-Meknès", submission_method="depot", deadline_date=d(-28),
        shortlist_date=d(3), result="pending",
    )
    apply_checklist_template(a2)
    for item in a2.checklist_items:
        item.done = True
    a2.events.append(ApplicationEvent(kind="written", title="Épreuve écrite (exemple)", event_date=d(12),
                                      event_time=time(8, 30), location="Fès — faculté (exemple)",
                                      details="Bases de données, Data Warehouse, réseaux"))
    apps.append(a2)

    # 3. Data Engineer CDI dans un cabinet de conseil — test technique
    a3 = Application(
        title=PREFIX + "Data Engineer (CDI)",
        organization="Cabinet de conseil fictif — Casablanca (exemple)",
        sector="private", category="cdi", specialty="Data Engineering", city="Casablanca",
        work_mode="hybrid", source="LinkedIn", status="test_technique", priority=3,
        date_discovered=d(-15), date_applied=d(-12),
        next_action="Préparer l’environnement Docker pour le test", next_action_due=d(0), is_sample=True,
    )
    a3.private_details = PrivateJobDetails(
        currency="MAD", cv_document_id=cv_de.id, cover_letter_document_id=lm.id,
        tech_assessment_required=True, tech_assessment_date=d(2), tech_assessment_time=time(18, 0),
        negotiation_status="",
    )
    apps.append(a3)

    # 4. Data Scientist / IA — entretien
    a4 = Application(
        title=PREFIX + "Data Scientist / IA",
        organization="Entreprise fictive d’IA (exemple)", sector="private", category="cdi",
        specialty="Machine Learning / NLP", city="Rabat", work_mode="remote", source="Rekrute",
        status="entretien_rh", priority=2, date_discovered=d(-20), date_applied=d(-18),
        next_action="Préparer les questions sur le projet RAG", next_action_due=d(1), is_sample=True,
    )
    a4.private_details = PrivateJobDetails(currency="MAD", cv_document_id=cv_ds.id, follow_up_date=d(9))
    a4.events.append(ApplicationEvent(kind="interview_hr", title="Entretien RH (exemple)", event_date=d(1),
                                      event_time=time(10, 0), location="Visioconférence"))
    apps.append(a4)

    # 5. Opportunité internationale (relocalisation en France)
    a5 = Application(
        title=PREFIX + "Data Engineer — relocalisation France",
        organization="ESN fictive (exemple)", sector="private", category="cdi",
        specialty="Data Engineering / Cloud", city="Lyon", country="France", work_mode="hybrid",
        source="LinkedIn", status="a_examiner", priority=2, date_discovered=d(-2), is_sample=True,
        next_action="Vérifier les conditions de visa et de relocalisation", next_action_due=d(10),
    )
    a5.private_details = PrivateJobDetails(currency="EUR", relocation_notes="Relocalisation en France à étudier.")
    apps.append(a5)

    # 6. Candidature refusée (pour les statistiques)
    a6 = Application(
        title=PREFIX + "Analyste BI (CDD)", organization="Société fictive de distribution (exemple)",
        sector="private", category="cdd", specialty="Business Intelligence", city="Casablanca",
        work_mode="onsite", source="Indeed", status="refusee", priority=1,
        date_discovered=d(-60), date_applied=d(-55), is_sample=True,
    )
    a6.private_details = PrivateJobDetails(currency="MAD", rejection_reason="Profil plus expérimenté retenu (exemple).")
    apps.append(a6)

    for app in apps:
        db.session.add(app)
    db.session.flush()

    # Documents rattachés et checklist partiellement complétée
    links = [(a1, cv_pub), (a1, cin), (a2, cv_pub), (a2, cin), (a2, diplome), (a3, cv_de), (a3, lm), (a4, cv_ds)]
    for app, doc in links:
        db.session.add(ApplicationDocument(application_id=app.id, document_id=doc.id))
    for item in a1.checklist_items:
        if item.category == "cv":
            item.done, item.document_id = True, cv_pub.id
        elif item.category == "cin":
            item.done, item.document_id = True, cin.id
        elif item.category == "diplome_ingenieur":
            item.done, item.document_id = True, diplome.id
    # « Demande manuscrite signée » reste manquante volontairement

    # Sujets de préparation
    topics = [
        ("SQL avancé", a2, "Fonctions de fenêtrage et requêtes analytiques", 3, 3, 3, "in_progress", 90),
        ("Modélisation dimensionnelle", a2, "Schéma en étoile vs flocon, tables de faits", 3, 2, 2, "in_progress", 45),
        ("Big Data", a1, "Écosystème Hadoop / Spark", 2, 3, 2, "not_started", 0),
        ("Organisation administrative du Maroc", a1, "Administration centrale et services déconcentrés", 3, 2, 1, "not_started", 0),
        ("Dissertation en arabe", a1, "Plan type et entraînement chronométré", 2, 3, 2, "in_progress", 60),
        ("NLP et LLM", a4, "Architecture RAG et évaluation", 2, 3, 4, "reviewed", 120),
    ]
    for subject_name, app, topic, prio, diff, conf, status, minutes in topics:
        subject = _subject(subject_name)
        if subject is None:
            continue
        db.session.add(PreparationTopic(
            subject=subject, application=app, topic=PREFIX + topic, priority=prio, difficulty=diff,
            confidence=conf, status=status, minutes_spent=minutes, next_revision=d(3), is_sample=True,
        ))

    for app in apps:
        refresh_application(app)
        log_activity("seed", "Candidature d’exemple créée (données fictives)", app)
    db.session.commit()
    return len(apps)


def purge_demo() -> dict:
    apps = Application.query.filter_by(is_sample=True).all()
    app_ids = [a.id for a in apps]
    if app_ids:
        ActivityLog.query.filter(ActivityLog.application_id.in_(app_ids)).delete(synchronize_session=False)
    topics = PreparationTopic.query.filter_by(is_sample=True).delete(synchronize_session=False)
    for app in apps:
        db.session.delete(app)
    db.session.flush()
    docs = Document.query.filter_by(is_sample=True).all()
    for doc in docs:
        ChecklistItem.query.filter_by(document_id=doc.id).update({"document_id": None})
        PrivateJobDetails.query.filter_by(cv_document_id=doc.id).update({"cv_document_id": None})
        PrivateJobDetails.query.filter_by(cover_letter_document_id=doc.id).update({"cover_letter_document_id": None})
        delete_stored_file(doc.stored_filename)
        db.session.delete(doc)
    db.session.commit()
    return {"applications": len(apps), "documents": len(docs), "topics": topics}
