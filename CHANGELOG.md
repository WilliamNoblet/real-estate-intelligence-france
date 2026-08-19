# Changelog

Toutes les modifications notables de schéma, matching, métriques et connecteurs sont consignées ici (§121).
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/).

## [Non publié]

### Ajouté — Détection de vendeur pressé (repérage ventes rapides / successions)
- `analytics/motivated_seller.py` : `rapid_sale_signal` (fonction PURE) — score ∈ [0,1] de vendeur
  possiblement pressé à partir de l'historique d'une annonce (ampleur de la baisse cumulée, nombre
  de baisses successives, rapidité de la 1ʳᵉ baisse), niveau + motifs factuels. `rank_motivated_sellers`
  pour un futur « top annonces à surveiller ». Seuils calibrables (`RapidSaleConfig`).
- **Signal PROBABILISTE, jamais une conclusion** (§66) : ne dit jamais « succession/décès » ; renvoie
  un `disclaimer` rappelant qu'une succession n'est qu'une cause possible parmi d'autres. Aucune
  donnée personnelle utilisée.
- S'appuie sur `listing_indicators` (déjà codé) : **s'activera dès que la collecte d'annonces
  alimentera l'historique** (nécessite Docker + collectes répétées dans le temps). Tests purs inclus.

### Ajouté — Analyse régionale DVF hors-base (sans Docker)
- `analytics/regional.py` : agrégats PURS de prix **payé** au m² (médiane/Q1/Q3 robustes) par
  département, par an et par commune, sur un DataFrame de transactions déjà reconstruites.
  Réutilise exactement les règles d'ingestion (exclusion des €/m² aberrants et des non-logements,
  seuil d'échantillon communal). Registre `REGIONS` (bretagne, gironde…).
- `scripts/analyse_dvf_regionale.py` : CLI de bout en bout **sans base ni Docker** — télécharge
  (idempotent) les fichiers geo-dvf, reconstruit, agrège, écrit `data/analysis/<région>.json`
  (+ `.parquet`). `make analyse-region REGION=bretagne`.
- Permet de produire de grosses analyses de marché même tant que la stack Docker est indisponible.
- Tests purs (frame synthétique) : exclusions, médianes robustes, volumes, tops communaux.
- Validé en réel sur la **Bretagne** (22/29/35/56, 2021-2025) : 451 029 transactions reconstruites,
  225 555 exploitables au €/m², médiane régionale 2 360 €/m² (Q1 1 667 / Q3 3 254).

### Corrigé — 3ᵉ revue adversariale (scheduler / géocodage / rapprochement)
- **[critique]** scheduler : `next_run_time=None` (défaut `run_at_start=false`) mettait tous les jobs
  en PAUSE → le worker tournait sans jamais rien exécuter. Corrigé (kwarg omis hors run_at_start).
- scheduler : un job sans `interval_seconds` est ignoré au lieu de crasher le worker (KeyError).
- rapprochement DVF : le garde de type exclut aussi `UNKNOWN` (deux types inconnus ne valident plus
  un match ; `find_dvf_candidates` renvoie [] pour une annonce de type inconnu).
- géocodage : une ville faite d'espaces ne casse plus le repli sur le code postal.

### Ajouté — Rapprochement annonce ↔ DVF (§61, §198)
- `matching/dvf_reconciliation.py` : `score_dvf_match` (scoring PUR : type éliminatoire, commune,
  surface, chronologie mutation/retrait, plausibilité de prix) + `find_dvf_candidates` (candidats
  DVF triés par confiance, persistables dans `dvf_match_candidate`). Toujours PROBABILISTE, jamais
  « vendue à X » (§66).
- `property_type` ajouté sur `listing` (migration `0005`, renseigné à l'ingestion, exposé par l'API).
- API `GET /listings/{id}/dvf-candidates`.
- Tests : scoring pur (match fort, type éliminatoire, chronologie) + intégration base.

### Ajouté — Géocodage des annonces (§29)
- Colonnes géo sur `listing` (latitude/longitude/location/insee_code/geocoded_at/geocoding_score),
  migration `0004`.
- `pipelines/geocoding/client.py` : client IGN `data.geopf.fr/geocodage` (l'ancienne API BAN est
  décommissionnée) ; `parse_geocode_response` pur.
- `pipelines/geocoding/run.py` : `geocode_pending` — géocode les annonces sans position (ville+CP
  du dernier snapshot -> insee + coordonnées commune). `make geocode` + job scheduler `geocode_listings`.
- Précision COMMUNE (approximative) : jamais présentée comme une adresse certaine (§29).
- Tests : parser (fixture) + enrichissement base (géocodeur factice). Client validé en direct.

### Ajouté — Phase 7 (scheduler)
- `pipelines/scheduler.py` : automatisation locale via APScheduler, jobs pilotés par
  `config/default.yaml` (`collect_immonot` 1×/jour, `geocode_listings` toutes les 6 h),
  intervalles POLIS (§140). Le worker lance le scheduler ; `scheduled_jobs` testé.

### Ajouté — Connecteur Immonot (Phase 5, collecte réelle)
- `collectors/immonot/adapter.py` : discovery via sitemap officiel (filtré par département,
  borné), parsing des balises **OpenGraph** (rendu serveur, pas de JS) → type/ville/CP/pièces/
  surface/prix + identifiant stable. Branché sur l'orchestrateur ; `make collect` l'exécute.
- Contraintes LIMITED respectées : sitemap-only, ~1 req/s, user-agent honnête, pas de donnée
  personnelle, pas d'extraction substantielle. DPE non scrapé (enrichi via ADEME plus tard).
- Tests purs (parser + helpers) sur fixtures **synthétiques** (aucune donnée réelle). `enabled: true`.

### Corrigé — 2ᵉ revue adversariale (historisation / comparables / API annonces / collecte)
- **[critique]** orchestrateur : `seen` comparait les id de `discover()` (ex. URLs) aux id
  canoniques normalisés → toutes les annonces pouvaient être marquées absentes à tort. Corrigé
  (comparaison sur `normalized.external_id`).
- **[critique]** orchestrateur : ajout de `session.rollback()` + isolation d'erreur sur les deux
  boucles (une annonce/erreur DB n'interrompt plus toute la passe, §147).
- **[critique]** comparables : exclusion des transactions au €/m² aberrant (`extreme_ppm2`) qui
  faussaient médiane/quartiles/écart au marché (§160).
- `property_type` retiré du `payload_hash` (il n'était ni stocké ni diffé → évite un snapshot fantôme).
- `NormalizedListing` : arrondi des montants à 2 décimales (aligné sur PostgreSQL Numeric) → plus
  d'asymétrie stocké-vs-brut dans les diffs.
- `listing_state` : tie-breaker `id` sur l'ordre des snapshots + `drop_pct` calculé côté Python →
  cohérence prix courant/initial et baisse entre `/listings` et `/price-drops`.

### Ajouté — Orchestrateur de collecte (glue Phase 5→6)
- `collectors/run.py` : `run_collection` — pour un `ListingSourceAdapter`, exécute
  discover → fetch → parse → normalize → validate → `ingest_observation`, et marque absentes
  (`record_missing`) les annonces connues non redécouvertes. Générique, testé avec un adaptateur
  factice (sans réseau). `make collect` (CLI, stub tant qu'aucun connecteur réel n'est activé).
- Il ne reste plus, pour la collecte réelle, qu'à écrire l'adaptateur Immonot (parse HTML du site).

### Ajouté — Phase 8 (API de lecture des annonces)
- `analytics/listing_state.py` : état courant d'une annonce dérivé de ses snapshots
  (prix actuel/initial/min, baisse cumulée, nb de baisses, durée observée) + `price_drops`
  (annonces triées par plus forte baisse, SQL).
- API `GET /listings`, `/listings/{id}`, `/listings/{id}/snapshots`, `/listings/{id}/events`,
  `/listings/{id}/price-history`, `/price-drops` (§107).
- Dashboard : section « historique d'une annonce » (métriques + graphe de prix Altair).
- Test d'intégration base : état courant, price-drops et couche HTTP.

### Ajouté — Phase 9 (comparables DVF)
- `analytics/comparables.py` : `find_comparable_sales` — transactions payées proches d'un bien
  (même type, `ST_DWithin`, tolérance de surface, période), avec **élargissement progressif**
  (rayon puis période) tant que l'échantillon est insuffisant, **stats robustes** (médiane/Q1/Q3/IQR/n)
  et **écart au marché** formulé prudemment (« écart vs la médiane des comparables », jamais
  « surévalué de X % », §66).
- API `GET /comparables?lat=&lon=&property_type=&surface_m2=&asking_price_per_m2=`.
- Tests : fonctions pures (stats robustes, arithmétique de mois) + intégration base (sélection
  correcte des comparables, exclusions distance/surface/période/type, écart au marché).

### Ajouté — Phase 5/6 (contrat connecteur & moteur d'historisation)
- `collectors/base.py` : schéma normalisé `NormalizedListing` (Pydantic) + interface
  `ListingSourceAdapter` (discover/fetch/parse/normalize/validate). Contract test.
- `pipelines/listings/history.py` : moteur pur d'historisation (Phase 6) — `payload_hash`,
  `has_meaningful_change`, `diff_events` (PRICE_DECREASE/INCREASE, DESCRIPTION_CHANGED,
  PROPERTY_DETAILS_CHANGED), `listing_indicators` (prix initial/actuel/min, baisse cumulée,
  nb de baisses, durée observée, délai avant 1re baisse), et `transition` (machine à états
  ACTIVE/MISSING/REMOVED/REAPPEARED). Testé sur l'exemple §47.
- `pipelines/listings/ingest.py` : persistance d'une observation → listing + listing_check +
  (listing_snapshot si changement significatif) + listing_event ; `record_missing` fait avancer
  la machine à états (REMOVED après N vérifications négatives). Test d'intégration base : cycle
  complet découverte → 2 baisses → 3 absences (REMOVED) → réapparition.
- Le connecteur Immonot (collecte HTTP réelle) reste à brancher (nécessite réseau + base).

### Corrigé — revue adversariale du pipeline DVF/géo
- **[critique]** upserts DVF et COG découpés en lots (`backend/app/core/bulk.py`) : un `INSERT`
  unique dépassait la limite de 65535 paramètres de PostgreSQL et faisait planter tout import réel.
- `transaction_dvf.location` recalculée à chaque (ré)import (`only_missing=False`) : la géométrie
  ne reste plus figée quand un ré-import corrige lat/lon.
- Compteurs `rows_inserted` / `rows_updated` désormais exacts (les updates ne sont plus comptés
  comme des inserts) ; propagés à `job_run.items_updated`.
- Pagination `/transactions` et `/transactions/nearby` rendue déterministe (tie-breaker `id`).

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
