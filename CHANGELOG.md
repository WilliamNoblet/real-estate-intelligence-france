# Changelog

Toutes les modifications notables de schéma, matching, métriques et connecteurs sont consignées ici (§121).
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [Non publié]

### Ajouté — Phase 3 (géographie & carte)
- Référentiel officiel COG (`pipelines/geo/cog.py`) : régions / départements / communes depuis
  `geo.api.gouv.fr`, upsert dans l'ordre des FK ; CLI `python -m pipelines.geo.run` (`make geo-load`).
- Géolocalisation PostGIS (`pipelines/geo/location.py`) : matérialisation de `transaction_dvf.location`
  (geography 4326) depuis lat/lon, à l'import et en backfill.
- API `GET /transactions/nearby` (requête spatiale `ST_DWithin`) + lat/lon dans `GET /transactions`.
- Dashboard : carte des transactions DVF par commune (pydeck) + médiane/Q1/Q3 du €/m².
- Tests : transformations COG (pures) + intégration base (géolocalisation + requête spatiale).

### Ajouté — Phase 2 (import DVF)
- Pipeline DVF géolocalisées (`pipelines/dvf/`) : téléchargement + SHA256 (`client.py`),
  reconstruction par `id_mutation` avec règles documentées (`reconstruct.py`,
  voir `docs/dvf-reconstruction.md`), chargement idempotent par upsert (`load.py`),
  orchestration CLI `python -m pipelines.dvf.run --dep 33` (`run.py`).
- Contrainte `UNIQUE(transaction_dvf.id_mutation)` via migration `0003` (upsert idempotent).
- Statistiques de marché par commune (`analytics/dvf_stats.py`) : médiane/Q1/Q3 du €/m²,
  seuil « échantillon insuffisant ».
- Endpoints API `GET /transactions` (paginé) et `GET /markets/{insee_code}`.
- Tests : reconstruction sur fixture (8 cas pièges) + intégration base (chargement + stats).

### Ajouté — Phase 0 (init) & Phase 1 (base)
- Échafaudage du dépôt : `docker-compose.yml` (db · api · worker · dashboard · adminer), `Dockerfile`,
  `pyproject.toml` (uv), `Makefile`, `.env.example`, `.gitignore`, CI GitHub Actions, Dependabot.
- Configuration applicative : `config/default.yaml` (seuils paramétrables) + `backend/app/core/`.
- Schéma initial PostgreSQL/PostGIS via Alembic (`0001` extension PostGIS, `0002` schéma initial) :
  référentiels (`data_source`, `ingestion_batch`, `job_run`, `region`, `department`, `commune`, `iris`),
  transactions (`transaction_dvf`), annonces (`property`, `listing`, `listing_snapshot`, `listing_check`,
  `listing_event`), matching (`property_match_candidate`, `dvf_match_candidate`), qualité
  (`data_quality_issue`) et enrichissement (`dpe`).
- API FastAPI minimale (`/health`, `/`, `/sources`) et dashboard Streamlit d'amorçage.

[Non publié]: https://github.com/OWNER/real-estate-intelligence-france
