"""Connecteurs d'annonces (Phase 5+). Un adapter INDÉPENDANT par source (§30).

Interface cible (§34) : ListingSourceAdapter{discover, fetch, parse, normalize, validate}
produisant un schéma normalisé unique NormalizedListing (§97). Aucun connecteur n'existe encore ;
le premier sera Immonot (voir docs/sources/immonot.md), en respectant les contraintes LIMITED."""
