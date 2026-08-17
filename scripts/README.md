# scripts/

Utilitaires d'exploitation. Les sauvegardes sont pilotées via le `Makefile` (§88-89) :

```bash
make backup                                   # -> backups/AAAA-MM-JJ_database.dump (format custom pg_dump)
make restore FILE=backups/2027-01-01_database.dump
```

Un backup non testé n'est pas une sauvegarde : `make restore` doit être vérifié régulièrement (§89).
Priorité dès que le collecteur produit des données réelles (§143) : l'historique des annonces est irremplaçable.
