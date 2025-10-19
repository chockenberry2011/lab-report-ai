SHELL := /bin/bash
.ONESHELL:

.PHONY: help up down build rebuild clean logs status fresh shell-api api-restart shell-worker shell-extractor shell-trainer up-airflow down-airflow

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@egrep '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up: ## Start all core services (redis, api, worker, extractor, trainer, ui, labelstudio)
	docker compose up -d redis api worker extractor trainer ui labelstudio

down: ## Stop all services
	docker compose down

build: ## Build all services
	# Build UI first to maximize npm ci cache for subsequent builds
	$(MAKE) ui-check-scripts
	docker compose build ui
	docker compose build

rebuild: ## Rebuild all services from scratch
	docker compose build --no-cache

fresh: ## Stop, rebuild, and start all services (fresh deployment)
	@echo "🔄 Stopping all services..."
	$(MAKE) down
	@echo "🔨 Building all services..."
	$(MAKE) build
	@echo "🚀 Starting all services..."
	$(MAKE) up
	@echo "✅ Fresh deployment complete!"

clean: ## Stop services and remove volumes
	docker compose down -v
	docker system prune -f

logs: ## Show logs from all services
	docker compose logs -f

status: ## Show status of all services
	docker compose ps

up-airflow: ## Start all services including Airflow
	docker compose --profile airflow up -d

down-airflow: ## Stop all services including Airflow
	docker compose --profile airflow down

shell-api: ## Open shell in API service
	docker compose exec api /bin/bash

api-restart: ## Restart API service
	docker compose build api
	docker compose up -d api

shell-worker: ## Open shell in worker service
	docker compose exec worker /bin/bash

shell-extractor: ## Open shell in extractor service
	docker compose exec extractor /bin/bash

shell-trainer: ## Open shell in trainer service
	docker compose exec trainer /bin/bash

build-extractor: ## Build extractor service
	docker compose build extractor

up-extractor: ## Start extractor service
	docker compose up -d extractor

# Extractor-specific commands
test-extractor: ## Run extractor unit tests
	docker compose exec extractor python -m pytest test_extractor.py -v

demo-extractor: ## Run extractor demo
	docker compose exec extractor python demo.py

extract-text: ## Extract text from PDF (usage: make extract-text PDF=/data/file.pdf)
	docker compose exec extractor python -m services.extractor extract_text $(PDF)

extract-lines: ## Extract lines from PDF (usage: make extract-lines PDF=/data/file.pdf)
	docker compose exec extractor python -m services.extractor extract_lines $(PDF)

# Trainer-specific commands
trainer-selftest: ## Test that all trainer modules can be imported
	docker compose exec trainer python -m services.trainer.selftest
train-roles: ## Train line role classifier (usage: make train-roles DATA=/data/training.json)
	docker compose exec trainer python trainer.py cli train $(DATA)

eval-roles: ## Evaluate role classifier
	docker compose exec trainer python trainer.py cli eval --interactive

sample-roles-data: ## Generate sample training data
	docker compose exec trainer python trainer.py cli sample --output /data/sample_roles.json

classify-roles: ## Apply role classification to extractor output (usage: make classify-roles INPUT=/data/outbox/file.lines.json)
	docker compose exec trainer python trainer.py cli integrate --input $(INPUT)

roles-sanity: ## Sanity-check roles model output (usage: make roles-sanity FILE=/data/outbox/file.lines.json)
	docker compose exec worker python -m services.trainer.roles.dev_sanity $(FILE) --model-dir /models/roles

# TEST_ROW token classifier commands
sample-testrow-data: ## Generate sample TEST_ROW training data
	docker compose exec trainer python trainer.py cli sample-testrow --output /data/sample_testrow.json

train-testrow: ## Train TEST_ROW token classifier (usage: make train-testrow DATA=/data/training.json)
	docker compose exec trainer python trainer.py cli train-testrow $(DATA)

eval-testrow: ## Evaluate TEST_ROW classifier interactively
	docker compose exec trainer python trainer.py cli eval-testrow --interactive

parse-testrow: ## Parse TEST_ROW line into tokens (usage: make parse-testrow TEXT="Glucose 95 mg/dL 70-100")
	docker compose exec trainer python -c "from testrow.rule_splitter import RuleBasedSplitter; s = RuleBasedSplitter(); print('Rule-based:', s.parse_to_bio_labels('$(TEXT)'))"

# Header extraction commands
test-headers: ## Run header extractor unit tests
	docker compose exec trainer python trainer.py cli test-headers

demo-headers: ## Run header extraction demo
	docker compose exec trainer python trainer.py cli demo-headers

extract-headers: ## Extract headers from classified lines (usage: make extract-headers - interactive)
	docker compose exec trainer python -c "from headers import HeaderExtractionService; s = HeaderExtractionService(); print('Header extraction service ready')"

process-document: ## Process complete document with all extractors
	docker compose exec trainer python -c "print('Use Celery task: process_full_document')"

# Development helpers
dev-setup: ## Initial setup for development
	@echo "Creating required directories..."
	mkdir -p data models orchestrator/dags
	@echo "Building services..."
	$(MAKE) build
	@echo "Starting services..."
	$(MAKE) up
	@echo ""
	@echo "Services available at:"
	@echo "  API: http://localhost:8000"
	@echo "  UI: http://localhost:3000"
	@echo "  Label Studio: http://localhost:8080"
	@echo "  Redis: localhost:6379"
		@echo ""
		@echo "To include Airflow, run: make up-airflow"

# ----- lab-ai non-conflicting helpers (do not duplicate up/down/build) -----
.PHONY: worker-restart roles.train roles.eval testrow.train testrow.eval reprocess.one

worker-restart:
	@docker compose restart worker

# Train/eval LINE ROLES (expects /data/training/roles/roles.aug.json to exist)
roles.train:
	@set -euo pipefail
	@docker compose exec -T trainer sh -lc '\
	  python -m services.trainer.roles.train_roles \
	    "/data/training/roles/roles.aug.json" \
	    --output-dir "/models/roles" \
	    --model-type logistic \
	    --embedding-model tfidf \
	    --test-size 0.5 \
	    --random-seed 13 \
	'

roles.eval:
	@set -euo pipefail
	@docker compose exec -T trainer sh -lc '\
	  python -m services.trainer.roles.eval_roles \
	    "/data/training/roles/roles.aug.json" \
	    --model-dir "/models/roles" \
	    --embedding-model tfidf || true \
	'

# Train/eval TEST ROW tagger (expects train/dev JSONL)
testrow.train:
	@set -euo pipefail
	@docker compose exec -T trainer sh -lc '\
	  python -m services.trainer.testrow.train_testrow \
	    /data/training/testrow/train.jsonl \
	    --dev /data/training/testrow/dev.jsonl \
	    --output-dir /models/testrow \
	'

testrow.eval:
	@set -euo pipefail
	@docker compose exec -T trainer sh -lc '\
	  python -m services.trainer.testrow.eval_testrow \
	    /data/training/testrow/dev.jsonl \
	    --model-dir /models/testrow || true \
	'

# Reprocess a single PDF by basename: make reprocess.one FILE=<uuid-without-.pdf>
reprocess.one:
	@set -euo pipefail
	@if [ -z "$$FILE" ]; then echo "Usage: make reprocess.one FILE=<basename>"; exit 2; fi
	@docker compose exec -T extractor sh -lc '\
	  python -m services.extractor.cli extract_lines "/data/inbox/$$FILE.pdf" \
	'
	@docker compose exec -T worker sh -lc '\
	python - <<- PY || true
	import json, pathlib
	b="$$FILE"
	for suf in ("01a_lines_merged","02_roles","03_compose"):
	    p=f"/data/outbox/{b}.{suf}.debug.json"
	    if pathlib.Path(p).exists():
	        d=json.load(open(p))
	        print(suf, "ok;", "keys:", list(d)[:5])
	    else:
	        print(suf, "missing")
	PY
	'

debug-report: ## quick peek at last processed job's intermediary debug artifacts
	@set -euo pipefail
	@docker compose exec -T worker sh -lc '\
	python - <<- PY
	import os, json, pathlib
	from glob import glob
	b = sorted([p for p in os.listdir("/data/outbox") if p.endswith(".json")])[-1].split(".json")[0]
	for suf in ("01_lines","02_roles","03_compose"):
	    p=f"/data/outbox/{b}.{suf}.debug.json"
	    if pathlib.Path(p).exists():
	        d=json.load(open(p))
	        print(suf, "ok;", "keys:", list(d)[:5])
	    else:
	        print(suf, "missing")
	PY
	'

debug-proba: ## probe probability shape helper
	@docker compose exec -T worker python3 -c "from services.worker.composer.scoring import _lookup_line_proba; print('_lookup (dict):', _lookup_line_proba({3:{'TEST_ROW':0.9}}, 3)); print('_lookup (aligned list):', _lookup_line_proba([None,None,{'TEST_ROW':0.5}], 2)); print('_lookup (list of dicts):', _lookup_line_proba([{'line_number':7,'distribution':{'TEST_ROW':0.8}}], 7))"
# UI lockfile guard before UI Docker build
.PHONY: ui-check-lock ui-build up-ui-verbose

ui-check-lock:
	@cd ui && npm run check:lock

ui-check-scripts:
	@cd ui && npm run check:scripts

ui-build: ui-check-lock ui-check-scripts
	@echo "Building UI image..."
	# Put your UI docker build command here if separate, else composed in compose.yml
	# Example:
	# docker build -f ui/Dockerfile -t lab-ai-ui:latest ui

up-ui-verbose: ## Build and start UI with verbose output and fresh cache
	docker compose up -d ui
	sleep 2
	docker compose ps
	docker compose exec ui wget -qO- http://localhost/health || true
	docker compose exec ui wget -qO- http://localhost/api/health || true

# ---- Corrections triage helper ----
.PHONY: corrections.triage
corrections.triage: ## Triage corrections file (usage: make corrections.triage ID=<result_id> [FIX=1] [RESULTS_DIR=/data/results] [DATA_ROOT=/data])
	@set -euo pipefail
	@if [ -z "${ID:-}" ]; then echo "Usage: make corrections.triage ID=<result_id> [FIX=1] [RESULTS_DIR=/data/results] [DATA_ROOT=/data]"; exit 2; fi
	@args=""
	@if [ -n "${RESULTS_DIR:-}" ]; then args="$$args --results-dir '$(RESULTS_DIR)'"; elif [ -n "${DATA_ROOT:-}" ]; then args="$$args --data-root '$(DATA_ROOT)'"; fi
	@if [ "${FIX:-0}" = "1" ]; then args="$$args --fix"; fi
	@docker compose exec -T api python /services/api/scripts/corrections_triage.py "$(ID)" $$args

# ---- Corrections normalize/apply helper ----
.PHONY: corrections.normalize corrections.apply
corrections.normalize: ## Normalize corrections.json across all results (usage: make corrections.normalize [DRYRUN=1])
	@set -euo pipefail
	@args=""
	@if [ "${DRYRUN:-0}" = "1" ]; then args="$$args --dry-run"; fi
	@docker compose exec -T api python /services/api/scripts/corrections_normalize.py $$args

.PHONY: check-imports
check-imports: ## Audit backend imports to prevent 'api.api' path
	@set -euo pipefail
	@bash services/api/scripts/check_imports.sh

corrections.apply: ## Normalize and apply to canonical docs (usage: make corrections.apply [DRYRUN=1])
	@set -euo pipefail
	@args="--apply"
	@if [ "${DRYRUN:-0}" = "1" ]; then args="$$args --dry-run"; fi
	@docker compose exec -T api python /services/api/scripts/corrections_normalize.py $$args
