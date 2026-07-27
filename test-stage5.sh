#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/6] Java tests and coverage"
(cd "$root_dir/backend-java" && ./mvnw verify)

echo "[2/6] Python tests and coverage"
(cd "$root_dir/ai-python" && python -m pytest)

echo "[3/6] Frontend unit tests and coverage"
(cd "$root_dir/frontend" && npm run test:unit:coverage)

echo "[4/6] Frontend lint"
(cd "$root_dir/frontend" && npm run lint)

echo "[5/6] Frontend production build"
(cd "$root_dir/frontend" && npm run build)

echo "[6/6] Playwright E2E"
(cd "$root_dir/frontend" && npm run test:e2e)

echo "Stage 5 checks passed."
