# ADR-002 — Modèle check / snapshot / event (append-only)

- Statut : accepté
- Date : 2026-08-17

## Contexte
L'actif central du projet est l'historique horodaté des annonces (§142, §197). Il faut pouvoir reconstruire chaque parcours de prix sans jamais perdre d'information (§39), et distinguer « on a vérifié » de « la donnée a changé » (§42).

## Décision
Trois entités distinctes :
- **`listing_check`** — chaque visite (trouvé ?, HTTP, succès parsing). Preuve d'observation.
- **`listing_snapshot`** — observation **append-only**, créée uniquement si le `payload_hash` des champs signifiants change (§41). Sinon, mise à jour de `last_seen_at`/`last_checked_at`.
- **`listing_event`** — diff typé entre snapshots (`PRICE_DECREASE`, `LISTING_REMOVED`, `POSSIBLE_REPUBLICATION`…).

Les snapshots sont la **source de vérité** ; toute table courante/agrégée (ex. `listing_current_state`, §111) est un **dérivé reconstructible**. Corrections tracées, jamais d'`UPDATE` silencieux de l'historique (§86-87).

## Conséquences
- Requêtes « état courant » servies par une vue/table dérivée pour la performance, sans perte d'historique.
- Statuts standardisés `ACTIVE/MISSING/REMOVED/REAPPEARED/UNKNOWN` via une machine à états à seuil configurable (`missing_before_removed`, §50). Une annonce absente n'est jamais « vendue » (§49).
