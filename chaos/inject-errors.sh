#!/bin/bash
# inject-errors.sh — Trigger an error burst in a service
# Usage: bash chaos/inject-errors.sh <service> <duration_seconds>

SERVICE=${1:-bet-service}
DURATION=${2:-60}

echo "🔥 Injecting errors into $SERVICE for ${DURATION}s..."

END=$((SECONDS + DURATION))
while [ $SECONDS -lt $END ]; do
  kubectl exec -n hippogriff deploy/$SERVICE -- \
    curl -sf localhost:8000/chaos/error > /dev/null 2>&1 &
  sleep 0.5
done

echo "✅ Error injection complete for $SERVICE"
