# ai-agent-saas-template — top-level developer interface.
#
# Every target here is a thin wrapper. The underlying tools (pnpm, uv, docker,
# terraform) remain directly usable; nothing is hidden behind the Makefile.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

WEB      := apps/web
API      := services/api
AGENT    := services/agent
MCP      := services/mcp
CONTRACTS := packages/contracts
TERRAFORM_DIR := infra/terraform

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
	$(UV) sync --project $(API)
	$(UV) sync --project $(AGENT)
	$(UV) sync --project $(MCP)
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
dev: ## Run web + api + agent + mcp together (Ctrl-C stops all)
	@./scripts/dev.sh

.PHONY: web-dev
web-dev: ## Run the Next.js app on :3000
	$(PNPM) --filter web dev

.PHONY: api-dev
api-dev: ## Run the FastAPI service on :8000
	cd $(API) && $(UV) run fastapi dev app/main.py --host 0.0.0.0 --port 8000

.PHONY: agent-dev
agent-dev: ## Run the Strands agent locally on :8080
	@./scripts/agent-dev.sh

.PHONY: mcp-dev
mcp-dev: ## Run the MCP server on :8090
	cd $(MCP) && $(UV) run python server.py

# ---------------------------------------------------------------------------
# Local infrastructure
# ---------------------------------------------------------------------------

.PHONY: infra-up
infra-up: ## Start Postgres + LocalStack and apply migrations
	docker compose up -d postgres localstack
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
	cd $(API) && $(UV) run alembic upgrade head

.PHONY: db-rollback
db-rollback: ## Roll back the most recent migration
	cd $(API) && $(UV) run alembic downgrade -1

.PHONY: db-migration
db-migration: ## Create a migration: make db-migration NAME="add plans table"
	@if [ -z "$(NAME)" ]; then echo 'ERROR: NAME is required. Example: make db-migration NAME="add plans table"'; exit 1; fi
	cd $(API) && $(UV) run alembic revision --autogenerate -m "$(NAME)"

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
	cd $(API) && $(UV) run python -m app.seed

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

.PHONY: format
format: ## Format all code
	$(UV) run --project $(API) ruff format $(API) $(CONTRACTS)
	$(UV) run --project $(MCP) ruff format $(MCP)
	$(UV) run --project $(AGENT) ruff format $(AGENT) evals tests
	$(PNPM) --filter web format

.PHONY: format-check
format-check: ## Verify formatting without writing changes
	$(UV) run --project $(API) ruff format --check $(API) $(CONTRACTS)
	$(UV) run --project $(MCP) ruff format --check $(MCP)
	$(UV) run --project $(AGENT) ruff format --check $(AGENT) evals tests
	$(PNPM) --filter web exec prettier --check "src/**/*.{ts,tsx}"

.PHONY: lint
lint: ## Lint Python and TypeScript
	$(UV) run --project $(API) ruff check $(API) $(CONTRACTS)
	$(UV) run --project $(MCP) ruff check $(MCP)
	$(UV) run --project $(AGENT) ruff check $(AGENT) evals tests
	$(PNPM) --filter web lint

.PHONY: typecheck
typecheck: ## Type-check Python and TypeScript
	$(UV) run --project $(API) mypy $(API)/app
	$(UV) run --project $(MCP) mypy $(MCP)
	$(UV) run --project $(AGENT) mypy $(AGENT)
	$(PNPM) --filter web typecheck
	$(PNPM) --filter e2e typecheck

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

.PHONY: test-unit
test-unit: ## Unit + service + tool-contract tests (no external infrastructure)
	$(UV) run --project $(CONTRACTS) pytest $(CONTRACTS)/tests -q
	$(UV) run --project $(API) pytest $(API)/tests -q
	$(UV) run --project $(MCP) pytest $(MCP)/tests -q
	$(UV) run --project $(AGENT) pytest $(AGENT)/tests -q
	$(PNPM) --filter web test

.PHONY: test-integration
test-integration: ## Integration tests against local Postgres + LocalStack + MCP
	@./scripts/require-infra.sh
	$(UV) run --project $(API) pytest tests/integration -q

.PHONY: test-e2e
test-e2e: ## Playwright end-to-end tests against the local stack
	@./scripts/require-stack.sh
	$(PNPM) --filter e2e test

.PHONY: e2e-install
e2e-install: ## Install the Playwright browsers
	$(PNPM) --filter e2e exec playwright install --with-deps chromium

.PHONY: eval
eval: ## Run the agent evaluation suite
	$(UV) run --project $(AGENT) python -m evals.run

.PHONY: test
test: test-unit test-integration test-e2e ## Full local test suite

.PHONY: check
check: format-check lint typecheck contracts-check test-unit terraform-fmt terraform-validate ## Fast pre-push suite

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

.PHONY: api-package
api-package: ## Build the FastAPI Lambda container image
	docker build -f $(API)/Dockerfile --target lambda -t ai-agent-saas-api:$(or $(TAG),local) .

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

.PHONY: api-deploy
api-deploy: ## Deploy the API: make api-deploy ENV=dev
	$(require_env)
	@./scripts/deploy/api.sh $(ENV)

.PHONY: agent-deploy
agent-deploy: ## Deploy the agent to AgentCore Runtime: make agent-deploy ENV=dev
	$(require_env)
	@./scripts/deploy/agent.sh $(ENV)

.PHONY: mcp-deploy
mcp-deploy: ## Deploy the MCP server / Gateway targets: make mcp-deploy ENV=dev
	$(require_env)
	@./scripts/deploy/mcp.sh $(ENV)

.PHONY: web-deploy
web-deploy: ## Deploy the web application: make web-deploy ENV=dev
	$(require_env)
	@./scripts/deploy/web.sh $(ENV)

.PHONY: deploy
deploy: ## Deploy every component: make deploy ENV=dev
	$(require_env)
	@$(MAKE) --no-print-directory terraform-plan ENV=$(ENV)
	@$(MAKE) --no-print-directory terraform-apply ENV=$(ENV) CONFIRM=$(CONFIRM)
	@$(MAKE) --no-print-directory api-deploy ENV=$(ENV)
	@$(MAKE) --no-print-directory mcp-deploy ENV=$(ENV)
	@$(MAKE) --no-print-directory agent-deploy ENV=$(ENV)
	@$(MAKE) --no-print-directory web-deploy ENV=$(ENV)
	@$(MAKE) --no-print-directory smoke ENV=$(ENV)

.PHONY: deploy-dev
deploy-dev: ## Deploy to the dev environment
	@$(MAKE) --no-print-directory deploy ENV=dev

.PHONY: deploy-staging
deploy-staging: ## Deploy to the staging environment
	@$(MAKE) --no-print-directory deploy ENV=staging

.PHONY: deploy-prod
deploy-prod: ## Deploy to production (requires CONFIRM=prod)
	@$(MAKE) --no-print-directory deploy ENV=prod CONFIRM=$(CONFIRM)

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
