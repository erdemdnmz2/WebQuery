# Security policy

WebQuery is under development. The current main branch receives best-effort
security fixes; no supported-release SLA or security certification is claimed.

## Reporting a vulnerability

Do not put exploitable details, credentials or customer data in a public issue.
Use **Security → Report a vulnerability** on GitHub when private reporting is
available. Otherwise contact the maintainer through an existing private channel
to arrange secure disclosure before sharing sensitive details. Include affected
commit/version, impact and a minimal reproduction with synthetic data.

## Deployment responsibilities

- Use HTTPS and private/restricted ingress with secure cookies. VPN access does
  not replace application authentication or authorization.
- Provision separate least-privilege target accounts. SQL analysis and masking
  are not a SQL sandbox or a complete sensitive-data boundary.
- Keep metadata, Redis and target DBs inaccessible from public ingress; verify
  actual proxy peers before trusting forwarded client-IP headers.
- Store signing/encryption/database/Slack secrets outside Git and Docker build
  contexts. Back up encryption keys separately and test restore/rotation.
- Use disposable infrastructure for destructive tests and review release
  dependency advisories; never reuse customer database URLs in CI.

See [feature limits](docs/features.md), [configuration](docs/configuration.md)
and [remaining hardening work](docs/implementation-plan.md). This repository's
ignore rules do not scan all secrets or make an existing leak recoverable.
