"""Historisation des annonces (Phase 6) : check / snapshot / event et indicateurs de prix.

Le moteur (`history.py`) est une logique PURE (aucun réseau, aucune base) : il compare une
observation à la précédente, décide s'il faut un nouveau snapshot, et émet les événements
typés (baisse/hausse de prix, changement de description…).
Les snapshots restent la source de vérité (§184)."""
