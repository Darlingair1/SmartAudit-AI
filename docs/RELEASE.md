# Release Process

SmartAudit-AI uses Semantic Versioning. The authoritative version is stored in `VERSION` and must match the frontend package and backend Maven project.

## Version changes

- `MAJOR`: incompatible API, schema, or deployment changes.
- `MINOR`: backward-compatible features.
- `PATCH`: backward-compatible fixes.

Before tagging:

1. Update `VERSION`, `frontend/package.json`, `frontend/package-lock.json`, and the backend Maven version.
2. Move relevant entries from `Unreleased` in `CHANGELOG.md` to the dated version.
3. Run the complete stage-five test entry.
4. Review dependency and security alerts.
5. Create and push an annotated `vMAJOR.MINOR.PATCH` tag.

## Automated release

The Release workflow validates the tag, reruns all tests, builds and pushes three GHCR images, scans them, generates CycloneDX SBOMs, creates a source archive, rejects forbidden contents, produces `SHA256SUMS`, and creates the GitHub Release.

Release artifacts include:

- source archive;
- SHA256 checksums;
- backend, AI, and frontend image SBOMs;
- immutable image digests.

The release must be rejected if it includes credentials, `.env` files, deployment secrets, logs, databases, model weights, uploaded contracts, coverage output, test traces, or build caches.

## Remote setup required

Before the first release, configure the GitHub remote, enable branch protection, configure maintainers/CODEOWNERS, and confirm GHCR package visibility. No long-lived registry password is required; the workflow uses the scoped `GITHUB_TOKEN`.
