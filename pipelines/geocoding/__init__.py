"""Géocodage (Phase 3/7, §29) via l'API IGN Géoplateforme (data.geopf.fr/geocodage).

⚠ L'ancienne API `api-adresse.data.gouv.fr` est décommissionnée (janv. 2026). On géocode les
annonces au niveau COMMUNE (ville + code postal -> insee + coordonnées approximatives) : une
localisation approximative ne doit jamais être présentée comme une adresse certaine (§29)."""
