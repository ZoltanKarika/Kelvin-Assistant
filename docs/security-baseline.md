# v1.0 Security and Permission Baseline

This document records the v1.0 security baseline for Kelvin Assistant. It ties
the local safety model to concrete tests and operator expectations.

---

## Default Secure Configuration

- Production installs must use `KELVIN_API_AUTH_MODE=required`.
- `KELVIN_API_TOKEN_FILE` must point to a token file outside the repository,
  usually `/etc/kelvin-assistant/api-tokens.json`.
- Token files store only `token_sha256` digests and known scopes. Raw bearer
  tokens are shown once to the client and then kept in a password manager or
  client credential store.
- The `/health` and `/` endpoints remain public for process checks. Protected
  API, settings, memory, agent, audit, and status endpoints require scoped
  bearer tokens when auth is configured.
- n8n receives only the minimum Kelvin API scopes required by each workflow.
  Do not give n8n `agent:approve`; local human approval remains Kelvin's safety
  boundary.
- Settings and UI responses expose whether secrets are configured, not the raw
  values.

---

## Permission Boundaries

| Boundary | Required behavior | Evidence |
|---|---|---|
| API token file | Missing, malformed, duplicate, plaintext, or unknown-scope token files fail closed. | `tests/unit/adapters/test_file_api_tokens.py` |
| Scoped API auth | Missing or invalid tokens return 401; valid tokens without a required scope return 403. | `tests/unit/api/test_auth_dependency.py` |
| Settings write access | Runtime settings updates require `agent:approve`, while read-only settings require `system:read`. | `backend/src/kelvin_assistant/api/settings_routes.py`, `tests/unit/api/test_settings_endpoint.py` |
| Agent write tools | Write, destructive, and privileged tools require explicit approval before execution. | `tests/unit/api/test_agent_endpoint.py`, `tests/unit/adapters/test_write_tools.py` |
| Approval binding | Approval decisions must reference the stored pending tool call and cannot approve invented calls. | `tests/unit/api/test_agent_endpoint.py` |
| Workspace boundary | Unknown workspaces and cross-workspace tool targets are denied. | `tests/unit/api/test_agent_endpoint.py`, `tests/unit/adapters/test_write_tools.py` |
| Input/context guards | Credential requests, workspace escape, dangerous commands, and prompt-boundary attacks are blocked. | `tests/unit/domain/test_input_guard.py`, `tests/unit/domain/test_context_guard.py` |
| Output masking | Bearer tokens, private keys, PostgreSQL URLs, and generic credential URLs are masked. | `tests/unit/domain/test_output_guard.py` |
| Audit logging | Security decisions store masked content and can be listed without exposing raw secrets. | `tests/unit/ports/test_audit_logging.py`, `tests/unit/api/test_audit_endpoint.py` |
| Notification redaction | Approval, completion, failure, and daily summary notifications do not expose raw secrets or tool diffs. | `tests/unit/api/test_notifications.py` |
| n8n isolation | n8n health and delegated email failures are non-blocking for local Kelvin behavior. | `tests/unit/api/test_n8n_endpoint.py`, `tests/unit/api/test_network_resilience.py`, `tests/unit/api/test_notifications.py` |

---

## v1.0 Regression Checklist

Run this focused security set when changing auth, settings, notifications,
agent tools, guard logic, n8n, or audit behavior:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .pytest_temp\v10-security `
  tests/unit/adapters/test_file_api_tokens.py `
  tests/unit/api/test_auth_dependency.py `
  tests/unit/api/test_agent_endpoint.py `
  tests/unit/adapters/test_write_tools.py `
  tests/unit/api/test_settings_endpoint.py `
  tests/unit/api/test_notifications.py `
  tests/unit/api/test_n8n_endpoint.py `
  tests/unit/api/test_audit_endpoint.py `
  tests/unit/domain/test_input_guard.py `
  tests/unit/domain/test_context_guard.py `
  tests/unit/domain/test_output_guard.py `
  tests/unit/ports/test_audit_logging.py
```

For full release verification, also run the standard v1.0 quality gate from
`docs/ai/v10-readiness-audit.md`.

---

## Known Limits

- Kelvin can mask common secret patterns, but it cannot prove arbitrary freeform
  text contains no sensitive business data. Operators should keep raw secrets
  out of prompts, goals, summaries, and workflow exports.
- The local UI and notification emails summarize run state; detailed diffs and
  raw tool arguments remain in the local approval/run surfaces where scoped
  access and local review apply.
- `KELVIN_API_AUTH_MODE=disabled` is acceptable only for local development on a
  trusted machine. Production and shared LAN deployments must require auth.
- n8n is a separate automation layer. Its credential store, owner account, 2FA,
  workflow exports, and network exposure must be managed according to
  `docs/n8n-credential-setup.md` and `docs/n8n-integration.md`.
- Email and n8n notification delivery are best-effort. Delivery failure must not
  approve a tool, bypass local approval, or block normal Kelvin API operation.

---

## Operator Acceptance Criteria

Before accepting v1.0 security readiness:

1. Production config has auth required and a hashed token file outside Git.
2. n8n credentials use least-privilege scopes and no `agent:approve`.
3. Settings UI reports secret presence only, never raw token or password values.
4. Approval emails and n8n payloads omit raw tool arguments and diffs.
5. Completion, failure, and daily summary notifications mask known secret
   patterns.
6. Security audit entries contain masked content only.
7. The focused security regression checklist passes.
