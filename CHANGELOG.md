# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- GitHub Actions for tests, security analysis, dependency review, SBOM generation, and releases.
- Repeatable Docker-based Playwright end-to-end tests using a local mock LLM.
- Java, Python, and frontend coverage gates.
- Reproducible BGE model downloads with pinned revisions and SHA256 verification.
- One-time, environment-driven bootstrap administrator creation for empty databases.

### Changed

- Upgraded Spring Boot to 3.5.16 and refreshed minimal runtime images to remove known High/Critical vulnerabilities.
- Switched Windows startup to the repository Maven Wrapper and documented Flyway-managed empty-database setup.
- Corrected release-content checks so public `.env.example` templates are allowed while real `.env` files remain blocked.

## [0.1.0] - 2026-07-26

### Added

- Initial open-source SmartAudit-AI application.
- Java backend, Python AI service, Vue frontend, MySQL schema migrations, and Docker Compose deployment.
- Authentication, PDF validation, callback signing, SSE task updates, and retention controls.

[Unreleased]: ../../compare/v0.1.0...HEAD
[0.1.0]: ../../releases/tag/v0.1.0
