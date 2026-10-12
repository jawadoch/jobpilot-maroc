# JobPilot Maroc

Gestionnaire personnel de candidatures pour la recherche d’emploi au Maroc — concours
publics et secteur privé. Application Flask locale, mono-utilisateur, entièrement en
français, qui fonctionne **sans connexion Internet** une fois les dépendances installées
(Bootstrap, Bootstrap Icons et Chart.js sont fournis dans `app/static/vendor`).

## Fonctionnalités

| Module | Contenu |
|---|---|
| **Tableau de bord** | Indicateurs (total, actives, public/privé, échéances, examens, actions requises, offres, refus, taux de réponse), actions urgentes, événements à 7 et 30 jours, activité récente, 4 graphiques. |
| **Candidatures** | Modèle unique pour le public et le privé : création, consultation, modification, duplication, archivage, suppression (avec confirmation). Statut distinct de la **prochaine action**. Recherche, filtres (secteur, statut, contrat, ville, échéance, priorité, archives), tris, regroupement par statut, pagination, filtres enregistrés. |
| **Concours publics** | Administration, code, grade/échelle, postes, candidats, région, mode de dépôt, ouverture, date + heure limite, éligibilité, diplôme exigé, pièces, mobilité, affectation, présélection, résultats, résultat du concours, liens officiels. Nombre illimité d’étapes (écrit, oral, entretien, test…). |
| **Secteur privé** | Salaire (facultatif, MAD/EUR/autre), fréquence, prétentions, mobilité/relocalisation (ex. France), version du CV et de la lettre envoyées, recommandation, test technique, retours d’entretien et RH, relance, négociation, offre, motif de refus. |
| **Calendrier** | Vues agenda, semaine et mois ; niveaux d’alerte : en retard, aujourd’hui, ≤ 3 jours, ≤ 7 jours, à venir, terminé. Rappels **dans l’application uniquement** (aucun e-mail, SMS ni notification). |
| **Entretiens et examens** | Épreuves et entretiens à venir, passés, avec retours/résultats. |
| **Documents** | Bibliothèque (CV, diplômes, CIN, attestations…), versions sans écrasement, expiration, rattachement plusieurs-à-plusieurs aux candidatures, téléchargement sécurisé. |
| **Checklist du dossier** | Modèle configurable copié dans chaque nouveau concours, puis modifiable par candidature ; pièce complétée / associée / disponible / manquante, pourcentage, préparation à l’envoi. Les statuts « Prête à envoyer » et « Envoyée » sont bloqués si des pièces obligatoires manquent (contournement explicite « Forcer »). |
| **Préparation** | Sujets par matière (liste prédéfinie modifiable de 40 matières), lien au concours, priorité, difficulté, confiance 1–5, état, prochaine révision, temps passé, poids ; vues points faibles, examens à venir, révisions dues ; progression par domaine. |
| **Statistiques** | Tableaux détaillés et définitions des taux. |
| **Paramètres** | Profil, statuts (libellés, ordre, signification, ajout), modèle de checklist, import/export, sauvegarde/restauration, données d’exemple. |

## Installation sous Windows 11 (PowerShell)

Prérequis : **Python 3.12 ou plus récent** ([python.org](https://www.python.org/downloads/windows/), cochez « Add python.exe to PATH »). Vérifiez avec :

```powershell
py -3.12 --version
```

Puis, depuis le dossier du projet :

```powershell
cd D:\FIND_WORK\jobpilot-maroc
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Si PowerShell refuse d’exécuter `Activate.ps1`, autorisez les scripts locaux pour votre
> utilisateur puis relancez l’activation :
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

Configuration facultative : `Copy-Item .env.example .env`, puis modifiez `.env`.

## Démarrage

```powershell
cd D:\FIND_WORK\jobpilot-maroc
.\.venv\Scripts\Activate.ps1
python run.py
```

Ouvrez **http://127.0.0.1:5000** dans votre navigateur. Arrêt : `Ctrl+C` dans PowerShell.

Au premier démarrage, la base SQLite `instance\jobpilot.db` est créée avec les statuts,
les matières de préparation, le modèle de checklist et votre profil (modifiable dans
Paramètres). Les démarrages suivants **ne suppriment jamais** de données : seules les tables
manquantes sont créées.

### Données d’exemple (facultatif)

Des candidatures **fictives**, préfixées `[EXEMPLE]` et marquées d’un badge, peuvent être
ajoutées puis retirées sans toucher à vos données réelles — depuis
*Paramètres › Données d’exemple*, ou en ligne de commande :

```powershell
flask --app run seed-demo     # ajoute les exemples
flask --app run purge-demo    # supprime uniquement les exemples
```

### Autres commandes

```powershell
flask --app run init-db       # crée les tables manquantes (sans rien supprimer)
flask --app run backup        # sauvegarde la base dans instance\backups
python -m pytest              # lance les tests
```

## Données, sauvegarde et restauration

| Élément | Emplacement par défaut |
|---|---|
| Base de données | `instance\jobpilot.db` |
| Documents importés | `uploads\` (fichiers renommés avec un identifiant aléatoire) |
| Sauvegardes | `instance\backups\` |
| Clé secrète générée | `instance\secret_key` |

**Sauvegarder** (*Paramètres › Sauvegarde*) :
1. « Sauvegarder la base » télécharge une copie cohérente `.db` (aussi conservée dans `instance\backups`).
2. « Archive des documents » télécharge un `.zip` du dossier `uploads`.

Conservez ces deux fichiers sur un support externe. Vous pouvez aussi simplement copier les
dossiers `instance` et `uploads` lorsque l’application est arrêtée.

**Restaurer** : choisissez un fichier `.db`, cochez la case et tapez `RESTAURER`. Le fichier
est vérifié (format SQLite, intégrité, tables JobPilot) **avant** toute modification, et la
base actuelle est d’abord copiée sous `instance\backups\jobpilot-avant-restauration-….db`.
Les documents ne font pas partie de la base : pour les restaurer, décompressez l’archive
`.zip` et placez son contenu dans `uploads\`.

**Exporter / importer** (*Paramètres › Import / export*) :
- CSV compatible Excel (UTF-8 avec BOM, séparateur `;`), JSON des candidatures avec étapes,
  checklist et documents, et export JSON complet.
- Import CSV à partir du modèle téléchargeable (ou d’un export CSV) : un **aperçu** montre les
  erreurs et les doublons (même titre + organisation + référence, sans tenir compte des
  accents ni de la casse) ; rien n’est enregistré avant confirmation et les doublons sont ignorés.

## Choix techniques et conventions

- **Fuseau horaire** : `Africa/Casablanca` (l’identifiant IANA du Maroc ; « Europe/Casablanca »
  n’existe pas). Les dates saisies (dates limites, épreuves, entretiens) sont stockées telles
  quelles en heure locale ; les horodatages techniques sont stockés en UTC et affichés en heure
  marocaine. Affichage au format JJ/MM/AAAA, montants en MAD.
- **Statut ≠ prochaine action** : chaque candidature a un statut (où elle en est) et une
  prochaine action datée (ce qu’il faut faire). Le champ « Catégorie / type de contrat » sert
  de type de contrat pour le privé.
- **Événements synchronisés** : la date limite, la publication des présélectionnés et des
  résultats (public), le test technique et la relance (privé) saisis dans la fiche deviennent
  automatiquement des étapes du calendrier (icône lien). La date limite est marquée traitée
  quand la candidature passe à un statut « envoyée ».
- **Statistiques** : une candidature *envoyée* a un statut de type envoyée, réponse, offre,
  acceptée, refus ou sans réponse (hors retirées et hors préparation). Le *taux de réponse* =
  candidatures ayant reçu une suite ÷ candidatures envoyées. La signification de chaque statut
  se règle dans *Paramètres › Statuts*.
- **Migrations** : pas d’Alembic, pour rester léger. L’initialisation crée seulement les tables
  manquantes. Si une future version ajoute des colonnes à une table existante, elle devra
  fournir une migration (ou Flask-Migrate pourra être ajouté).

## Sécurité

- Le serveur écoute uniquement sur **127.0.0.1** (inaccessible depuis le réseau).
- Protection CSRF sur tous les formulaires et actions, ORM SQLAlchemy (aucune requête SQL
  concaténée), validation des saisies, en-têtes de sécurité (CSP stricte sans script en ligne,
  `nosniff`, anti-iframe).
- Documents : extensions autorisées (PDF, DOC, DOCX, ODT, RTF, TXT, JPG, PNG), vérification de
  la signature du fichier, taille maximale configurable, nom de stockage aléatoire, accès
  uniquement par identifiant (jamais par chemin), téléchargement en pièce jointe, jamais
  exécutés. Le contenu des documents n’est jamais journalisé.
- Aucune clé d’API ni compte externe n’est nécessaire.

### Si l’application doit un jour être accessible depuis le réseau

La version actuelle **n’a pas d’authentification** : ne changez pas `JOBPILOT_HOST` en
`0.0.0.0` en l’état. Pour un déploiement, il faudrait au minimum : ajouter une authentification
(par ex. Flask-Login avec mot de passe haché), définir une `JOBPILOT_SECRET_KEY` longue et
privée, servir l’application via un serveur WSGI (par ex. `waitress-serve --listen=127.0.0.1:5000 run:app`)
derrière un proxy HTTPS, activer les cookies `Secure`/`HttpOnly`, et chiffrer les sauvegardes.

## Structure du projet

```
jobpilot-maroc/
├── app/
│   ├── __init__.py          fabrique Flask, en-têtes de sécurité, erreurs, commandes CLI
│   ├── constants.py         libellés français, statuts, catégories, matières par défaut
│   ├── extensions.py        SQLAlchemy, CSRF
│   ├── forms.py             formulaires WTForms (messages en français)
│   ├── models.py            modèles et relations
│   ├── utils.py             fuseau horaire, dates et montants à la française
│   ├── routes/              dashboard, applications, events, documents, preparation, settings, exports
│   ├── services/            statistiques, échéances/agenda, sauvegarde, import/export, documents, exemples
│   ├── static/              CSS, JS, bibliothèques locales (vendor/)
│   └── templates/           gabarits Jinja2
├── tests/                   tests pytest
├── instance/                base, sauvegardes, clé (créé au démarrage, ignoré par git)
├── uploads/                 documents importés (créé au démarrage, ignoré par git)
├── config.py  run.py  requirements.txt  .env.example  pytest.ini
```

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Les tests (base temporaire, sans toucher à vos données) couvrent : rendu de toutes les pages
sur base vide, création public/privé, validation en français, doublons, modification,
recherche et filtres, archivage, suppression, duplication, blocage du statut « Prête à
envoyer » et contournement, checklist, étapes multiples, tableau de bord, préparation,
documents (import, refus des fichiers invalides, chemins, versions, rattachement), export
CSV/JSON, import CSV avec aperçu et doublons, sauvegarde/restauration, statistiques, niveaux
d’alerte, CSRF et en-têtes de sécurité.
