# Kelvin Assistant v1.0 Release Notes

Release version: `1.0.0`

Kelvin Assistant v1.0 is the first stable local release target. It turns the
completed local chat, memory, agent, UI, notification, n8n, backup, and
security work into a documented offline AI platform that can be installed,
operated, backed up, restored, and verified.

---

## Highlights

- Stable FastAPI service with local health, readiness, status, and version
  endpoints.
- Versioned `/api/v1` chat, streaming chat, memory, agent, security audit,
  settings, and n8n health routes.
- Local operational UI for runs, approvals, audit, settings, and n8n status.
- Scoped bearer-token authentication for LAN and production-style deployments.
- Server-managed agent runs with explicit tool proposals, approvals, audit
  logging, and local Windows client execution.
- SMTP or n8n-backed email notifications for approvals, run results, and daily
  summaries.
- PostgreSQL and pgvector support for persistence-backed memory and knowledge
  features.
- Backup, restore, operational runbook, API contract, security baseline, and
  release-package documentation.

---

## Stable Documents

- `docs/installation.md`
- `docs/api-contract.md`
- `docs/security-baseline.md`
- `docs/operational-runbooks.md`
- `docs/backup-restore.md`
- `docs/release-package.md`
- `docs/licensing.md`
- `THIRD_PARTY_NOTICES.md`

---

## Packaging Notes

The source release is Apache-2.0. Third-party packages, models, and optional
services keep their own license terms. The release package must include:

- `LICENSE`
- `NOTICE`
- `THIRD_PARTY_NOTICES.md`
- `uv.lock`
- `pyproject.toml`
- source code and documentation
- offline dependency manifest and SHA-256 checksums
- offline model manifest and SHA-256 checksums

Model weights are not bundled with the source tree. Operators must obtain model
assets under their applicable terms, record the exact model names, and verify
checksums before moving them into the offline environment.

---

## Known Limits

- Final end-to-end v1.0 operational verification remains Step 9.
- Containerization remains a test/development path unless a deployment runbook
  explicitly promotes it.
- n8n is optional. Kelvin local chat, agent, approval, audit, settings, and SMTP
  paths must remain usable when n8n is degraded or unavailable.
- Open WebUI, voice control, and public internet exposure are not part of the
  v1.0 supported surface.
- Some development tests still emit upstream deprecation warnings; Step 9 records
  the final accepted warning set.

---

## Upgrade Notes

Upgrade from the latest v0.9 state using `docs/installation.md`, then verify:

1. `/health`, `/status`, `/ready`, `/ready/database`, and `/version`.
2. `/ui/runs`, `/ui/approvals`, `/ui/audit`, `/ui/settings`, and `/ui/n8n`.
3. Token scopes and `KELVIN_API_AUTH_MODE=required` for LAN-accessible hosts.
4. Email notification provider, test email, approval email, run result email, and
   daily summary email.
5. Backup and restore procedure, including n8n encryption key handling when n8n
   is configured.
