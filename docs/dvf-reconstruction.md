# Règles de reconstruction des transactions DVF

> Une **ligne DVF ≠ une vente** (§26). Ce document fige les règles de passage
> « lignes brutes geo-dvf » → « transactions ». Code : `pipelines/dvf/reconstruct.py`.

## Regroupement
On regroupe les lignes par **`id_mutation`** (fourni par geo-dvf). Chaque mutation de vente
produit **une** ligne `transaction_dvf`.

## Prix
`valeur_fonciere` est **répétée** sur chaque ligne d'une mutation → on prend **une seule valeur**
(`max`), **jamais la somme**. Si absente → `sale_price = NULL` + drapeau `no_price`.

## Périmètre
On ne conserve que les **ventes** : `nature_mutation ∈ {Vente, Vente en l'état futur d'achèvement,
Vente terrain à bâtir, Adjudication}`. Les autres (Échange, Expropriation, Donation…) sont **rejetées**
(comptées dans `ingestion_batch.rows_rejected`).

## Surfaces
- `surface_m2` = **somme des `surface_reelle_bati`** des locaux **habitables** uniquement
  (`type_local ∈ {Maison, Appartement}`). Les dépendances/locaux commerciaux sont exclus. `0 → NULL`.
- `land_surface_m2` = somme des `surface_terrain` des **parcelles distinctes** (la surface de terrain
  est répétée sur chaque local d'une même parcelle → dédoublonnage par parcelle avant somme).
- `rooms` = somme des `nombre_pieces_principales` des locaux habitables. `0 → NULL`.

## Classification (`property_type`)
| Condition | Type |
|---|---|
| 1 Maison, 0 Appartement | `HOUSE` |
| 1 Appartement, 0 Maison | `APARTMENT` |
| aucun bâti habitable + terrain > 0 | `LAND` |
| plusieurs logements ou mixte | `OTHER` (+ drapeau `multi_bien`) |

## Prix au m²
`price_per_m2 = sale_price / surface_m2`, calculé **uniquement** pour un **logement unique**
(`HOUSE`/`APARTMENT`, non multi) avec surface et prix strictement positifs. Sinon `NULL`.

## Drapeaux qualité (`quality_flag`, concaténés par `;`)
`multi_bien` · `no_price` · `no_surface` · `surface_gt_5000` · `extreme_ppm2` (€/m² < 200 ou > 30 000).
Les valeurs sont **conservées et marquées**, jamais supprimées silencieusement (§160). Les seuils
sont dans `config/default.yaml` / `pipelines/dvf/source.py`.

## Limites assumées
- Une mutation groupant plusieurs biens hétérogènes est représentée en une ligne `OTHER` sans €/m²
  (attribution impossible sans hypothèse).
- La géolocalisation (`location` PostGIS) n'est pas peuplée en Phase 2 (lat/lon stockés) → Phase 3.
- Périmètre géographique : DVF exclut 67/68/57 et Mayotte.
