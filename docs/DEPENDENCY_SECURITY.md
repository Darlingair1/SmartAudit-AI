# Dependency Security Status

## Policy

Critical and high-severity vulnerabilities block releases. Exceptions must identify the advisory, affected component, compensating control, owner, and expiry date. This repository does not maintain permanent blanket ignores.

## Current Python migration blocker

The 2026-07-26 dependency migration upgraded FastAPI, LangChain, Transformers, PyPDF, Requests, and python-dotenv. The final `pip-audit --requirement ai-python/requirements.lock.txt --strict` run reported no known vulnerabilities.

LangChain 1.x and Transformers 5.x are now installed and covered by the Python test suite. ChromaDB remains on 0.6.3 with `langchain-chroma` 0.2.3 because the current ChromaDB 1.x line has an unfixed pre-authentication code-injection advisory; the application uses embedded Chroma and does not expose the affected server endpoint.

Required remediation sequence:

1. Upgrade direct low-risk dependencies such as Requests, PyPDF, and python-dotenv with focused parser/callback regression tests.
2. Keep the LangChain package family pinned as one compatible set and update imports, chains, tools, and structured-output handling together.
3. Upgrade FastAPI/Starlette together and rerun callback, authentication, health, and upload tests.
4. Upgrade Transformers/sentence-transformers together and verify embedding and reranking compatibility with the declared model locks.
5. Regenerate `requirements.lock.txt`, rerun `pip-audit`, all Python tests, Docker E2E, and image scans.

## Frontend status

The production dependency audit using the official npm registry reports zero vulnerabilities after compatible lockfile updates. Remaining npm advisories are limited to development tooling and require major ESLint/Vite upgrades; they are tracked by Dependabot and do not enter the production frontend image.

## Final Local Verification Note (2026-07-26)

The final AI image was rebuilt and verified with `pip check`; the application stack restarted healthy and the complete Playwright suite passed 5/5. Trivy was attempted through `aquasec/trivy:0.63.0`, but its vulnerability database download timed out after five minutes. No Trivy result is being treated as a pass. Resume with the four local image scans when registry access is available.
