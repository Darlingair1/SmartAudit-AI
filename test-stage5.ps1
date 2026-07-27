$ErrorActionPreference = "Stop"

Write-Host "[1/6] Java tests and coverage"
Push-Location (Join-Path $PSScriptRoot "backend-java")
try { .\mvnw.cmd verify } finally { Pop-Location }

Write-Host "[2/6] Python tests and coverage"
Push-Location (Join-Path $PSScriptRoot "ai-python")
try { .\venv\Scripts\python.exe -m pytest } finally { Pop-Location }

Write-Host "[3/6] Frontend unit tests and coverage"
Push-Location (Join-Path $PSScriptRoot "frontend")
try { npm run test:unit:coverage } finally { Pop-Location }

Write-Host "[4/6] Frontend lint"
Push-Location (Join-Path $PSScriptRoot "frontend")
try { npm run lint } finally { Pop-Location }

Write-Host "[5/6] Frontend production build"
Push-Location (Join-Path $PSScriptRoot "frontend")
try { npm run build } finally { Pop-Location }

Write-Host "[6/6] Playwright E2E"
Push-Location (Join-Path $PSScriptRoot "frontend")
try { npm run test:e2e } finally { Pop-Location }

Write-Host "Stage 5 checks passed."
