"""Pipeline géographique (Phase 3) : référentiel officiel (COG) + géolocalisation PostGIS.

- cog.py : régions / départements / communes depuis geo.api.gouv.fr (Découpage administratif,
  toujours actif — seul le géocodage d'adresses a migré vers l'IGN, §5).
- location.py : peuplement de la colonne `location` (geography) des transactions depuis lat/lon."""
