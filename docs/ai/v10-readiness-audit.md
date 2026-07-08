# v1.0 Release Readiness Gap Audit

This audit is Step 1 of `docs/ai/v10-guide.md`. It records what is already
ready for v1.0, what is partially ready, what is missing, and which PR should
handle each gap.

Audit date: 2026-07-08
Baseline branch: `codex/v1.0-readiness-audit`

---

## Current Status

Kelvin has the main product capabilities expected before v1.0: local FastAPI
runtime, Ollama integration, PostgreSQL-backed knowledge/memory/agent/audit
adapters, scoped API tokens, approval-gated write tools, security guards,
operational UI pages, n8n status, and email notifications.

v1.0 is not ready yet because the install, operations, backup/restore, security
baseline, API contract, and release verification docs are not yet tied together
as one repeatable stable-release procedure.

---

## Completed Items

| Area | Evidence | Status |
|---|---|---|
| FastAPI service and local UI | `backend/src/kelvin_assistant/api/app.py`, `backend/src/kelvin_assistant/web/` | Ready for v1.0 verification |
| Health and readiness endpoints | `tests/unit/api/test_system_endpoints.py`, `tests/unit/api/test_n8n_endpoint.py` | Covered by tests |
| Scoped token auth | `api-tokens.example.json`, `tests/unit/adapters/test_file_api_tokens.py`, `tests/unit/api/test_auth_dependency.py` | Implemented and tested |
| Fail-closed auth configuration | `create_app()` raises when auth is required without token file | Implemented |
| Agent run persistence and approvals | `tests/unit/api/test_agent_endpoint.py`, `tests/unit/adapters/test_postgres_agent_runs.py` | Implemented and tested |
| Write-tool local approval boundary | `tests/unit/adapters/test_write_tools.py` | Implemented and tested |
| Security guards and audit logging | `tests/unit/domain/test_input_guard.py`, `tests/unit/domain/test_output_guard.py`, `tests/unit/ports/test_audit_logging.py` | Covered by tests |
| Email notification behavior | `tests/unit/api/test_notifications.py`, `tests/unit/api/test_settings_endpoint.py` | Implemented and tested |
| n8n health is non-blocking | `tests/unit/api/test_n8n_endpoint.py`, `tests/unit/api/test_network_resilience.py` | Covered by tests |
| systemd service hardening | `infrastructure/systemd/kelvin-api.service` | Present |
| v1.0 plan | `docs/ai/v10-guide.md`, `docs/roadmap.md` | Created |

---

## Partially Completed Items

| Area | Gap | Next step |
|---|---|---|
| Installation docs | `docs/installation.md` now covers the operational UI, production auth, email/n8n settings pointers, v1.0 upgrade, rollback, and smoke checks. | Done in `codex/v1.0-install-runbook` |
| Runtime readiness docs | `/health`, `/status`, `/ready`, and `/ready/database` now distinguish process health, aggregate degraded state, and strict dependency readiness. | Done in `codex/v1.0-runtime-hardening` |
| Backup/restore docs | `docs/backup-restore.md` now covers Kelvin post-restore API/UI/audit verification, retention guidance, n8n credential restore checks, and acceptance criteria. | Done in `codex/v1.0-backup-restore` |
| Security docs | Token management and security behavior are spread across several docs; v1.0 needs one baseline checklist for tokens, approvals, masking, audit, email, and n8n boundaries. | Step 5 |
| Operational runbooks | UI, email, n8n, audit, approvals, and troubleshooting docs exist in pieces but are not combined into daily-operation runbooks. | Step 6 |
| API contract | Versioned routes and schemas exist, but v1.0 stable/unstable surfaces are not explicitly frozen. | Step 7 |
| Release package | Version is still `0.6.0` in `pyproject.toml`; release notes, version update, notices review, and offline verification are pending. | Step 8 |
| End-to-end verification | Unit tests pass in prior v0.9 checks, but v1.0 needs a recorded operational verification across install, service startup, UI, email, n8n outage, backup, and restore. | Step 9 |

---

## Missing or Contradictory Items

| Priority | Finding | Evidence | Proposed owner step |
|---|---|---|---|
| P1 | n8n credential guide shows a plaintext `token` field that conflicts with the hashed `token_sha256` format. | `docs/n8n-credential-setup.md` vs `api-tokens.example.json` and `tests/unit/adapters/test_file_api_tokens.py` | Done in `codex/v1.0-security-doc-sync` |
| P1 | Production auth mode is documented as optional, but v1.0 needs a clear rule for when `KELVIN_API_AUTH_MODE=required` is mandatory. | `.env.example`, `docs/installation.md`, `create_app()` | Done in `codex/v1.0-security-doc-sync` |
| P1 | Backup restore does not end with Kelvin-specific health/readiness/UI/audit verification. | `docs/backup-restore.md` | Done in `codex/v1.0-backup-restore` |
| P2 | Install docs still reference the old minimal chat UI instead of the full operational UI. | `docs/installation.md` | Done in `codex/v1.0-install-runbook` |
| P2 | `.env.example` does not list v0.9 email and n8n settings, even though `Settings` supports them. | `.env.example`, `backend/src/kelvin_assistant/config/settings.py` | Done in `codex/v1.0-install-runbook` |
| P2 | Release version metadata is behind the milestone history. | `pyproject.toml` version `0.6.0` | Step 8 |
| P2 | Offline supply-chain section is aspirational and lacks concrete artifact/checksum commands. | `docs/installation.md` | Step 8 |
| P2 | Containerization is documented as a trial stack, not a v1.0-supported deployment path. | `docs/containerization-test.md` | Step 2 or Step 8 |
| P3 | Deprecation warnings remain in tests for FastAPI status naming and `datetime.utcnow()`. | Prior test output and related tests | Step 9 or a small cleanup PR |
| P3 | Several docs mix English and Hungarian; v1.0 should decide whether this is acceptable or standardize operator-facing sections. | README and docs | Step 1 follow-up or Step 2 |

---

## Recommended PR Order

1. **Fix security-critical doc contradictions** - done in `codex/v1.0-security-doc-sync`
   - Branch: `codex/v1.0-security-doc-sync`
   - Commit: `docs: align v1.0 token and credential guidance`
   - Covers: n8n credential format, production auth rule, `.env.example` auth notes.

2. **Update install and upgrade runbook** - done in `codex/v1.0-install-runbook`
   - Branch: `codex/v1.0-install-runbook`
   - Commit: `docs: add v1.0 install and upgrade runbook`
   - Covers: fresh install, v0.9 to v1.0 upgrade, UI/email/n8n config pointers.

3. **Verify backup and restore** - done in `codex/v1.0-backup-restore`
   - Branch: `codex/v1.0-backup-restore`
   - Commit: `docs: verify v1.0 backup and restore process`
   - Covers: Kelvin post-restore checks, n8n encryption key handling, retention.

4. **Harden runtime readiness docs and tests** - done in `codex/v1.0-runtime-hardening`
   - Branch: `codex/v1.0-runtime-hardening`
   - Commit: `feat(runtime): harden v1.0 service readiness`
   - Covers: degraded-mode checklist and any missing readiness regressions.

5. **Create operational runbooks**
   - Branch: `codex/v1.0-ops-runbooks`
   - Commit: `docs: add v1.0 operational runbooks`
   - Covers: UI, approvals, audit, settings, email tests, n8n outage handling.

6. **Freeze API and configuration contracts**
   - Branch: `codex/v1.0-contract-freeze`
   - Commit: `docs(api): freeze v1.0 API and configuration contracts`
   - Covers: stable routes, schema expectations, token scopes, config variables.

7. **Prepare release package**
   - Branch: `codex/v1.0-release-package`
   - Commit: `docs: prepare v1.0 release package`
   - Covers: version update, release notes, licenses, offline artifact checklist.

8. **Run final stable verification**
   - Branch: `codex/v1.0-stable-verification`
   - Commit: `test(integration): verify v1.0 stable release`
   - Covers: full tests and manual operational verification evidence.

---

## Verification Commands

Use these commands for each PR unless the PR changes only prose and has a clear
reason to run a smaller check set.

```powershell
uv run ruff check backend tests scripts
uv run ruff format --check backend tests scripts
uv run mypy backend/src tests scripts
uv run pytest --basetemp .pytest_temp/v10 --cov=kelvin_assistant --cov-report=term-missing
git diff --check
```

For operational PRs, add the relevant live checks:

```powershell
Invoke-RestMethod http://<VM_IP>:8000/health
Invoke-RestMethod http://<VM_IP>:8000/ready
Invoke-RestMethod http://<VM_IP>:8000/ready/database
Invoke-RestMethod http://<VM_IP>:8000/version
```

For backup/restore PRs, record the exact backup file path, restore target, and
post-restore health/readiness/UI/audit checks.

---

## Definition of Done for Step 1

- [x] Current v1.0-ready surfaces are identified.
- [x] Gaps are separated by area and priority.
- [x] Each gap maps to a v1.0 guide step.
- [x] Suggested branch names and commit messages are listed.
- [x] Verification commands are documented.
- [x] Runtime behavior is unchanged.
