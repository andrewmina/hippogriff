# 🦅 Hippogriff

> Real-time sports betting & fantasy sports platform — Datadog demo environment

Hippogriff is a fictional fintech/gaming platform built to demonstrate the full Datadog observability stack. It simulates a high-throughput, event-driven betting platform with realistic traffic patterns, intentional failure modes, and a full suite of telemetry.

## What's running

| Service | Language | Purpose |
|---|---|---|
| `odds-engine` | Python/FastAPI | Real-time odds calculation, DogStatsD metrics |
| `bet-service` | Python/FastAPI | Bet placement, APM + DBM |
| `wallet-service` | Python/FastAPI | Deposits, withdrawals, ASM enabled |
| `auth-service` | Python/FastAPI | JWT auth, ASM attack surface |
| `scoring-service` | Go | Live score ingestion, Kafka consumer |
| `lineup-service` | Python/FastAPI | Fantasy lineup management |
| `tip-assistant` | Python | Anthropic-powered AI tips, LLM Observability |
| `fraud-detector` | Python | Fraud scoring, custom metrics |
| `notification-service` | Python | Kafka-driven push/email notifications |
| `settlement-service` | Python | Bet settlement engine, Postgres DBM |
| `web-app` | Next.js | Frontend, Datadog RUM + Session Replay |

## Datadog products covered

APM · Logs · Infrastructure · RUM · Session Replay · Error Tracking · DBM · DSM · NPM · Profiling · ASM · CSM · LLM Observability · Synthetics · Monitors · SLOs · Incidents · CI Visibility · Service Catalog · Dashboards

## Quick start

```bash
# 1. Copy and fill in your secrets
cp .env.example .env
# edit .env with your keys

# 2. Initialize Terraform
make init

# 3. Preview infrastructure
make plan

# 4. Deploy everything
make apply

# 5. Start load generator
make load

# 6. Tear down
make destroy
```

## Cost

Designed to run at ~$20–30/month on Azure using spot node pools.

- 2× Standard_B2s spot nodes: ~$8–14/mo
- 1× Standard_B2s system node: ~$6/mo
- Azure load balancer + public IP: ~$3/mo
- Azure Container Registry (Basic): ~$5/mo
- Azure Blob (log archive): ~$1/mo
- Azure Functions (serverless demo): ~$1/mo
- Anthropic API (tip-assistant): ~$2–5/mo

## Repository structure

```
hippogriff/
├── .github/workflows/       # CI/CD pipelines (DD CI Visibility)
├── infra/
│   ├── terraform/           # All Azure + Datadog infrastructure as code
│   │   ├── modules/         # Reusable modules: aks, acr, keyvault, datadog-azure
│   │   └── environments/dev # Dev environment root module
│   └── k8s/                 # Kubernetes manifests
│       ├── namespaces/      # Namespace definitions
│       └── datadog-operator/ # DatadogAgent CRD + Operator config
├── services/                # All microservices
│   └── <service>/
│       ├── app/             # Application code
│       ├── Dockerfile
│       └── k8s/             # Helm chart / K8s manifests for this service
├── load-generator/          # Locust traffic simulation
├── chaos/                   # Chaos injection scripts
└── scripts/                 # Helper scripts (bootstrap, port-forward, etc.)
```

## Secrets

Never commit secrets. All sensitive values go in `.env` (git-ignored).

See `.env.example` for required variables.
