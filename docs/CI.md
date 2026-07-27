# Continuous Integration

## Required checks

The repository defines these workflows:

- `CI`: Java verify/JaCoCo, Python pytest/coverage, frontend unit/lint/build, and Docker Playwright E2E.
- `CodeQL`: Java, Python, and JavaScript security analysis.
- `Security`: Gitleaks, dependency review, pip-audit, npm audit, and Trivy filesystem scanning.
- `Supply Chain`: CycloneDX source SBOM and container image scanning.
- `Release`: tag validation, full tests, image publishing, image SBOMs, archive checks, and GitHub Release creation.

All jobs use synthetic E2E data and the local mock LLM. CI must never receive a production API key.

## Local equivalent

Windows:

```powershell
.\test-stage5.ps1
```

Linux/macOS:

```bash
./test-stage5.sh
```

Security scanners require Docker or their native CLI and are intentionally separate from the fast local test entry point.

The release boundary contains three production images: `backend`, `ai`, and `frontend`. The mock LLM image is test-only and is not published. Local release validation on 2026-07-27 used Trivy 0.63.0 with `HIGH,CRITICAL`, `--ignore-unfixed`, and a nonzero exit code, then generated CycloneDX SBOMs for the dependency manifests and all three production images.

When npm is configured to use a registry mirror without the audit API, run the production dependency check against the official registry:

```powershell
npm --prefix frontend audit --omit=dev --audit-level=high --registry=https://registry.npmjs.org
```

## Branch protection

After the GitHub remote exists, protect the default branch and require pull requests, one approval, resolved conversations, and these checks:

- `Java tests`
- `Python tests`
- `Frontend tests and build`
- `Docker Playwright E2E`
- `Gitleaks`
- `Dependency review`
- all CodeQL language jobs
- `Trivy repository scan`
- all image scan jobs

Disable force pushes and branch deletion. Restrict workflow changes to maintainers. Add `.github/CODEOWNERS` only after the actual GitHub maintainer account or team is known.

## Vulnerability policy

| Severity | Pull request | Release | Target response |
| --- | --- | --- | --- |
| Critical | Block | Block | 24 hours |
| High | Block unless time-limited exception is documented | Block | 7 days |
| Medium | Track in an issue | Allowed with review | 30 days |
| Low | Track during routine maintenance | Allowed | 90 days |

Every exception must identify the advisory, affected component, compensating control, owner, and expiry date. Permanent blanket ignores are not allowed.

## Failure diagnostics

Test reports, coverage summaries, Playwright traces, and container logs are uploaded with short retention. Diagnostics must be reviewed for secrets and contract text before sharing outside trusted maintainers.
