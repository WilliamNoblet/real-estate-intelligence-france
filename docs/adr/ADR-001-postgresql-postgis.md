# ADR-001 — PostgreSQL + PostGIS comme base opérationnelle

- Statut : accepté
- Date : 2026-08-17

## Contexte
Le projet manipule des transactions et des annonces fortement géographiques (distance, contenance, appartenance à une commune/IRIS) et doit rester gratuit et reproductible, potentiellement jusqu'à plusieurs millions d'annonces et dizaines de millions de snapshots (§125).

## Décision
Utiliser **PostgreSQL 16 + PostGIS 3.4** comme base opérationnelle unique. Colonnes de position en `geography(Point,4326)` (calculs en mètres via `ST_DWithin`/`ST_Distance`), index GIST.

## Conséquences
- Un seul moteur pour le relationnel et le spatial ; pas de Big Data prématuré (§173).
- DuckDB reste envisageable **en complément** pour des analyses offline lourdes sur Parquet (§127), sans devenir la base opérationnelle.
- Le partitionnement/archivage n'est envisagé que si le volume l'impose réellement (§126).
