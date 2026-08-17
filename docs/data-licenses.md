# Licences des données

> « Accessible sur internet » ≠ « librement réutilisable » (§128). Chaque dataset a sa licence.

| Source | Licence | Points de vigilance |
|---|---|---|
| DVF / DVF géolocalisées (DGFiP/Etalab) | Licence Ouverte 2.0 | CGU : pas de ré-identification des personnes, pas d'indexation par moteurs externes. Exclut 67/68/57 et Mayotte. |
| DVF+ open-data (Cerema) | Licence Ouverte 2.0 | — |
| DV3F (Cerema) | Conditions Fichiers fonciers — **accès restreint** | Non utilisé (habilitation requise). |
| Cadastre Etalab / PCI | Licence Ouverte | Géométrie simplifiée ; cas Strasbourg à part. |
| IGN Géoplateforme (BD TOPO, Admin Express, Contours IRIS) | Licence Ouverte / Etalab 2.0 | Accès **sans clé** via `data.geopf.fr`. |
| BAN / géocodage (IGN) | Etalab 2.0 | API `data.geopf.fr/geocodage` (l'ancienne `api-adresse.data.gouv.fr` est décommissionnée). 50 req/s/IP. |
| INSEE (COG, recensement, Filosofi) | Licence Ouverte | Filosofi figé à 2021. Millésimes à aligner. |
| DPE ADEME (`dpe03existant`) | Licence Ouverte 2.0 | Adresse = donnée personnelle (RGPD) ; pas d'usage de démarchage nominatif. |
| Annonces (portails) | **Propriété du producteur** (droit sui generis, L341-1 CPI) + CGU | Voir `docs/sources/*.md`. Pas d'extraction substantielle ; minimisation RGPD ; jamais de contournement d'anti-bot. |

## Cadre juridique de la collecte d'annonces
- **Droit sui generis du producteur de base de données** (art. L341-1 s. CPI) : interdit l'extraction d'une part substantielle **même si `robots.txt` l'autorise**.
- **RGPD / CNIL** (recommandations juin 2025) : minimisation, exclusion des sources qui s'opposent au moissonnage (robots/CGU/CAPTCHA), information des personnes.
- **Contournement d'anti-bot** (DataDome, Cloudflare, 403) : proscrit (risque art. 323-1 CP).

*Ce document n'est pas un conseil juridique.*
