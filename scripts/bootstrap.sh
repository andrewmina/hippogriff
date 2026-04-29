#!/bin/bash
# bootstrap.sh — One-time setup after terraform apply
# Seeds events, verifies agent connectivity, runs smoke tests

set -euo pipefail

source .env

echo "🦅 Hippogriff bootstrap starting..."

# 1. Get kubeconfig
echo "→ Pulling AKS credentials..."
az aks get-credentials \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${CLUSTER_NAME}" \
  --overwrite-existing

# 2. Wait for all pods to be ready
echo "→ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod \
  --all -n hippogriff --timeout=300s

# 3. Seed events in odds-engine
echo "→ Seeding sporting events..."
kubectl exec -n hippogriff deploy/odds-engine -- \
  curl -sf -X POST localhost:8000/seed | python3 -m json.tool

# 4. Verify Datadog agent is reporting
echo "→ Checking Datadog agent status..."
DD_AGENT_POD=$(kubectl get pods -n datadog -l app=datadog-agent -o name | head -1)
kubectl exec -n datadog $DD_AGENT_POD -- agent status 2>&1 | grep -A5 "APM Agent"

# 5. Smoke test key endpoints
echo "→ Running smoke tests..."
for svc in odds-engine bet-service wallet-service auth-service; do
  echo -n "  $svc health: "
  kubectl exec -n hippogriff deploy/$svc -- curl -sf localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])"
done

echo ""
echo "✅ Bootstrap complete!"
echo ""
echo "Next steps:"
echo "  make load        — start traffic generation"
echo "  make port-forward — access services locally"
echo "  make dd-status   — check full agent status"
echo ""
echo "Datadog links:"
echo "  APM:  https://app.datadoghq.com/apm/services"
echo "  Infra: https://app.datadoghq.com/infrastructure"
echo "  Logs: https://app.datadoghq.com/logs"
