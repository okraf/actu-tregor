# actu-tregor

Agenda des événements du Trégor : concerts, fest-noz, expositions, marchés, sorties. Filtres par jour, commune et type d'événement.

## Fonctionnement

- **Site** : FastAPI + Jinja2, pages rendues côté serveur (lisibles sans JavaScript) : `/`, `/ville/<commune>`, `/type/<type>`, `/evenement/<id>-<titre>`, `sitemap.xml`, `robots.txt`. API JSON : `GET /api/evenements?type=&ville=&quand=&jour=&q=`.
- **Données** : NocoDB, base `TREGOR` (créée par `scripts/nocodb_init.py`) :
  - `evenements` : un événement (titre, type, dates, heure, commune, lieu, source, lien). Cocher `masque` pour retirer un événement du site ; une correction faite à la main est écrasée si la source change la même donnée.
  - `articles` : chaque article de presse lu, avec le verdict de l'IA (`evenement`, `autre`, `a_analyser`, `erreur`).
  - `collectes` : une ligne par source et par passage (lus, nouveaux, mis à jour, erreurs).
- **Collecte** : `POST /api/collecte` (en-tête `X-Cle-Collecte`, paramètre `source` facultatif), appelé par un planificateur (n8n). Les doublons entre sources sont écartés (titre simplifié + date + commune), la première source a la priorité.
- **Sources** :
  - Alentoor : agenda de chaque commune, JSON-LD schema.org.
  - OpenAgenda : export open data quotidien (`evenements-publics-openagenda` sur public.opendatasoft.com), sans les agendas emploi.
  - Unidivers : flux RSS des villes, puis fiche JSON-LD de chaque nouvel événement (200 au plus par passage).
  - actu.fr Le Trégor : articles analysés par une IA (API Ollama, `/api/chat`) qui repère les annonces d'événements datés ; 40 analyses au plus par passage.
- **Périmètre** : `data/communes.json`, 57 communes de Lannion-Trégor Communauté et 8 du Trégor finistérien, régénéré par `scripts/communes.py`. Les communes déléguées et lieux-dits connus sont rattachés à leur commune (`ALIAS` dans `app/referentiel.py`).
- **Types** : classement par mots-clés (`TYPES` dans `app/referentiel.py`), la catégorie de la source sert d'indice.

## Configuration

Statique : copier `config.example.toml` en `local/config.toml` (serveur) ou `config.toml` (poste de dev), jamais versionnés.

## Développement

```sh
uv venv -p 3.13 .venv && uv pip install -p .venv -r requirements.txt pytest
.venv/bin/python -m pytest -q tests
.venv/bin/uvicorn app.main:app --port 8765 --reload
.venv/bin/python -m app.collecte.passage openagenda   # une source, ou toutes sans argument
```

## Déploiement

Conteneur `website-tregor` (port 8080, aucun port publié, réseau Docker externe `app_network`), derrière un reverse proxy qui porte TLS, domaine et en-têtes de sécurité. `docker compose up -d --build` dans le dossier du dépôt, avec `local/config.toml` en place.
