# Tout le monde veut prendre Sa Maison

Système d'alerting immobilier personnel — surveille les nouvelles annonces Leboncoin et envoie une notification WhatsApp dès qu'une annonce correspond à tes critères.

---

## Fonctionnalités

### Authentification
- Connexion par numéro de téléphone uniquement, sans mot de passe
- Session persistante via cookie JWT (30 jours)
- Accès privé : un seul utilisateur autorisé, configuré dans le `.env`

### Gestion des alertes
- Créer, modifier, supprimer des alertes
- Activer / mettre en pause une alerte sans la supprimer
- Critères disponibles par alerte :
  - Ville + rayon de recherche (en km)
  - Coordonnées GPS (lat/lng) pour le centrage
  - Prix maximum
  - Surface habitable minimale
  - Surface terrain minimale
  - Surface extérieure minimale (balcon/terrasse)
  - Nombre de pièces minimum

### Surveillance automatique
- Job automatique toutes les **heures** via APScheduler
- Interroge l'API Leboncoin (lib `lbc`) avec les critères de chaque alerte active
- Filtre les doublons via l'identifiant unique de l'annonce Leboncoin
- Insère les nouvelles annonces en base et envoie une notification WhatsApp

### Notifications WhatsApp
- Envoi via **Callmebot** (gratuit, aucun compte Meta requis)
- Format du message :
  ```
  🏠 Titre de l'annonce
  350 000€ | 95m² | T4
  Terrain:500m² | Ext:12m²
  📍 Lyon 7e
  🔗 leboncoin.fr/annonce/12345678
  ```

### Interface web
- **Dashboard** : liste des alertes avec statuts, critères, dernière vérification, nombre d'annonces trouvées et 3 stats globales (alertes actives, total, annonces détectées)
- **Formulaire** : création et édition d'alerte
- **Historique** : toutes les annonces détectées, filtrables par alerte, affichées en colonnes style presse
- Tous les formulaires soumis en JSON via `fetch()` (pas de rechargement de page)

### Design
- Style éditorial bordeaux inspiré des journaux — typographie Playfair Display + Source Sans 3
- Masthead "Tout le monde veut prendre / Sa Maison"
- Favicon 🏠 intégré en SVG inline
- Fond crème, accents bordeaux `#8b1a1a`

---

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | Python 3.11+ / FastAPI |
| Base de données | SQLite via SQLAlchemy |
| Templates HTML | Jinja2 |
| Job scheduler | APScheduler (in-process, toutes les heures) |
| Scraping Leboncoin | lib `lbc` (API non-officielle) |
| Notifications | WhatsApp via Callmebot |
| Client HTTP | httpx |
| Auth | JWT via python-jose |
| Config | python-dotenv |

---

## Dépendances

```
fastapi
uvicorn[standard]
sqlalchemy
jinja2
python-jose[cryptography]
apscheduler
lbc
httpx
python-dotenv
```

---

## Installation

```powershell
# 1. Cloner le projet
git clone <repo>
cd lbc-finder

# 2. Créer et activer l'environnement virtuel
python -m venv venv
venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
copy .env.example .env
# Puis éditer .env avec tes valeurs
```

---

## Configuration `.env`

```env
# Ton numéro de téléphone (utilisé pour te connecter à l'interface)
PHONE_NUMBER=0612345678

# Secret JWT — génère avec : python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=une_clé_longue_et_aléatoire

# Callmebot WhatsApp
# Envoie "I allow callmebot to send me messages" au +34 644 59 78 99 sur WhatsApp
# Tu reçois ton apikey en retour
WHATSAPP_PHONE=+33612345678
WHATSAPP_APIKEY=ton_apikey
```

---

## Démarrage local

```powershell
# Activer le venv (à faire à chaque nouvelle session)
venv\Scripts\activate

# Lancer l'application
python -m uvicorn app.main:app --reload --port 8000
```

Ouvre **http://localhost:8000** dans ton navigateur.
Connecte-toi avec le numéro configuré dans `PHONE_NUMBER`.

---

## Tester la réception d'une notification WhatsApp

### Étape 1 — Crée une alerte large
Dans l'interface, crée une alerte avec des critères très larges pour maximiser les chances de trouver des annonces :
- Ville : Paris (ou une grande ville)
- Rayon : 50 km
- Aucun autre filtre

### Étape 2 — Déclenche le job manuellement
Sans attendre l'heure automatique, force une vérification immédiate depuis PowerShell :

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8000/api/run-now" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"phone":"0612345678"}' `
  -UseBasicParsing
```

Remplace `0612345678` par ton numéro configuré dans `.env`.

### Étape 3 — Surveille les logs
Dans le terminal uvicorn tu dois voir :

```
[INFO] app.scheduler: === Lancement du job horaire ===
[INFO] app.scheduler: 1 alerte(s) active(s)
[INFO] app.scheduler: Vérification alerte #1 — Mon alerte
[INFO] app.sms: WhatsApp envoyé à +33612345678
[INFO] app.scheduler: Alerte #1 — 3 nouvelle(s) annonce(s)
```

### Étape 4 — Vérifier l'historique
Va sur **http://localhost:8000/history** — les annonces détectées doivent apparaître.
Si tu as reçu un message WhatsApp, tout fonctionne.

### En cas de problème

| Symptôme | Cause probable |
|---|---|
| Pas de logs scheduler | Le job ne s'est pas déclenché, vérifie que l'appli tourne |
| Logs OK mais pas de WhatsApp | Vérifie `WHATSAPP_APIKEY` et `WHATSAPP_PHONE` dans `.env` |
| Erreur 403 Leboncoin | Protection anti-bot Datadome, attends quelques minutes |
| 0 annonce trouvée | Élargis les critères de l'alerte |

---

## Déploiement Railway

### Variables d'environnement à configurer dans Railway
Dans ton projet Railway → onglet **Variables** :

| Variable | Valeur |
|---|---|
| `PHONE_NUMBER` | ton numéro |
| `JWT_SECRET` | ta clé générée |
| `WHATSAPP_PHONE` | ton numéro au format +336... |
| `WHATSAPP_APIKEY` | ta clé Callmebot |

### Déployer
```powershell
git add .
git commit -m "deploy"
git push
```

Railway redéploie automatiquement à chaque push sur `master`.

> ⚠️ Railway utilise un système de fichiers éphémère — la base SQLite est effacée à chaque redéploiement. Pour un usage long terme, ajoute un volume persistant dans Railway ou migre vers PostgreSQL.

---

## Structure du projet

```
lbc-finder/
├── app/
│   ├── main.py          # FastAPI — routes et logique HTTP
│   ├── database.py      # Modèles SQLAlchemy + init SQLite
│   ├── scheduler.py     # Job horaire APScheduler + scraping
│   ├── sms.py           # Envoi WhatsApp via Callmebot
│   ├── auth.py          # Authentification JWT
│   ├── config.py        # Variables d'environnement
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── alert_form.html
│       └── history.html
├── .env                 # Variables sensibles (non commité)
├── .env.example         # Template de configuration
├── .gitignore
├── Procfile             # Config Railway
├── runtime.txt          # Version Python pour Railway
├── requirements.txt
└── README.md
```