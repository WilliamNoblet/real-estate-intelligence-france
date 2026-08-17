# ADR-003 — Streamlit pour le dashboard du MVP

- Statut : accepté
- Date : 2026-08-17

## Contexte
Le MVP doit fournir rapidement une interface utile (table d'annonces, carte, historique de prix, filtres, §98-104) sans investir dans un front lourd.

## Décision
**Streamlit** pour le dashboard du MVP, consommant l'**API FastAPI** (jamais la base directement, §163). Cartographie via MapLibre/pydeck, deux couches distinctes annonces vs DVF (§103).

## Conséquences
- Time-to-MVP réduit ; itération rapide.
- Migration ultérieure possible vers React/Next.js si le besoin d'UX le justifie, sans changer l'API.
