# ai-agent-saas-template — top-level developer interface.
#
# Every target here is a thin wrapper. The underlying tools (pnpm, uv, docker,
# terraform) remain directly usable; nothing is hidden behind the Makefile.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

WEB      := apps/web
BACKEND  := services/backend
CONTRACTS := packages/contracts
# The AWS path lives under advanced/ and is not the default (ADR-009).
TERRAFORM_DIR := advanced/infra/terraform

PNPM := pnpm
UV   := uv

# ENV selects a Terraform/deployment environment. Deployment targets refuse to
# run without it rather than silently defaulting to something dangerous.
ENV ?=

-include .env
export

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

define require_env
	@if [ -z "$(ENV)" ]; then \
		echo "ERROR: ENV is required. Example: make $@ ENV=dev"; exit 1; \
	fi
	@case "$(ENV)" in \
		local|dev|staging|prod) ;; \
		*) echo "ERROR: ENV must be one of: local dev staging prod (got '$(ENV)')"; exit 1 ;; \
	esac
endef

define require_tool
	@command -v $(1) >/dev/null 2>&1 || { \
		echo "ERROR: '$(1)' is not installed. $(2)"; exit 1; }
endef

.PHONY: help
help: ## Show this help
	@echo "ai-agent-saas-template"
	@echo ""
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

.PHONY: install
install: ## Install all JavaScript and Python dependencies
	$(call require_tool,pnpm,Install with: corepack enable pnpm)
	$(call require_tool,uv,Install with: curl -LsSf https://astral.sh/uv/install.sh | sh)
	$(PNPM) install
	$(UV) sync --project $(CONTRACTS)
	$(UV) sync --project $(BACKEND)
	@echo ""
	@echo "Next: cp .env.example .env && make infra-up && make dev"

.PHONY: env
env: ## Create .env from .env.example if it does not exist
	@if [ -f .env ]; then echo ".env already exists; leaving it alone."; \
	else cp .env.example .env; echo "Created .env from .env.example"; fi

# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

.PHONY: dev
dev: ## Run web + backend together (Ctrl-C stops both)
	@./scripts/dev.sh

.PHONY: dev-stop
dev-stop: ## Free the development ports if a server was left running
	@./scripts/dev-stop.sh

.PHONY: web-dev
web-dev: ## Run the Next.js app on :3000
	$(PNPM) --filter web dev

.PHONY: backend-dev
backend-dev: ## Run the API + agent + MCP server on :8000
	cd $(BACKEND) && $(UV) run uvicorn asgi:app --reload --host 0.0.0.0 --port 8000

# ---------------------------------------------------------------------------
# Local infrastructure
# ---------------------------------------------------------------------------

.PHONY: infra-up
infra-up: ## Start Postgres and apply migrations
	docker compose up -d postgres
	@./scripts/wait-for-postgres.sh
	@$(MAKE) --no-print-directory db-migrate

.PHONY: infra-down
infra-down: ## Stop local infrastructure (keeps volumes)
	docker compose down

.PHONY: infra-reset
infra-reset: ## Destroy local infrastructure and volumes, then start clean
	docker compose down -v --remove-orphans
	@$(MAKE) --no-print-directory infra-up
	@$(MAKE) --no-print-directory seed

.PHONY: infra-logs
infra-logs: ## Tail local infrastructure logs
	docker compose logs -f

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

.PHONY: db-migrate
db-migrate: ## Apply Alembic migrations to the local database
	cd $(BACKEND) && $(UV) run alembic upgrade head

.PHONY: db-rollback
db-rollback: ## Roll back the most recent migration
	cd $(BACKEND) && $(UV) run alembic downgrade -1

.PHONY: db-migration
db-migration: ## Create a migration: make db-migration NAME="add plans table"
	@if [ -z "$(NAME)" ]; then echo 'ERROR: NAME is required. Example: make db-migration NAME="add plans table"'; exit 1; fi
	cd $(BACKEND) && $(UV) run alembic revision --autogenerate -m "$(NAME)"

.PHONY: contracts
contracts: ## Regenerate shared JSON Schema and TypeScript from the Pydantic contracts
	$(UV) run --project packages/contracts python packages/contracts/generate.py

.PHONY: contracts-check
contracts-check: ## Fail if the generated contracts are stale
	@$(MAKE) --no-print-directory contracts
	@if ! git diff --quiet -- packages/contracts/generated; then \
		echo "ERROR: generated contracts are stale. Run 'make contracts' and commit the result."; \
		git --no-pager diff --stat -- packages/contracts/generated; \
		exit 1; \
	fi

.PHONY: seed
seed: ## Load deterministic demo data into the local database
	cd $(BACKEND) && $(UV) run python -m app.seed

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

.PHONY: format
format: ## Format all code
	$(UV) run --project $(BACKEND) ruff format $(BACKEND) $(CONTRACTS) evals tests
	$(PNPM) --filter web format

.PHONY: format-check
format-check: ## Verify formatting without writing changes
	$(UV) run --project $(BACKEND) ruff format --check $(BACKEND) $(CONTRACTS) evals tests
	$(PNPM) --filter web exec prettier --check "src/**/*.{ts,tsx}"

.PHONY: lint
lint: ## Lint Python and TypeScript
	$(UV) run --project $(BACKEND) ruff check $(BACKEND) $(CONTRACTS) evals tests
	$(PNPM) --filter web lint

.PHONY: typecheck
typecheck: ## Type-check Python and TypeScript
	$(UV) run --project $(BACKEND) mypy $(BACKEND)
	$(PNPM) --filter web typecheck
	$(PNPM) --filter e2e typecheck

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

.PHONY: test-unit
test-unit: ## Unit + service + tool-contract tests (no external infrastructure)
	$(UV) run --project $(CONTRACTS) pytest $(CONTRACTS)/tests -q
	$(UV) run --project $(BACKEND) pytest $(BACKEND)/tests -q
	$(PNPM) --filter web test

.PHONY: test-integration
test-integration: ## Integration tests against local Postgres + MCP
	@./scripts/require-infra.sh
	$(UV) run --project $(BACKEND) pytest tests/integration -q

.PHONY: test-e2e
test-e2e: ## Playwright end-to-end tests against the local stack
	@./scripts/require-stack.sh
	$(PNPM) --filter e2e test

.PHONY: e2e-install
e2e-install: ## Install the Playwright browsers
	$(PNPM) --filter e2e exec playwright install --with-deps chromium

.PHONY: eval
eval: ## Run the agent evaluation suite
	$(UV) run --project $(BACKEND) python -m evals.run

.PHONY: test
test: test-unit test-integration test-e2e ## Full local test suite

.PHONY: check
check: format-check lint typecheck contracts-check test-unit ## Fast pre-push suite
	@echo ""
	@echo "Terraform is not checked here — it belongs to the advanced/ AWS path."
	@echo "Run 'make infra-check' if you are working on it."

# ---------------------------------------------------------------------------
# Terraform
# ---------------------------------------------------------------------------

.PHONY: terraform-fmt
terraform-fmt: ## Check Terraform formatting
	$(call require_tool,terraform,See https://developer.hashicorp.com/terraform/install)
	terraform fmt -check -recursive $(TERRAFORM_DIR)

.PHONY: terraform-fmt-write
terraform-fmt-write: ## Rewrite Terraform files to canonical format
	terraform fmt -recursive $(TERRAFORM_DIR)

.PHONY: terraform-validate
terraform-validate: ## Validate every Terraform environment
	$(call require_tool,terraform,See https://developer.hashicorp.com/terraform/install)
	@for e in local dev staging prod; do \
		echo "==> validating envs/$$e"; \
		terraform -chdir=$(TERRAFORM_DIR)/envs/$$e init -backend=false -input=false >/dev/null; \
		terraform -chdir=$(TERRAFORM_DIR)/envs/$$e validate; \
	done

.PHONY: terraform-init
terraform-init: ## Initialize Terraform: make terraform-init ENV=dev
	$(require_env)
	terraform -chdir=$(TERRAFORM_DIR)/envs/$(ENV) init -input=false

.PHONY: terraform-plan
terraform-plan: ## Plan Terraform changes: make terraform-plan ENV=dev
	$(require_env)
	terraform -chdir=$(TERRAFORM_DIR)/envs/$(ENV) init -input=false
	terraform -chdir=$(TERRAFORM_DIR)/envs/$(ENV) plan -input=false -out=tfplan

.PHONY: terraform-apply
terraform-apply: ## Apply Terraform changes: make terraform-apply ENV=dev
	$(require_env)
	@if [ "$(ENV)" = "prod" ] && [ "$(CONFIRM)" != "prod" ]; then \
		echo "ERROR: production apply requires CONFIRM=prod (CI uses a protected environment instead)."; exit 1; \
	fi
	terraform -chdir=$(TERRAFORM_DIR)/envs/$(ENV) apply -input=false tfplan

.PHONY: infra-check
infra-check: terraform-fmt terraform-validate ## Terraform formatting + validation

.PHONY: infra-local-apply
infra-local-apply: ## Apply the local Terraform env against LocalStack
	$(call require_tool,terraform,See https://developer.hashicorp.com/terraform/install)
	terraform -chdir=$(TERRAFORM_DIR)/envs/local init -input=false
	terraform -chdir=$(TERRAFORM_DIR)/envs/local apply -input=false -auto-approve

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

.PHONY: build
build: ## Build all container images
	docker compose build

.PHONY: backend-image
backend-image: ## Build the deployable backend image
	docker build -f $(BACKEND)/Dockerfile --target runtime \
		-t ai-agent-saas-backend:$(or $(TAG),local) .

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------
#
# Railway deploys the backend and Vercel deploys the web app, both on branch
# push, so there is no deploy target here — see docs/DEPLOYMENT.md. The AWS path
# (Terraform, Lambda, AgentCore) is preserved under advanced/.

.PHONY: deploy-help
deploy-help: ## Show the deploy commands
	@echo "Deploys happen on push:"
	@echo "  dev      -> Railway env 'dev'        + Vercel preview"
	@echo "  staging  -> Railway env 'staging'    + Vercel preview"
	@echo "  main     -> Railway env 'production' + Vercel production"
	@echo ""
	@echo "Railway runs 'alembic upgrade head' before each deploy (railway.json)."
	@echo "See docs/DEPLOYMENT.md. AWS path: advanced/README.md"

# ---------------------------------------------------------------------------
# Post-deploy validation
# ---------------------------------------------------------------------------

.PHONY: smoke
smoke: ## Smoke-test a deployed environment: make smoke ENV=staging
	$(require_env)
	@./scripts/smoke.sh $(ENV)

.PHONY: staging-check
staging-check: ## Full release-candidate validation: make staging-check ENV=staging
	$(require_env)
	@./scripts/staging-check.sh $(ENV)

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf $(WEB)/.next $(WEB)/out .pytest_cache .ruff_cache .mypy_cache
	find . -name __pycache__ -type d -prune -not -path "./.git/*" -exec rm -rf {} +
