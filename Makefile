# Aura — local single-user AI-native development center.

SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help bootstrap install migrate backend web up down containers-down status db-admin purge-volumes infra-down rag-up rag-down rag-logs actions-up test lint check smoke

AURA_VOLUMES = aura_aura_pg_data aura_aura_gitea_data aura_aura_runner_data
RAGFLOW_VOLUMES = ragflow_esdata01 ragflow_osdata01 ragflow_infinity_data \
	ragflow_serenedb_data ragflow_ob_data ragflow_seekdb_data \
	ragflow_vastbase_data ragflow_mysql_data ragflow_minio_data \
	ragflow_redis_data ragflow_kvrocks_data ragflow_tei_data \
	ragflow_kibana_data ragflow_nats_data ragflow_clickhouse_data ragflow_logs

help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

bootstrap: ## Generate .env, start PostgreSQL/Gitea, create the admin and token.
	./scripts/bootstrap.sh

install: ## Install backend and frontend dependencies.
	cd backend && uv sync
	cd frontend && pnpm install

migrate: ## Apply database migrations.
	cd backend && uv run python -m aura.migrate upgrade head

backend: migrate ## Run the backend in the foreground (http://127.0.0.1:8000).
	cd backend && uv run uvicorn aura.main:app --reload --host 127.0.0.1 --port 8000

web: ## Run the frontend in the foreground (http://127.0.0.1:5173).
	cd frontend && pnpm dev --host 127.0.0.1 --port 5173

up: bootstrap install rag-up ## Bootstrap, start RAGFlow, and run backend + frontend.
	./scripts/dev.sh start
	@echo "Aura is running at http://127.0.0.1:5173"
	@echo "RAGFlow is starting at http://127.0.0.1:8080 (API http://127.0.0.1:9380)"

down: ## Stop backend and frontend (containers keep running).
	./scripts/dev.sh stop

containers-down: ## Stop all Aura and RAGFlow containers (volumes persist).
	docker compose --profile '*' down
	docker compose --project-directory infra/ragflow -f infra/ragflow/docker-compose.yml --profile '*' down

status: ## Show application and container status.
	./scripts/dev.sh status
	@docker compose ps

db-admin: ## Start the pgweb database browser (http://127.0.0.1:8081).
	docker compose up -d db-admin

purge-volumes: ## Delete all Aura/RAGFlow named volumes (irreversible; prompts).
	@vols="$(AURA_VOLUMES) $(RAGFLOW_VOLUMES)"; \
	printf 'This will permanently DELETE these Aura/RAGFlow named volumes:\n'; \
	for v in $$vols; do printf '  - %s\n' "$$v"; done; \
	printf '\nDatabase contents, Gitea repositories, RAGFlow datasets, and run data will be lost.\n'; \
	printf 'Unrelated Docker volumes are not touched.\n'; \
	printf "Type 'DELETE' to continue: "; \
	read answer; \
	if [ "$$answer" != "DELETE" ]; then printf 'Aborted.\n'; exit 1; fi; \
	./scripts/dev.sh stop || true; \
	docker compose --profile '*' down -v --remove-orphans; \
	docker compose --project-directory infra/ragflow -f infra/ragflow/docker-compose.yml --profile '*' down -v --remove-orphans; \
	for v in $$vols; do docker volume rm -f "$$v" >/dev/null 2>&1 || true; done; \
	printf 'Aura/RAGFlow named volumes deleted.\n'

infra-down: containers-down ## Stop all Docker containers (alias of containers-down).

rag-up: ## Start the RAGFlow v1.0.0-rc2 stack.
	@test -f infra/ragflow/.env || cp infra/ragflow/.env.example infra/ragflow/.env
	docker compose --project-directory infra/ragflow -f infra/ragflow/docker-compose.yml up -d

rag-down: ## Stop the RAGFlow stack (volumes persist).
	@if [ -f infra/ragflow/docker-compose.yml ]; then \
		docker compose --project-directory infra/ragflow -f infra/ragflow/docker-compose.yml --profile '*' down; \
	fi

rag-logs: ## Follow RAGFlow server logs.
	docker compose --project-directory infra/ragflow -f infra/ragflow/docker-compose.yml logs -f ragflow-cpu

actions-up: ## Start the optional Gitea Actions runner (needs AURA_RUNNER_TOKEN).
	docker compose --profile actions up -d runner

test: ## Run backend tests and frontend typecheck.
	cd backend && uv run pytest -q
	cd frontend && pnpm typecheck

lint: ## Lint the backend and frontend.
	cd backend && uv run ruff check src tests
	cd frontend && pnpm lint

check: lint test ## Everything CI would run.
	cd frontend && pnpm build

smoke: ## Live end-to-end smoke test (requires Docker + Claude Code).
	./scripts/smoke.sh

.PHONY: smoke
