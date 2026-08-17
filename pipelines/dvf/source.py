"""Métadonnées et constantes de la source DVF géolocalisées (geo-dvf, Etalab).

Source vérifiée le 2026-08-16 : Licence Ouverte 2.0, mise à jour semestrielle.
Fichiers bulk par département : {BASE_URL}/{annee}/departements/{dep}.csv.gz
Fichiers par commune :         {BASE_URL}/{annee}/communes/{dep}/{insee}.csv.gz
⚠ DVF exclut les départements 67, 68, 57 et Mayotte (976) (régime du Livre foncier)."""
from __future__ import annotations

BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"

# Départements hors périmètre DVF (à ne pas tenter de télécharger).
EXCLUDED_DEPARTMENTS = {"67", "68", "57", "976"}

# Métadonnées pour le catalogue data_source.
SOURCE_META = {
    "name": "DVF géolocalisées (geo-dvf)",
    "source_type": "OPEN_DATA",
    "provider": "Etalab / DINUM (à partir des données DGFiP)",
    "url": "https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees",
    "access_method": "Téléchargement bulk CSV .gz par département/commune",
    "license": "Licence Ouverte / Open Licence 2.0",
    "terms_url": "https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees",
    "refresh_frequency": "Semestrielle (avril / octobre)",
    "free": True,
    "notes": "Regrouper par id_mutation ; ne jamais sommer valeur_fonciere. Exclut 67/68/57/976.",
}

# Colonnes utiles du CSV geo-dvf (le fichier en compte ~40).
USED_COLUMNS = [
    "id_mutation",
    "date_mutation",
    "nature_mutation",
    "valeur_fonciere",
    "code_postal",
    "code_commune",
    "nom_commune",
    "code_departement",
    "id_parcelle",
    "type_local",
    "surface_reelle_bati",
    "nombre_pieces_principales",
    "surface_terrain",
    "longitude",
    "latitude",
]

# Codes conservés à l'ingestion : uniquement les mutations à titre de vente.
# Les autres natures (Échange, Expropriation, Donation…) sont comptées comme rejetées.
SALE_NATURES = {
    "Vente",
    "Vente en l'état futur d'achèvement",
    "Vente terrain à bâtir",
    "Adjudication",
}

# Types de locaux considérés comme surface habitable (pour le €/m²).
HABITABLE_TYPES = ["Maison", "Appartement"]

# Bornes de plausibilité (miroir de config/default.yaml, §76).
MIN_PLAUSIBLE_PPM2 = 200.0
MAX_PLAUSIBLE_PPM2 = 30000.0
MAX_SURFACE_M2 = 5000.0


def department_csv_url(dep: str, year: int) -> str:
    return f"{BASE_URL}/{year}/departements/{dep}.csv.gz"


def commune_csv_url(dep: str, insee: str, year: int) -> str:
    return f"{BASE_URL}/{year}/communes/{dep}/{insee}.csv.gz"
