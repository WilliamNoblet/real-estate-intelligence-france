# Marché immobilier breton — prix payés (DVF), 2021-2025

> Analyse produite **hors-base** (sans Docker) via `scripts/analyse_dvf_regionale.py` +
> `analytics/regional.py`, sur les données **DVF géolocalisées** (Etalab / DGFiP, Licence Ouverte 2.0).
> Départements 22 (Côtes-d'Armor), 29 (Finistère), 35 (Ille-et-Vilaine), 56 (Morbihan).
>
> ⚠ Toutes les valeurs sont des **médianes de prix réellement payés au m²** (prix de transaction),
> **jamais** des prix demandés (§26, §66). Aucun jugement « surévalué / sous-évalué ».
>
> Chiffres passés par une **contre-analyse adversariale** (21 constats confirmés, 5 écartés pour
> imprécision numérique). Reproductible : `make analyse-region REGION=bretagne`.

## Base de calcul

| Étape | Volume |
|---|---:|
| Lignes brutes DVF (2021-2025, 4 dépts) | 1 254 285 |
| Lignes hors-vente rejetées | 15 340 |
| **Transactions reconstruites** (regroupées par mutation) | **451 029** |
| dont maisons + appartements | 227 348 |
| **Exploitables au €/m²** (base des médianes) | **225 555** |

Une mutation s'éclate sur ~2,78 lignes DVF ; la valeur foncière n'est **jamais** sommée. Le €/m² n'est
calculé que pour un **logement unique** (une seule maison ou un seul appartement) avec surface et prix ;
les €/m² aberrants (< 200 € ou > 30 000 €) sont exclus.

## Niveaux de prix (médiane €/m², période entière)

| Dépt | Global | Q1 | Q3 | Maison | Appartement | n |
|---|---:|---:|---:|---:|---:|---:|
| 35 Ille-et-Vilaine | **2 818** | 2 065 | 3 767 | 2 402 | 3 333 | 69 308 |
| 56 Morbihan | **2 713** | 1 842 | 3 756 | 2 496 | 3 205 | 51 857 |
| 29 Finistère | **2 061** | 1 545 | 2 653 | 2 038 | 2 097 | 62 948 |
| 22 Côtes-d'Armor | **1 902** | 1 315 | 2 615 | 1 842 | 2 108 | 41 442 |
| **Région** | **2 360** | 1 667 | 3 254 | 2 171 | 2 774 | 225 555 |

Écart entre le département le plus cher et le moins cher : **+48 %**.

## Constats vérifiés

1. **Une Bretagne coupée en deux.** L'axe Rennes–golfe du Morbihan (35, 56) se détache nettement de
   l'Ouest et de l'intérieur (29, 22).
2. **La côte dessine le prix, pas la centralité.** Les 8 communes les plus chères sont toutes littorales
   ou insulaires et dépassent Rennes (3 827 €) : Île-de-Bréhat 6 567, Île-aux-Moines 6 253,
   La Trinité-sur-Mer 5 811, Carnac 5 585, Dinard 5 304, Quiberon 5 109, Saint-Malo 4 505. À l'opposé, le
   Centre-Bretagne rural descend sous 810 € (Bolazec 721). Rapport jusqu'à **×9**. Hors Rennes (+36 % vs
   médiane départementale) et Vannes (+41 %), les grands pôles de l'Ouest sont au niveau ou **sous** la
   médiane de leur département (Saint-Brieuc, Lorient, Brest, Quimper).
3. **L'appartement se paie ~+28 % au m²** que la maison à l'échelle régionale (localisation + surfaces plus
   petites, pas un logement plus cher). Prime forte à l'est/sud (35 : +39 %, 56 : +28 %), faible à l'ouest
   (29 : +3 %, cas atypique de quasi-parité).
4. **Une flambée concentrée sur 2022** (+10 à +14 % en un an), puis une progression qui se casse dès 2023.
5. **Retournement 2024 des maisons** dans les 3 départements les plus chers (−1,8 à −2,7 %).
6. **Rebond 2024→2025 modéré et inégal** (prix +1 à +3 % sur les maisons ; volumes en hausse dans 3 dépts
   sur 4). À confirmer : 2025 peut être incomplète dans DVF.
7. **Côtes-d'Armor à contre-courant** : seule médiane maison jamais en recul, +22,2 % sur la période
   (rattrapage depuis un niveau bas).
8. **Effondrement des volumes** : −32,8 % de transactions entre 2021 (111 158) et 2024 (74 729), homogène
   entre départements ; creux en 2024, léger rebond en 2025 (77 390). Le Finistère ne rebondit pas (−2,2 %).

## Volumes de ventes (tous types)

| Année | 22 | 29 | 35 | 56 | Région |
|---|---:|---:|---:|---:|---:|
| 2021 | 22 199 | 29 901 | 32 041 | 27 017 | 111 158 |
| 2022 | 20 751 | 27 941 | 30 765 | 24 365 | 103 822 |
| 2023 | 16 809 | 22 973 | 24 265 | 19 883 | 83 930 |
| 2024 | 15 191 | 20 143 | 21 451 | 17 944 | 74 729 |
| 2025 | 15 521 | 19 703 | 23 250 | 18 916 | 77 390 |

## Précautions de lecture

- **Prix payés, pas demandés.** DVF enregistre les montants actés. Les prix demandés (annonces) sont une
  autre grandeur, traitée séparément par la plateforme.
- **Bâti uniquement.** La moitié des transactions (terrains 31 %, « autres » 18,5 %) n'alimente pas le €/m².
- **Petits échantillons.** Les médianes d'îles et petites communes (Île-de-Bréhat n=47, Bolazec n=30) sont
  indicatives, non stables. Seuil de robustesse retenu : n ≥ 20.
- **Résidences secondaires.** Les marchés insulaires et côtiers reflètent largement un marché de résidence
  secondaire, peu comparable à un marché de résidence principale.
- **2025 préliminaire.** Délai d'enregistrement des mutations : la dernière année peut être sous-comptée.
- **Couverture.** Les 4 départements bretons sont couverts par DVF (contrairement à l'Alsace-Moselle 67/68/57
  et à Mayotte 976, régis par le livre foncier).

## Reproduire

```bash
make analyse-region REGION=bretagne          # -> data/analysis/bretagne.json (+ .parquet)
# ou, pour un périmètre libre :
python -m scripts.analyse_dvf_regionale --departments 22 29 35 56 --years 2023 2024 2025
```
