# Observatoire du marché immobilier français

Plateforme **local-first** d'observation du marché immobilier français. Elle distingue rigoureusement
deux notions que l'on ne mélange jamais :

- 🟠 **Prix demandé** — ce que le vendeur affiche dans une annonce ;
- 🟢 **Prix de transaction (DVF)** — ce qui a réellement été payé.

L'actif central du projet est l'**historique horodaté des annonces** (apparition, baisses de prix,
retrait, réapparition, republication), progressivement rapproché des transactions DVF réelles — de
façon **toujours probabiliste**.

> État : socle complet — base PostGIS, import DVF, géographie/carte, moteur d'historisation des
> annonces, connecteur Immonot, géocodage, comparables et rapprochement annonce↔DVF, scheduler,
> détection de vendeur pressé. Il reste à **peupler la base avec des données réelles** (nécessite
> Docker). En attendant, l'**analyse DVF fonctionne déjà hors-base** (voir plus bas). Détail complet
> dans `CHANGELOG.md`.

## Architecture

```
sources open data ──► worker (collecte · ETL · matching) ──► PostgreSQL/PostGIS ──► API FastAPI ──► Dashboard
```

- **Base** : PostgreSQL 16 + PostGIS 3.4 — *les snapshots sont la source de vérité, le reste est un dérivé recalculable*.
- **API** : FastAPI (docs auto sur `/docs`).
- **Worker** : collecte + pipelines + matching + scheduler (APScheduler, Phase 7).
- **Dashboard** : Streamlit (MVP).
- **Orchestration** : Docker Compose (`db · api · worker · dashboard · adminer`).

Voir `docs/adr/` pour les décisions d'architecture et `docs/data-dictionary.md` pour le schéma.

## Prérequis
- Docker + Docker Compose
- (Optionnel) `make` — voir la section « Sans make » pour Windows.

## Démarrage rapide

```bash
git clone <votre-remote>/real-estate-intelligence-france.git
cd real-estate-intelligence-france
cp .env.example .env

docker compose up -d          # démarre db · api · worker · dashboard
make migrate                  # applique les migrations Alembic (crée le schéma)
```

Puis :
- API : http://localhost:8000/docs
- Dashboard : http://localhost:8501
- Adminer (dev) : `make adminer` → http://localhost:8080

Importer la zone pilote (Gironde) — *disponible à partir de la Phase 2* :

```bash
make dvf-import DEP=33
```

## Analyse DVF hors-base (sans Docker)

Les transactions **DVF** (prix réellement payés, open data Etalab) s'analysent **sans base ni
Docker** : téléchargement + reconstruction (mêmes règles que l'ingestion) + agrégats robustes
(médiane/quartiles du €/m² par département, année et commune).

```bash
make analyse-region REGION=bretagne          # -> data/analysis/bretagne.json (+ .parquet)
# périmètre libre :
python -m scripts.analyse_dvf_regionale --departments 22 29 35 56 --years 2023 2024 2025
```

Régions prédéfinies : `bretagne`, `gironde`, … (`analytics/regional.REGIONS`). Étude d'exemple :
[`docs/marche-bretagne-2021-2025.md`](docs/marche-bretagne-2021-2025.md) (451 029 transactions,
4 départements bretons). Le module `analytics/motivated_seller.py` (détection de vendeur pressé)
s'activera dès que la collecte d'annonces alimentera l'historique.

## Commandes (Makefile)

| Commande | Effet |
|---|---|
| `make up` / `make down` | Démarre / arrête la stack |
| `make logs` / `make ps` | Logs / état des conteneurs |
| `make migrate` | `alembic upgrade head` |
| `make revision m="…"` | Nouvelle migration autogénérée |
| `make test` / `make lint` | Tests / ruff |
| `make dvf-import DEP=33` | Import DVF d'un département |
| `make analyse-region REGION=bretagne` | **Analyse DVF régionale hors-base (sans Docker)** |
| `make geo-load` / `make geocode` | Référentiel COG / géocodage des annonces |
| `make collect` | Passe de collecte d'annonces |
| `make dashboard` | Démarre api + dashboard |
| `make backup` / `make restore FILE=…` | Sauvegarde / restauration PostgreSQL |
| `make psql` / `make shell` | Console SQL / shell conteneur |

### Sans `make` (Windows)
`make` n'est pas toujours présent sous Windows. Équivalents directs :

```bash
docker compose up -d
docker compose run --rm api alembic -c database/alembic.ini upgrade head   # = make migrate
docker compose run --rm -e DATABASE_URL=postgresql+psycopg://reif:reif@db:5432/reif api pytest   # = make test
docker compose run --rm api ruff check .                                    # = make lint
```

## Sources de données (open data, vérifiées le 2026-08-16)
DVF géolocalisées (transactions) · Cadastre Etalab · IGN Géoplateforme (`data.geopf.fr`, sans clé) ·
géocodage BAN (`data.geopf.fr/geocodage`) · INSEE COG 2026 · DPE ADEME. Détails et licences :
`docs/data-licenses.md`.

## Limitations & principes
- Une annonce **retirée n'est pas « vendue »** ; un prix demandé n'est pas un prix payé.
- Les rapprochements inter-annonces et annonce↔DVF sont **probabilistes**, avec score de confiance.
- **Collecte responsable** : respect de `robots.txt`/CGU, pas de contournement d'anti-bot, pas
  d'extraction substantielle, minimisation RGPD (aucune donnée personnelle de particulier).
- DVF exclut les départements 67, 68, 57 et Mayotte.

## Roadmap (résumé)
**Faits** : 0 init · 1 base · 2 DVF · 3 géo/carte · 4 audit sources · 5 connecteur Immonot ·
6 snapshots/événements · 7 scheduler · 8 dashboard · 9 comparables DVF · rapprochement annonce↔DVF ·
géocodage · analyse régionale hors-base · détection de vendeur pressé.
**À venir** : peuplement en données réelles (Docker), 2ᵉ source (PAP), calibration du matching sur
données réelles, republications, sauvegardes. Détail : `CHANGELOG.md` et le rapport d'architecture.

## Licence
Code sous licence MIT (`LICENSE`). Les **données** restent soumises à leurs licences propres
(`docs/data-licenses.md`).
