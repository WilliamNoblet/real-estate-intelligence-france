# Fiche d'audit — Immonot

> Vérifié le **2026-08-16**. Décision : **LIMITED**. Connecteur retenu comme **premier** (Phase 5).
> **Implémenté** : `collectors/immonot/adapter.py` (activé dans `config/sources/immonot.yaml`).

| Critère | Constat |
|---|---|
| Nom / éditeur | Immonot — Notariat Services (annonces des notaires de France) |
| Domaine | `www.immonot.com` |
| Type de source | Portail notarial (professionnels) |
| API publique ? | Non. Un flux XML existe mais c'est un canal d'**ingestion** partenaire (les logiciels de négociation notariale *poussent* les annonces), pas une API de diffusion. |
| Flux officiel ? | **Oui** — `https://www.immonot.com/sitemap.xml` (index public, 47 sitemaps enfants, daté du jour de vérification). |
| robots.txt | **Le plus permissif de l'échantillon** : `Disallow` uniquement sur `/utilisateur/`, `/account/`, `/api/`, `/web-view/` ; puis `Allow: /`. Sitemap déclaré. Pas de crawl-delay. |
| Authentification | Non pour la consultation des annonces publiques. |
| JavaScript nécessaire ? | Non pour l'énumération : le sitemap fournit des URL directes d'annonces. |
| Pagination | Énumération structurée via l'index de sitemaps (préférable au parcours paginé). |
| Identifiant stable | Oui, présent dans les URL des sitemaps enfants. |
| URL stable | Oui (URL canoniques d'annonces). |
| Données personnelles | Émetteurs = offices notariaux (professionnels). Exposition de particuliers faible ; **exclure toute donnée personnelle**. |
| Anti-bot | Aucun blocage constaté (robots.txt et sitemap récupérés sans 403 ni challenge). |
| Risques | Droit **sui generis** du producteur de BDD (art. L341-1 CPI) : ne pas extraire une part **substantielle** même si robots.txt l'autorise. CGU non lues intégralement → à confirmer. |

## Décision : LIMITED — contraintes impératives

- Collecte via le **sitemap officiel** uniquement ; ne pas crawler les pages de recherche.
- Débit **≤ 1 req/s**, `concurrency = 1`, backoff sur erreur.
- **Pas d'extraction substantielle** de la base ; usage strictement **personnel**.
- **Jamais** d'usurpation d'user-agent ; UA honnête et identifiable.
- **Aucune** donnée personnelle de particulier stockée.
- Désactivation immédiate du connecteur si la source change de politique.
- Idéalement : solliciter un accord/licence auprès de Notariat Services pour tout usage au-delà.

## Pourquoi en premier ?

Le plus propre juridiquement et techniquement (robots permissif, flux officiel frais, sans anti-bot), et données majoritairement professionnelles → moindre enjeu RGPD. PAP (annonces de particuliers) viendra ensuite pour la richesse « donnée primaire ».

## Implémentation (2026-08-18)

- **Discovery** : sitemaps de détail (`annonce_detail_ancien/*`, `annonce_detail_neuf/*`) listés dans
  `sitemap.xml`. Filtrage par département (préfixe de code postal du slug), borne `max_listings` par passe.
- **Parsing** : balises **OpenGraph** rendues côté serveur (aucun JavaScript requis).
  `og:title` = « {Type} à vendre {Ville} ({CP}) {Dépt} {N} pièces {S} m² {Prix} € » → type, ville,
  code postal, pièces, surface, prix. `og:url` → identifiant stable. `og:description` → description.
- **DPE non scrapé** : l'étiquette énergie sera enrichie plus tard via l'open data ADEME
  (rapprochement par adresse + surface), pas extraite du site.
- **Débit** : ~1 req/s (`requests_per_minute: 60`), user-agent honnête, aucune donnée personnelle.
- Fixtures de test **synthétiques** (`tests/fixtures/immonot/`) : aucune donnée réelle reproduite.
- Lancement : `make collect` → `python -m collectors.run` (nécessite la base ; passe par
  l'orchestrateur `run_collection`).
