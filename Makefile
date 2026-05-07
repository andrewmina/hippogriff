SHELL := /bin/bash
.DEFAULT_GOAL := help

# Load .env if it exists
ifneq (,$(wildcard .env))
  include .env
  export
endif

ENV        ?= dev
TF_DIR      = infra/terraform/environments/$(ENV)
CLUSTER     = $(CLUSTER_NAME)
RG          = $(RESOURCE_GROUP)
REGION      = $(AZURE_REGION)

.PHONY: help init plan apply destroy login build push load chaos port-forward verify

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Azure ──────────────────────────────────────────────────────────────────

login: ## Authenticate with Azure
	az login
	az account set --subscription $(ARM_SUBSCRIPTION_ID)

# ── Terraform ──────────────────────────────────────────────────────────────

init: ## Initialise Terraform
	cd $(TF_DIR) && terraform init

plan: ## Preview infrastructure changes
	cd $(TF_DIR) && terraform plan \
	  -var="dd_api_key=$(DD_API_KEY)" \
	  -var="dd_app_key=$(DD_APP_KEY)" \
	  -var="anthropic_api_key=$(ANTHROPIC_API_KEY)" \
	  -var="subscription_id=$(ARM_SUBSCRIPTION_ID)"

apply: ## Deploy infrastructure
	cd $(TF_DIR) && terraform apply -auto-approve \
	  -var="dd_api_key=$(DD_API_KEY)" \
	  -var="dd_app_key=$(DD_APP_KEY)" \
	  -var="anthropic_api_key=$(ANTHROPIC_API_KEY)" \
	  -var="subscription_id=$(ARM_SUBSCRIPTION_ID)"

destroy: ## Tear down all infrastructure
	cd $(TF_DIR) && terraform destroy -auto-approve \
	  -var="dd_api_key=$(DD_API_KEY)" \
	  -var="dd_app_key=$(DD_APP_KEY)" \
	  -var="anthropic_api_key=$(ANTHROPIC_API_KEY)" \
	  -var="subscription_id=$(ARM_SUBSCRIPTION_ID)"

# ── Kubernetes ─────────────────────────────────────────────────────────────

kubeconfig: ## Pull AKS credentials into kubectl
	az aks get-credentials --resource-group $(RG) --name $(CLUSTER) --overwrite-existing

verify: kubeconfig ## Verify cluster + Datadog agent status
	@echo "=== Nodes ==="
	kubectl get nodes -o wide
	@echo ""
	@echo "=== Datadog Agent pods ==="
	kubectl get pods -n datadog -o wide
	@echo ""
	@echo "=== All namespaces ==="
	kubectl get pods -A --field-selector=status.phase!=Running 2>/dev/null || echo "All pods running"

port-forward: ## Port-forward key services locally
	@echo "Forwarding odds-engine  → localhost:8001"
	@echo "Forwarding bet-service  → localhost:8002"
	@echo "Forwarding web-app      → localhost:3000"
	kubectl port-forward -n hippogriff svc/odds-engine 8001:8000 &
	kubectl port-forward -n hippogriff svc/bet-service 8002:8000 &
	kubectl port-forward -n hippogriff svc/web-app 3000:3000 &
	@echo "Done. Ctrl+C to stop individual forwards."

# ── Docker / ACR ───────────────────────────────────────────────────────────

acr-login: ## Log in to Azure Container Registry
	az acr login --name $(ACR_NAME)

build: acr-login ## Build all service images
	@for svc in odds-engine bet-service wallet-service auth-service lineup-service \
	             tip-assistant fraud-detector notification-service settlement-service; do \
	  echo "Building $$svc..."; \
	  docker build -t $(ACR_NAME).azurecr.io/hippogriff/$$svc:latest services/$$svc; \
	done
	@echo "Building scoring-service (Go)..."
	docker build -t $(ACR_NAME).azurecr.io/hippogriff/scoring-service:latest services/scoring-service

push: ## Push all images to ACR
	@for svc in odds-engine bet-service wallet-service auth-service lineup-service \
	             tip-assistant fraud-detector notification-service settlement-service \
	             scoring-service; do \
	  echo "Pushing $$svc..."; \
	  docker push $(ACR_NAME).azurecr.io/hippogriff/$$svc:latest; \
	done

build-push: build push ## Build and push all images

# ── Load generation ────────────────────────────────────────────────────────

load: ## Start Locust load generator (headless, realistic traffic)
	cd load-generator && pip install -q locust && \
	locust -f locustfile.py --headless -u 50 -r 5 --run-time 24h \
	  --host http://localhost:8001

load-ui: ## Start Locust with web UI at localhost:8089
	cd load-generator && pip install -q locust && \
	locust -f locustfile.py --host http://localhost:8001

# ── Chaos ──────────────────────────────────────────────────────────────────

chaos-latency: ## Inject latency into odds-engine
	kubectl exec -n hippogriff deploy/odds-engine -- \
	  python -c "import time; time.sleep(999)" &
	@echo "Latency injected. Run 'make chaos-stop' to recover."

chaos-errors: ## Trigger error burst in bet-service
	bash chaos/inject-errors.sh bet-service 60

chaos-stop: ## Remove all chaos
	bash chaos/stop-chaos.sh

# ── Datadog ────────────────────────────────────────────────────────────────

dd-status: ## Check Datadog agent status on all nodes
	kubectl exec -n datadog $$(kubectl get pods -n datadog -l app=datadog-agent -o name | head -1) \
	  -- agent status

# ── ACR Build Tasks (no local Docker needed) ───────────────────────────────

ACR_SERVER = hippogriffacrdev.azurecr.io

acr-build: ## Build and push a single service via ACR build task
	@if [ -z "$(svc)" ]; then echo "Usage: make acr-build svc=odds-engine"; exit 1; fi
	az acr build --platform linux/arm64 \
	  --registry hippogriffacrdev \
	  --image hippogriff/$(svc):latest \
	  --image hippogriff/$(svc):$(shell git rev-parse --short HEAD 2>/dev/null || echo dev) \
	  services/$(svc)

acr-build-all: ## Build and push all Phase 2 services via ACR build tasks
	@for svc in odds-engine bet-service; do \
	  echo "🏗  Building $$svc in ACR..."; \
	  az acr build --platform linux/arm64 \
	    --registry hippogriffacrdev \
	    --image hippogriff/$$svc:latest \
	    services/$$svc; \
	  echo "✅ $$svc done"; \
	done

deploy-phase2: ## Deploy all Phase 2 resources to the cluster
	kubectl apply -f infra/k8s/postgres/
	kubectl apply -f services/odds-engine/k8s/
	kubectl apply -f services/bet-service/k8s/
	@echo "Waiting for deployments to be ready..."
	kubectl rollout status deployment/odds-engine -n hippogriff --timeout=120s
	kubectl rollout status deployment/bet-service -n hippogriff --timeout=120s
	@echo "✅ Phase 2 deployed"

seed: ## Seed events in odds-engine
	kubectl exec -n hippogriff deploy/odds-engine -- curl -sf -X POST localhost:8000/seed | python3 -m json.tool

logs-odds: ## Tail odds-engine logs
	kubectl logs -n hippogriff deploy/odds-engine -f

logs-bet: ## Tail bet-service logs
	kubectl logs -n hippogriff deploy/bet-service -f
