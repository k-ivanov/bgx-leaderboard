# BGX Navigation Dashboard — Makefile
#
# Common workflows. Run `make` or `make help` to see every target with a
# one-line description. Targets are grouped by the emoji prefix below:
#   🚀 start / stop          local dev
#   🗄  database             postgres lifecycle + seeding
#   🧪 test                  pytest + astro check
#   🔧 build / deploy        production image + release helpers
#   🧹 clean                 remove caches + build output
#   🩺 smoke                 quick healthchecks against a running instance

# ----------------------------------------------------------------------------
# Config (override with `make VAR=value <target>`)
# ----------------------------------------------------------------------------
VENV            ?= .venv
PYTHON          ?= python3
PORT            ?= 5001
HOST            ?= 0.0.0.0
FRONTEND_PORT   ?= 4321
IMAGE_TAG       ?= bgx-dashboard:latest
API_URL         ?= http://localhost:$(PORT)
COMPOSE         ?= docker compose

# Use an absolute path so cd'ing around doesn't confuse us.
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND  := $(ROOT)/backend
FRONTEND := $(ROOT)/frontend

# Colors for the help banner (fall back to plain text on dumb terminals).
ifneq ($(TERM),)
    C_RESET := \033[0m
    C_BOLD  := \033[1m
    C_DIM   := \033[2m
    C_GOLD  := \033[38;5;214m
else
    C_RESET :=
    C_BOLD  :=
    C_DIM   :=
    C_GOLD  :=
endif

.DEFAULT_GOAL := help

# ============================================================================
# Help
# ============================================================================

.PHONY: help
help: ## Show this help
	@printf "$(C_GOLD)$(C_BOLD)BGX Navigation Dashboard$(C_RESET) — make targets\n"
	@printf "  $(C_DIM)(override vars with \`make VAR=value target\`)$(C_RESET)\n\n"
	@awk 'BEGIN {FS = ":.*?## "} \
	      /^# ==+$$/ { inhdr=1; next } \
	      inhdr==1 && /^# / { sub(/^# /,""); printf "$(C_BOLD)%s$(C_RESET)\n", $$0; inhdr=2; next } \
	      inhdr==2 && /^# ==+$$/ { inhdr=0; next } \
	      /^[a-zA-Z0-9_.-]+:.*## / { printf "  $(C_GOLD)%-22s$(C_RESET) %s\n", $$1, $$2 } \
	      /^$$/ { inhdr=0 }' $(MAKEFILE_LIST)
	@printf "\n"

# ============================================================================
# 🚀 Start / stop — local dev
# ============================================================================

.PHONY: install
install: $(VENV)/.installed-backend $(FRONTEND)/node_modules ## Install backend + frontend deps (one-time setup)
	@printf "$(C_GOLD)✓$(C_RESET) backend + frontend deps installed\n"

$(VENV)/.installed-backend: $(BACKEND)/pyproject.toml
	@printf "$(C_GOLD)→$(C_RESET) creating venv and installing backend deps…\n"
	@cd $(BACKEND) && $(PYTHON) -m venv $(VENV) && \
	  $(VENV)/bin/pip install -q --upgrade pip && \
	  $(VENV)/bin/pip install -q -e '.[dev]'
	@touch $@

$(FRONTEND)/node_modules: $(FRONTEND)/package.json $(FRONTEND)/package-lock.json
	@printf "$(C_GOLD)→$(C_RESET) installing frontend deps…\n"
	@cd $(FRONTEND) && npm install --no-audit --no-fund
	@touch $@

.PHONY: dev
dev: ## Run backend + frontend in the foreground (Ctrl-C stops both)
	@printf "$(C_GOLD)→$(C_RESET) starting dev stack. Ctrl-C to stop.\n"
	@$(MAKE) db-up
	@trap '$(MAKE) dev-stop' INT TERM EXIT; \
	  ($(MAKE) --no-print-directory dev-backend &) && \
	  ($(MAKE) --no-print-directory dev-frontend &) && \
	  wait

.PHONY: dev-backend
dev-backend: $(VENV)/.installed-backend ## Start FastAPI (uvicorn --reload) on :5001
	@cd $(BACKEND) && \
	  . $(VENV)/bin/activate && \
	  PORT=$(PORT) HOST=$(HOST) uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

.PHONY: dev-frontend
dev-frontend: $(FRONTEND)/node_modules ## Start Astro dev server on :4321 (proxies /api to backend)
	@cd $(FRONTEND) && npm run dev -- --port $(FRONTEND_PORT)

.PHONY: dev-stop
dev-stop: ## Kill local dev processes (backend + frontend)
	@pkill -f "uvicorn app.main:app" 2>/dev/null || true
	@pkill -f "astro dev"           2>/dev/null || true
	@printf "$(C_GOLD)✓$(C_RESET) dev processes stopped\n"

.PHONY: stop
stop: dev-stop db-down ## Stop everything local (dev processes + Postgres container)

# ============================================================================
# 🗄 Database — postgres + seeding
# ============================================================================

.PHONY: db-up
db-up: ## Start the local Postgres container (docker compose)
	@$(COMPOSE) up -d postgres
	@for i in $$(seq 1 30); do \
	   if docker exec bgx-postgres pg_isready -U bgx -d bgx >/dev/null 2>&1; then \
	     printf "$(C_GOLD)✓$(C_RESET) postgres healthy after %ss\n" $$i; exit 0; \
	   fi; sleep 1; \
	 done; \
	 printf "$(C_GOLD)✗$(C_RESET) postgres did not become ready within 30s\n" && exit 1

.PHONY: db-down
db-down: ## Stop the Postgres container (keeps the volume)
	@$(COMPOSE) stop postgres 2>&1 | tail -1
	@printf "$(C_GOLD)✓$(C_RESET) postgres stopped (data preserved)\n"

.PHONY: db-nuke
db-nuke: ## ⚠️ Drop postgres volume + recreate (destroys all data)
	@printf "$(C_GOLD)⚠$(C_RESET)  this will delete the bgx-pg-data volume. Press Enter to continue, Ctrl-C to abort.\n"
	@read _
	@$(COMPOSE) down -v postgres
	@$(MAKE) db-up

.PHONY: migrate
migrate: $(VENV)/.installed-backend db-up ## Apply all pending alembic migrations
	@cd $(BACKEND) && . $(VENV)/bin/activate && alembic upgrade head

.PHONY: seed
seed: seed-2025 ## Seed all available seasons (currently just 2025)

.PHONY: seed-2025
seed-2025: migrate ## Import the 2025 aggregate CSVs (idempotent — wipes + rebuilds 2025)
	@cd $(BACKEND) && . $(VENV)/bin/activate && $(PYTHON) -m scripts.import_2025

.PHONY: seed-2026-karnare
seed-2026-karnare: migrate ## Import the 2026 Kyrnare event for every category (idempotent)
	@cd $(BACKEND) && . $(VENV)/bin/activate && \
	for cat_csv in scripts/seed_data/bgx-results-2026/karnare_2026_navigation_*.csv; do \
	  cat=$$(basename "$$cat_csv" | sed -E 's/karnare_2026_navigation_([a-z_]+)\.csv/\1/; s/standart/standard/; s/seniors_40plus/seniors_40/; s/seniors_50plus/seniors_50/'); \
	  name=$$(echo "$$cat" | sed -E 's/_/ /g; s/\b./\U&/g'); \
	  printf "  → %s\n" "$$cat"; \
	  $(PYTHON) -m scripts.import_event \
	    --file "$$cat_csv" \
	    --season 2026 \
	    --category "$$cat" --category-name "$$name" \
	    --event karnare --event-name "Kyrnare" --event-date 2026-04-18; \
	done

.PHONY: import-event
import-event: ## Import one (race, category) CSV. Usage: make import-event FILE=... CAT=expert CAT_NAME="Expert" EVENT=karnare EVENT_NAME="Kyrnare" DATE=2026-04-18 YEAR=2026
	@if [ -z "$(FILE)" ] || [ -z "$(CAT)" ] || [ -z "$(CAT_NAME)" ] || [ -z "$(EVENT)" ] || [ -z "$(EVENT_NAME)" ] || [ -z "$(DATE)" ]; then \
	  printf "Usage: make import-event FILE=<csv> CAT=expert CAT_NAME=\"Expert\" EVENT=karnare EVENT_NAME=\"Kyrnare\" DATE=2026-04-18 [YEAR=2026]\n"; \
	  exit 2; \
	fi
	@cd $(BACKEND) && . $(VENV)/bin/activate && $(PYTHON) -m scripts.import_event \
	  --file "$(FILE)" \
	  --season "$(or $(YEAR),2026)" \
	  --category "$(CAT)" --category-name "$(CAT_NAME)" \
	  --event "$(EVENT)" --event-name "$(EVENT_NAME)" --event-date "$(DATE)"

.PHONY: db-shell
db-shell: ## Open a psql shell against the local Postgres
	@docker exec -it bgx-postgres psql -U bgx -d bgx

.PHONY: db-reset
db-reset: db-nuke migrate seed ## Nuke + recreate the DB and seed 2025

# ============================================================================
# 🧪 Test + type-check
# ============================================================================

.PHONY: test
test: $(VENV)/.installed-backend db-up ## Run the full backend pytest suite (64 tests)
	@cd $(BACKEND) && . $(VENV)/bin/activate && \
	  $(PYTHON) -m pytest -p no:cacheprovider -o "pythonpath=."

.PHONY: test-fast
test-fast: $(VENV)/.installed-backend ## Run only DB-free backend tests (no Postgres required)
	@cd $(BACKEND) && . $(VENV)/bin/activate && \
	  $(PYTHON) -m pytest --noconftest -p no:cacheprovider --override-ini="addopts=" \
	    -o "pythonpath=." \
	    tests/test_slug.py tests/test_mount_order.py tests/test_cors.py

.PHONY: check-frontend
check-frontend: $(FRONTEND)/node_modules ## Run Astro type-check (`astro check`)
	@cd $(FRONTEND) && npm run check

.PHONY: check
check: test check-frontend ## Full check — pytest + astro check

.PHONY: gen-api-types
gen-api-types: $(FRONTEND)/node_modules ## Regenerate frontend TS types from /api/openapi.json
	@printf "$(C_GOLD)→$(C_RESET) regenerating TS types against $(API_URL)/api/openapi.json…\n"
	@curl -fsS "$(API_URL)/health" > /dev/null || { \
	  printf "$(C_GOLD)✗$(C_RESET) backend not reachable at $(API_URL). Run \`make dev-backend\` first.\n"; \
	  exit 1; \
	}
	@cd $(FRONTEND) && npm run generate:api-types

# ============================================================================
# 🔧 Build + deploy
# ============================================================================

.PHONY: build-frontend
build-frontend: $(FRONTEND)/node_modules ## Astro static build → frontend/dist/ (needs backend reachable)
	@curl -fsS "$(API_URL)/health" > /dev/null || { \
	  printf "$(C_GOLD)✗$(C_RESET) backend not reachable at $(API_URL). Run \`make dev-backend\` first.\n"; \
	  exit 1; \
	}
	@cd $(FRONTEND) && API_URL=$(API_URL) npm run build

.PHONY: build
build: ## Build the production Docker image (orchestrates API + Docker)
	@./scripts/build-image.sh $(IMAGE_TAG)

.PHONY: rebuild
rebuild: clean-dist build ## Clean the previous dist + rebuild the production image

.PHONY: run
run: ## Run the prod image locally against local Postgres on :5001
	@docker rm -f bgx-run 2>/dev/null || true
	@docker run -d --rm --name bgx-run \
	    -p $(PORT):5001 \
	    -e DATABASE_URL=postgresql+psycopg2://bgx:bgx@host.docker.internal:5432/bgx \
	    $(IMAGE_TAG)
	@printf "$(C_GOLD)→$(C_RESET) container running. Logs:  docker logs -f bgx-run\n"
	@printf "                              Stop:  make run-stop\n"

.PHONY: run-stop
run-stop: ## Stop the locally-running prod image
	@docker stop bgx-run 2>/dev/null || true
	@printf "$(C_GOLD)✓$(C_RESET) container stopped\n"

# ============================================================================
# 🩺 Smoke tests
# ============================================================================

.PHONY: health
health: ## curl /health (uses API_URL)
	@curl -sw "  [%{http_code}]\n" $(API_URL)/health

.PHONY: smoke
smoke: ## Hit the headline endpoints and print a brief report
	@printf "$(C_BOLD)/health$(C_RESET)\n"
	@curl -sw "  [%{http_code}]\n" $(API_URL)/health
	@printf "\n$(C_BOLD)/api/seasons$(C_RESET)\n"
	@curl -s $(API_URL)/api/seasons | $(PYTHON) -m json.tool | head -8
	@printf "\n$(C_BOLD)/api/seasons/2025/standings/expert (leader)$(C_RESET)\n"
	@curl -s $(API_URL)/api/seasons/2025/standings/expert | $(PYTHON) -c "import json,sys; d=json.load(sys.stdin); r=d['rows'][0]; print(f'  #{r[\"rider\"][\"race_number\"]} {r[\"rider\"][\"first_name\"]} {r[\"rider\"][\"last_name\"]} — {r[\"total_points\"]} pts')"
	@printf "\n$(C_BOLD)/api/nonexistent (should be JSON 404)$(C_RESET)\n"
	@curl -sw "  [%{http_code} %{content_type}]\n" $(API_URL)/api/nonexistent

.PHONY: logs
logs: ## Tail dashboard container logs
	@docker logs -f bgx-run 2>&1 | tail -100 || docker logs -f bgx-dashboard 2>&1 | tail -100

# ============================================================================
# 🧹 Cleanup
# ============================================================================

.PHONY: clean
clean: clean-cache clean-dist ## Remove caches + build output (keeps venv, keeps DB)
	@printf "$(C_GOLD)✓$(C_RESET) caches + dist cleaned\n"

.PHONY: clean-cache
clean-cache: ## Remove __pycache__, .pytest_cache, .astro, .mypy_cache
	@find $(BACKEND) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find $(BACKEND) -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@rm -rf $(FRONTEND)/.astro $(FRONTEND)/.mypy_cache 2>/dev/null || true

.PHONY: clean-dist
clean-dist: ## Remove frontend/dist/
	@rm -rf $(FRONTEND)/dist

.PHONY: clean-venv
clean-venv: ## Remove backend virtualenv
	@rm -rf $(BACKEND)/$(VENV)

.PHONY: clean-all
clean-all: clean clean-venv ## Nuke caches + venv + node_modules (leaves DB data)
	@rm -rf $(FRONTEND)/node_modules
	@printf "$(C_GOLD)✓$(C_RESET) everything derived cleaned (DB + source intact)\n"
