# Security Policy

## Supported Versions

Security fixes are provided for the latest release on the default branch. Pre-release builds and older releases are not supported unless a release note explicitly says otherwise.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting feature for this repository. If private reporting is unavailable, contact the repository owner privately and include:

- affected version or commit;
- reproduction steps and impact;
- relevant logs with secrets, contract text, personal data, and tokens removed;
- any suggested mitigation.

The maintainers will acknowledge a report within 5 business days, assess severity, and coordinate disclosure after a fix is available. Do not access data that does not belong to you or disrupt a deployed service while testing.

## Deployment Boundary

Production deployments must use the `prod` Spring profile and `APP_ENV=production`, strict JWT authentication, unique secrets of at least 32 characters, TLS at the reverse proxy, and an authenticated internal network between Java and Python services. Never use `demo-token` in production.

Contract content may be sent to the configured model provider. Remove or mask sensitive information unless the deployment has a lawful basis and appropriate data-processing controls.
