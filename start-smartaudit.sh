#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v java >/dev/null || { echo 'Java 21+ is required'; exit 1; }
command -v python3 >/dev/null || { echo 'Python 3.10+ is required'; exit 1; }
command -v npm >/dev/null || { echo 'Node.js 20+ and npm are required'; exit 1; }
[[ -f "$ROOT/env.deploy" ]] || { echo 'Create env.deploy from env.deploy.example first'; exit 1; }
[[ -f "$ROOT/ai-python/.env" ]] || { echo 'Create ai-python/.env from .env.example first'; exit 1; }
mkdir -p "$ROOT/logs"
(cd "$ROOT/backend-java" && ./mvnw spring-boot:run > "$ROOT/logs/backend.log" 2>&1) &
(cd "$ROOT/ai-python" && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > "$ROOT/logs/ai-python.log" 2>&1) &
(cd "$ROOT/frontend" && npm run dev -- --host 0.0.0.0 > "$ROOT/logs/frontend.log" 2>&1) &
trap 'kill 0' INT TERM EXIT
echo "Backend: http://localhost:8080  AI: http://localhost:8000  Frontend: http://localhost:5173"
wait
