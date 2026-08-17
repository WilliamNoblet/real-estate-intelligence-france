# Changelog

Toutes les modifications notables de schéma, matching, métriques et connecteurs sont consignées ici (§121).
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [Non publié]

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
