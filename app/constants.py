"""Listes de valeurs et libellés français utilisés dans toute l'application."""

SECTORS = {"public": "Public", "private": "Privé"}

CATEGORIES = {
    "concours": "Concours public",
    "cdi": "CDI",
    "cdd": "CDD",
    "stage": "Stage",
    "freelance": "Freelance",
    "doctorat": "Doctorat",
    "autre": "Autre",
}

WORK_MODES = {
    "onsite": "Sur site",
    "hybrid": "Hybride",
    "remote": "Télétravail",
    "unknown": "Non précisé",
}

PRIORITIES = {1: "Basse", 2: "Moyenne", 3: "Haute"}

SOURCES = [
    "Site officiel",
    "emploi-public.ma",
    "LinkedIn",
    "Rekrute",
    "Indeed",
    "E-mail",
    "Recommandation",
    "Salon / forum",
    "Candidature spontanée",
    "Autre",
]

# --- Statuts -----------------------------------------------------------------
# "kind" donne la sémantique d'un statut, ce qui permet de modifier les libellés
# ou d'ajouter des statuts sans casser les statistiques.
STATUS_KINDS = {
    "preparation": "Avant envoi",
    "sent": "Envoyée (en attente)",
    "progress": "Réponse — en cours de sélection",
    "offer": "Offre",
    "accepted": "Acceptée (clôturée)",
    "rejected": "Refus (clôturée)",
    "closed": "Sans réponse / clôturée",
    "withdrawn": "Retirée (clôturée)",
}
CLOSED_KINDS = {"accepted", "rejected", "closed", "withdrawn"}
# Dénominateur du taux de réponse : candidatures réellement envoyées
SUBMITTED_KINDS = {"sent", "progress", "offer", "accepted", "rejected", "closed"}
# Numérateur : le recruteur / l'administration a donné une suite
RESPONSE_KINDS = {"progress", "offer", "accepted", "rejected"}

STATUS_KIND_BADGES = {
    "preparation": "bg-secondary-subtle text-secondary-emphasis",
    "sent": "bg-primary-subtle text-primary-emphasis",
    "progress": "bg-info-subtle text-info-emphasis",
    "offer": "bg-success-subtle text-success-emphasis",
    "accepted": "text-bg-success",
    "rejected": "bg-danger-subtle text-danger-emphasis",
    "closed": "bg-light text-secondary border",
    "withdrawn": "bg-light text-secondary border",
}

# (code, libellé, type, dossier complet exigé)
DEFAULT_STATUSES = [
    ("a_examiner", "À examiner", "preparation", False),
    ("a_preparer", "À préparer", "preparation", False),
    ("dossier_en_cours", "Dossier en cours", "preparation", False),
    ("prete", "Prête à envoyer", "preparation", True),
    ("envoyee", "Candidature envoyée", "sent", True),
    ("accuse", "Accusé de réception", "sent", False),
    ("preselectionne", "Présélectionné", "progress", False),
    ("convocation", "Convocation reçue", "progress", False),
    ("test_technique", "Test technique / QCM", "progress", False),
    ("ecrit", "Épreuve écrite", "progress", False),
    ("oral", "Entretien oral", "progress", False),
    ("entretien_rh", "Entretien RH", "progress", False),
    ("offre", "Offre reçue", "offer", False),
    ("acceptee", "Acceptée", "accepted", False),
    ("refusee", "Refusée", "rejected", False),
    ("liste_attente", "Liste d’attente", "progress", False),
    ("cloturee", "Sans réponse / clôturée", "closed", False),
    ("retiree", "Retirée", "withdrawn", False),
]

# --- Concours publics --------------------------------------------------------
SUBMISSION_METHODS = {
    "": "Non précisé",
    "online": "En ligne",
    "email": "Par e-mail",
    "depot": "Dépôt physique",
    "postal": "Voie postale",
    "other": "Autre",
}

COMPETITION_RESULTS = {
    "pending": "En attente",
    "admitted": "Admis",
    "failed": "Non admis",
    "waiting": "Liste d’attente",
    "unknown": "Inconnu",
}

# --- Secteur privé -----------------------------------------------------------
SALARY_FREQUENCIES = {
    "": "Non précisé",
    "monthly": "Mensuel",
    "annual": "Annuel",
    "tjm": "Taux journalier (TJM)",
    "other": "Autre",
}
CURRENCIES = {"MAD": "MAD (DH)", "EUR": "EUR (€)", "other": "Autre"}

NEGOTIATION_STATUSES = {
    "": "Non concerné",
    "pending": "À venir",
    "in_progress": "En cours",
    "agreed": "Accord trouvé",
    "failed": "Échec",
}

# --- Événements / étapes ------------------------------------------------------
EVENT_KINDS = {
    "deadline": "Date limite de candidature",
    "written": "Épreuve écrite",
    "oral": "Épreuve orale",
    "interview": "Entretien technique",
    "interview_hr": "Entretien RH",
    "test": "Test technique / QCM",
    "followup": "Relance / suivi",
    "shortlist": "Publication des présélectionnés",
    "results": "Publication des résultats",
    "other": "Autre",
}
EXAM_KINDS = {"written", "oral", "interview", "interview_hr", "test"}
EVENT_ICONS = {
    "deadline": "bi-hourglass-split",
    "written": "bi-pencil-square",
    "oral": "bi-mic",
    "interview": "bi-people",
    "interview_hr": "bi-person-badge",
    "test": "bi-laptop",
    "followup": "bi-telephone-outbound",
    "shortlist": "bi-list-check",
    "results": "bi-trophy",
    "other": "bi-calendar-event",
    "action": "bi-arrow-right-circle",
    "dossier": "bi-folder-x",
}

# --- Documents ------------------------------------------------------------------
DOCUMENT_CATEGORIES = {
    "cv": "CV",
    "lettre_motivation": "Lettre de motivation",
    "diplome_ingenieur": "Diplôme d’ingénieur",
    "dut": "DUT",
    "releves": "Relevés de notes",
    "cin": "CIN",
    "attestation_travail": "Attestation de travail",
    "attestation_stage": "Attestation de stage",
    "recommandation": "Lettre de recommandation",
    "demande_manuscrite": "Demande manuscrite signée",
    "projet_recherche": "Projet de recherche",
    "autre": "Autre",
}

# (libellé, catégorie de document, obligatoire)
DEFAULT_CHECKLIST_TEMPLATE = [
    ("CV", "cv", True),
    ("Diplôme d’ingénieur (copie certifiée)", "diplome_ingenieur", True),
    ("DUT (si exigé)", "dut", False),
    ("Relevés de notes (si exigés)", "releves", False),
    ("CIN (copie)", "cin", True),
    ("Demande manuscrite signée", "demande_manuscrite", True),
    ("Lettre de motivation", "lettre_motivation", False),
    ("Attestations justificatives", "attestation_travail", False),
]

# --- Préparation ----------------------------------------------------------------
PREP_STATUSES = {
    "not_started": "Non commencé",
    "in_progress": "En cours",
    "reviewed": "Révisé",
    "mastered": "Maîtrisé",
}
PREP_STATUS_BADGES = {
    "not_started": "bg-secondary-subtle text-secondary-emphasis",
    "in_progress": "bg-primary-subtle text-primary-emphasis",
    "reviewed": "bg-info-subtle text-info-emphasis",
    "mastered": "bg-success-subtle text-success-emphasis",
}
DIFFICULTIES = {1: "Facile", 2: "Moyenne", 3: "Difficile"}
CONFIDENCE_LEVELS = {
    1: "1 — Très faible",
    2: "2 — Faible",
    3: "3 — Moyen",
    4: "4 — Bon",
    5: "5 — Excellent",
}

DEFAULT_PREP_SUBJECTS = {
    "Data et bases de données": [
        "SQL avancé",
        "Modélisation dimensionnelle",
        "Data Warehouse",
        "BI, OLAP, schémas en étoile et flocon",
        "ETL/ELT",
        "Big Data",
        "Data Lake et formats Parquet/Avro",
        "Data Engineering",
        "MongoDB",
        "PostgreSQL",
    ],
    "IA et analytique": [
        "Statistiques et probabilités",
        "Machine Learning",
        "Deep Learning",
        "NLP et LLM",
        "Feature engineering",
        "Évaluation des modèles",
        "Data Science",
        "Python pour la data",
    ],
    "Informatique et systèmes d'information": [
        "Algorithmique et programmation",
        "Java",
        "POO",
        "UML",
        "Architecture logicielle",
        "Microservices",
        "Systèmes d'exploitation",
        "Réseaux et protocoles OSI",
        "Cybersécurité",
        "Cloud",
        "DevOps, Git et Docker",
        "Gouvernance des systèmes d'information",
    ],
    "Préparation secteur public marocain": [
        "Organisation administrative du Maroc",
        "Institutions publiques",
        "Décentralisation et collectivités territoriales",
        "Transformation numérique de l'administration",
        "Protection des données personnelles",
        "Cybersécurité et services publics numériques",
        "Culture générale et actualité nationale",
        "Dissertation en arabe",
        "Expression écrite en français",
        "Présentation orale et motivation",
    ],
}

# Profil initial (modifiable dans Paramètres > Profil)
DEFAULT_PROFILE = {
    "full_name": "Jaouad Ouchbar",
    "headline": "Ingénieur d’État — Systèmes d’Information et Big Data",
    "degree": "Diplôme d’Ingénieur d’État en Ingénierie des Systèmes d’Information et Big Data",
    "degree_school": "ENSA Berrechid",
    "degree_year": "2025",
    "previous_degree": "DUT Génie Informatique",
    "previous_school": "EST Laâyoune",
    "previous_year": "2022",
    "domains": (
        "Python, Java, SQL, Data Engineering, Data Science, Business Intelligence, "
        "Machine Learning, Deep Learning, NLP, LLM, RAG, Bases de données, ETL/ELT, "
        "Docker, Cloud, Systèmes d'information"
    ),
    "location": "Maroc",
    "target_cities": "Laâyoune, Rabat, Casablanca, Fès",
    "objective": (
        "Obtenir un poste stable dans le secteur public tout en continuant à explorer "
        "les opportunités pertinentes du secteur privé."
    ),
}

MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
MONTHS_FR_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                   "juil.", "août", "sept.", "oct.", "nov.", "déc."]
WEEKDAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
WEEKDAYS_FR_SHORT = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
