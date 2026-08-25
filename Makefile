.PHONY: help sync test lint fix build dev up down logs clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

sync: ## Install dependencies into .venv (from lockfile)
	uv sync

install: sync ## Alias for sync

test: ## Run tests
	uv run pytest

lint: ## Lint source and tests
	uv run ruff check src tests

fix: ## Auto-fix lint issues
	uv run ruff check src tests --fix

dev: ## Run the app locally
	uv run python src/app.py

build: ## Build the Docker image
	docker build -t waterpijl:local .

up: ## Start all containers (app + email sidecar)
	docker compose up -d

down: ## Stop and remove containers
	docker compose down

logs: ## Tail logs for all services
	docker compose logs -f

clean: ## Remove the venv
	rm -rf .venv