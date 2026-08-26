#!/bin/bash
# Resets the testbed to a clean state for repeatable demos and
# experiments — Section 42 of the spec requires the demo sequence to
# be "achievable reliably", and Phase 15's own evaluation summary
# testing surfaced a real reason this matters: running an experiment
# repeatedly against a PLC that's still in an alarm state from the
# PREVIOUS run produces inconsistent results (see
# docs/architecture/evaluation-summary.md).
#
# What this clears:
#   - the historian database (telemetry/alarm/plc/ids event history)
#   - all experiment result files (JSON snapshots + results.csv)
#   - all captured pcaps
#
# What this does NOT touch: source code, docker images, Docker
# Compose state. Run `docker compose restart plc dashboard` (or
# `down`/`up`) separately if you also need the PLC's in-memory physics
# state reset to its default steady state — this script only clears
# persisted files.
#
# Usage:
#   scripts/reset/reset_environment.sh          (asks for confirmation)
#   scripts/reset/reset_environment.sh --yes     (skips confirmation)

set -e

cd "$(dirname "$0")/../.."   # repo root

if [ "$1" != "--yes" ]; then
  echo "This will permanently delete:"
  echo "  - data/logs/historian.db"
  echo "  - all files under data/experiments/*/  (JSON + CSV results)"
  echo "  - all files under data/pcaps/"
  echo ""
  read -p "Continue? [y/N] " confirm
  if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Cancelled."
    exit 0
  fi
fi

echo "[reset] Removing historian database..."
rm -f data/logs/historian.db

echo "[reset] Removing experiment results..."
find data/experiments -type f \( -name "result_*.json" -o -name "results.csv" -o -name "timeline_*.json" \) -delete
rm -f data/experiments/evaluation_summary.json

echo "[reset] Removing captured pcaps..."
find data/pcaps -type f -name "*.pcap" -delete

echo "[reset] Done. Restart the PLC/dashboard containers if you also need"
echo "[reset] the physics engine's in-memory state reset:"
echo "[reset]   docker compose restart plc dashboard"
