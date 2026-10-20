#!/usr/bin/env bash
# Live end-to-end smoke test against the local stack.
#
#   ./scripts/smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./scripts/bootstrap.sh
make install
./scripts/dev.sh start

cd "$ROOT/backend"
AURA_E2E=1 uv run pytest tests/test_e2e_smoke.py -q
