# Dictionnaire de données

Source de vérité du schéma : les modèles SQLAlchemy dans `backend/app/models/`.
Ce document en donne la vue d'ensemble ; il est complété au fil des phases (§117).

## Conventions
- Montants : `NUMERIC(12,2)` en euros (exact, agrégations SQL natives).
- Positions : `latitude`/`longitude` en `NUMERIC(9,6)` + `location` `geography(Point,4326)`.
- Horodatages : `timestamptz` (UTC en base, affichage Europe/Paris).
- Manquant : `NULL` (jamais `0`).

## Entités principales
| Table | Nature | Description |
|---|---|---|
| `data_source` | référentiel | Catalogue des sources (provenance). |
| `ingestion_batch`, `job_run` | opérationnel | Lots d'ingestion et exécutions de jobs (observabilité, idempotence). |
| `region`/`department`/`commune`/`iris` | référentiel géo | Codes officiels INSEE. |
| `transaction_dvf` | **fait — prix payé** | Transactions reconstruites (regroupées par `id_mutation`). |
| `property` | canonique | Bien immobilier présumé (relie plusieurs annonces). |
| `listing` | **annonce — prix demandé** | Une annonce par source ; `UNIQUE(source_id, external_listing_id)`. |
| `listing_snapshot` | historique append-only | Observation horodatée (prix, surface, DPE…). |
| `listing_check` | trace | Preuve de vérification (indépendante du changement). |
| `listing_event` | dérivé | Événements typés (baisse, retrait, republication…). |
| `property_match_candidate` | probabiliste | Fusions incertaines de biens (revue). |
| `dvf_match_candidate` | probabiliste | Rapprochement annonce ↔ transaction DVF. |
| `data_quality_issue` | qualité | Anomalies détectées par règle. |
| `dpe` | enrichissement | DPE ADEME (étiquettes énergie/GES). |

> Détail colonne-par-colonne (type, unité, nullable, source, bornes) à compléter par table au fur et à mesure.
