SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON_BIN ?= python3.12
VENV ?= .venv
BIN := $(VENV)/bin
DBT_DIR := dbt/marketplace_analytics
COMPOSE := docker compose
AIRFLOW_COMPOSE := $(COMPOSE) --profile airflow
AIRFLOW_VERSION := 3.3.2
AIRFLOW_CONSTRAINTS := https://raw.githubusercontent.com/apache/airflow/constraints-$(AIRFLOW_VERSION)/constraints-3.12.txt
AIRFLOW_VENV ?= .venv-airflow

# Load local settings so host-side commands reach the Dockerized PostgreSQL.
ifneq (,$(wildcard .env))
include .env
export
endif

# dbt parse needs credentials to render the profile but never connects.
DBT_PARSE_ENV := DATAFORGE_DB_USER=$${DATAFORGE_DB_USER:-parse_only} \
	DATAFORGE_DB_PASSWORD=$${DATAFORGE_DB_PASSWORD:-parse_only}

.PHONY: help
help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Setup -------------------------------------------------------------------

.PHONY: install
install: ## Create the virtualenv and install the project with dbt, dev, and docs extras
	$(PYTHON_BIN) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install --constraint constraints.txt -e ".[dbt,dev,docs]"

.PHONY: env
env: ## Create .env from .env.example if it does not exist
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "Created .env; replace the placeholder values")

# --- Data and pipeline (host) ------------------------------------------------

.PHONY: generate-data
generate-data: ## Generate the deterministic synthetic dataset into data/source
	$(BIN)/dataforge generate-data

.PHONY: generate-defects
generate-defects: ## Generate a dataset with injected defects into data/source_defects
	$(BIN)/dataforge generate-data --inject-defects --output-dir data/source_defects

.PHONY: init-db
init-db: ## Create raw and audit schemas in PostgreSQL
	$(BIN)/dataforge init-db

.PHONY: run-pipeline
run-pipeline: ## Run every stage locally without Airflow (needs PostgreSQL)
	$(BIN)/dataforge run-pipeline

.PHONY: demo-defects
demo-defects: generate-defects ## Run the pipeline on the defect dataset to see quarantine and reports
	DATAFORGE_SOURCE_DIR=data/source_defects $(BIN)/dataforge run-pipeline --run-id manual__defects_demo

# --- dbt -----------------------------------------------------------------------

.PHONY: dbt-parse
dbt-parse: ## Parse the dbt project (no database connection needed)
	$(DBT_PARSE_ENV) $(BIN)/dbt parse --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

.PHONY: dbt-seed
dbt-seed: ## Load dbt seeds
	$(BIN)/dataforge dbt seed

.PHONY: dbt-run
dbt-run: ## Build dbt models
	$(BIN)/dataforge dbt run

.PHONY: dbt-test
dbt-test: ## Run dbt data tests
	$(BIN)/dataforge dbt test

.PHONY: dbt-build
dbt-build: ## Seed, run, and test dbt in dependency order
	$(BIN)/dataforge dbt build

.PHONY: dbt-docs
dbt-docs: ## Generate dbt documentation into the dbt target directory
	$(BIN)/dataforge dbt docs -- generate

# --- Quality -------------------------------------------------------------------

.PHONY: lint
lint: ## Lint Python (ruff) and SQL (sqlfluff)
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	$(BIN)/sqlfluff lint $(DBT_DIR) sql

.PHONY: format
format: ## Auto-format Python and SQL
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .
	$(BIN)/sqlfluff fix $(DBT_DIR) sql

.PHONY: test
test: ## Run fast unit tests
	$(BIN)/pytest

.PHONY: test-integration
test-integration: ## Run integration tests against PostgreSQL (uses a separate test database)
	$(BIN)/pytest -m integration

.PHONY: airflow-venv
airflow-venv: ## Create a separate virtualenv with Airflow for DAG tests
	$(PYTHON_BIN) -m venv $(AIRFLOW_VENV)
	$(AIRFLOW_VENV)/bin/pip install --upgrade pip
	$(AIRFLOW_VENV)/bin/pip install "apache-airflow==$(AIRFLOW_VERSION)" pandas pytest --constraint $(AIRFLOW_CONSTRAINTS)
	$(AIRFLOW_VENV)/bin/pip install --no-deps -e .

.PHONY: test-dag
test-dag: ## Run DAG structure tests (requires `make airflow-venv`)
	$(AIRFLOW_VENV)/bin/pytest tests/dags -m airflow -p no:cacheprovider

.PHONY: ci
ci: lint test dbt-parse ## Run the checks that CI runs without a database

# --- Docker ----------------------------------------------------------------------

.PHONY: build
build: ## Build the Airflow image with the pipeline and dbt
	$(AIRFLOW_COMPOSE) build

.PHONY: db-up
db-up: ## Start PostgreSQL only
	$(COMPOSE) up -d --wait postgres

.PHONY: up
up: ## Start PostgreSQL and Airflow (UI on http://localhost:$${AIRFLOW_HOST_PORT:-8080})
	$(AIRFLOW_COMPOSE) up -d --build --wait

.PHONY: down
down: ## Stop all containers (data volumes are kept)
	$(AIRFLOW_COMPOSE) down

.PHONY: ps
ps: ## Show container status and health
	$(AIRFLOW_COMPOSE) ps -a

.PHONY: logs
logs: ## Follow logs of all services
	$(AIRFLOW_COMPOSE) logs -f --tail=100

.PHONY: psql
psql: ## Open a psql shell on the warehouse database
	$(COMPOSE) exec postgres psql -U "$(DATAFORGE_DB_USER)" -d "$(DATAFORGE_DB_NAME)"

.PHONY: trigger
trigger: ## Trigger the Airflow DAG once
	$(AIRFLOW_COMPOSE) exec airflow-scheduler airflow dags unpause marketplace_pipeline
	$(AIRFLOW_COMPOSE) exec airflow-scheduler airflow dags trigger marketplace_pipeline

.PHONY: reset
reset: ## Remove containers, volumes, generated data, and reports
	$(AIRFLOW_COMPOSE) down -v --remove-orphans
	rm -rf data/source data/source_defects data/reports

# --- Documentation ----------------------------------------------------------------

.PHONY: docs-images
docs-images: ## Render documentation images from the project and the warehouse
	$(BIN)/python scripts/render_docs_images.py
