#!/bin/bash
# One-shot setup: builds and starts the full Config A (flat network)
# testbed. This is the fastest path from a fresh clone to a running
# system — see README.md for what happens next.
#
# Usage:
#   scripts/setup/setup.sh

set -e

cd "$(dirname "$0")/../.."   # repo root

echo "[setup] Checking Docker is available..."
if ! command -v docker &> /dev/null; then
  echo "[setup] ERROR: docker command not found. Install Docker Desktop first:"
  echo "[setup]   https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! docker compose version &> /dev/null; then
  echo "[setup] ERROR: 'docker compose' (v2, no hyphen) not available."
  echo "[setup] Update Docker Desktop to a version that includes Compose v2."
  exit 1
fi

echo "[setup] Building and starting all containers (plc, dashboard, attacker, ids)..."
docker compose up --build -d

echo "[setup] Waiting for services to come up..."
sleep 8

echo "[setup] Checking container status..."
docker compose ps

echo ""
echo "[setup] Done. Open http://127.0.0.1:8000 in your browser."
echo "[setup] To run the first attack experiment:"
echo "[setup]   docker compose exec attacker python3 experiments/01-modbus-control/run_experiment.py plc 5020 6 1000"
echo "[setup] See README.md and docs/demo-script.md for the full guided walkthrough."