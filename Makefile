# Encapsule Docker Compose pour ne pas mémoriser vingt commandes (§16).
# Windows sans `make` : lancer directement les commandes `docker compose ...` correspondantes
# (voir README, section « Sans make »).

COMPOSE ?= docker compose
DEP ?= 33
DATE := $(shell date +%Y-%m-%d)

.DEFAULT_GOAL := help
.PHONY: help up down logs ps build migrate revision downgrade test lint format \
        dvf-import collect dashboard backup restore shell psql adminer

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Démarre toute la stack en arrière-plan
	$(COMPOSE) up -d

down: ## Arrête la stack (conserve les volumes)
	$(COMPOSE) down

logs: ## Suit les logs de tous les services
	$(COMPOSE) logs -f

ps: ## Liste les conteneurs
	$(COMPOSE) ps

build: ## (Re)construit les images
	$(COMPOSE) build

migrate: ## Applique les migrations Alembic (alembic upgrade head)
	$(COMPOSE) run --rm api alembic -c database/alembic.ini upgrade head

revision: ## Crée une migration autogénérée : make revision m="message"
	$(COMPOSE) run --rm api alembic -c database/alembic.ini revision --autogenerate -m "$(m)"

downgrade: ## Recule d'une migration
	$(COMPOSE) run --rm api alembic -c database/alembic.ini downgrade -1

test: ## Lance la suite de tests
	$(COMPOSE) run --rm -e DATABASE_URL=postgresql+psycopg://reif:reif@db:5432/reif api pytest

lint: ## Vérifie le style (ruff)
	$(COMPOSE) run --rm api ruff check .

format: ## Formate le code (ruff format)
	$(COMPOSE) run --rm api ruff format .

dvf-import: ## Importe DVF pour un département : make dvf-import DEP=33
	$(COMPOSE) run --rm worker python -m pipelines.dvf.run --dep $(DEP)

collect: ## Lance une passe de collecte d'annonces (discovery + refresh)
	$(COMPOSE) run --rm worker python -m collectors.run

dashboard: ## Ouvre le dashboard (démarre api + dashboard)
	$(COMPOSE) up -d api dashboard
	@echo "Dashboard : http://localhost:8501   |   API : http://localhost:8000/docs"

adminer: ## Démarre Adminer (inspection SQL, profil dev)
	$(COMPOSE) --profile dev up -d adminer
	@echo "Adminer : http://localhost:8080  (système PostgreSQL, serveur db, base reif)"

backup: ## Sauvegarde datée de PostgreSQL dans backups/
	@mkdir -p backups
	$(COMPOSE) exec -T db pg_dump -U reif -Fc reif > backups/$(DATE)_database.dump
	@echo "Backup écrit : backups/$(DATE)_database.dump"

restore: ## Restaure un backup : make restore FILE=backups/2027-01-01_database.dump
	@test -n "$(FILE)" || (echo "Usage: make restore FILE=backups/<date>_database.dump" && exit 1)
	$(COMPOSE) exec -T db pg_restore -U reif -d reif --clean --if-exists < $(FILE)
	@echo "Restauré depuis $(FILE)"

shell: ## Shell dans le conteneur api
	$(COMPOSE) run --rm api bash

psql: ## Console psql sur la base
	$(COMPOSE) exec db psql -U reif -d reif
