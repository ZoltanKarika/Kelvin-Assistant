# v1.0 API and Configuration Contract

This document freezes the Kelvin Assistant v1.0 surface for local clients,
operators, and n8n workflows. It records which routes, schemas, token scopes,
and configuration variables are stable for the v1.0 line, and which surfaces are
internal or intentionally unstable.

Use this document when updating the Windows client, n8n workflows, operator
runbooks, token files, `.env.example`, or API tests.

---

## 1. Compatibility Rule

For v1.0-compatible releases:

- Stable routes keep their HTTP method, path, required token scope, and response
  field names.
- Stable request fields remain accepted when they were accepted in v1.0.
- New optional request or response fields may be added.
- New enum values may be added only when existing clients can ignore them.
- Error responses keep the normal FastAPI `detail` envelope.
- Secrets remain masked in settings responses, audit responses, email content,
  and agent tool output.
- Breaking route, field, or scope changes require a new versioned path such as
  `/api/v2/...` or a documented migration.

The OpenAPI document at `/openapi.json` is useful for inspection, but the human
contract in this document is the v1.0 support boundary.

---

## 2. Stable System Routes

These routes are stable for operators, health checks, service monitors, and
local clients.

| Method | Path | Scope | Contract |
|---|---|---|---|
| `GET` | `/` | public | Returns `name`, `version`, and `environment`. |
| `GET` | `/health` | public | Returns `{ "status": "ok" }` when the FastAPI process is alive. |
| `GET` | `/status` | `system:read` | Returns aggregate `status` and per-component readiness/degraded detail. |
| `GET` | `/ready` | `system:read` | Returns configured LLM readiness, provider, and model, or HTTP 503. |
| `GET` | `/ready/database` | `system:read` | Returns PostgreSQL readiness, or HTTP 503. |
| `GET` | `/version` | public | Returns `{ "version": "<app-version>" }`. |

`/health` and `/version` remain public so systemd, simple LAN checks, and local
operator scripts can verify process liveness without a bearer token.

---

## 3. Stable Chat Routes

| Method | Path | Scope | Contract |
|---|---|---|---|
| `POST` | `/api/v1/chat` | `chat:use` | Creates one complete chat turn. |
| `POST` | `/api/v1/chat/stream` | `chat:use` | Streams one chat turn as server-sent events. |

Stable request fields:

- `message`: required string, trimmed, non-empty.
- `session_id`: optional UUID for continuing a server-side session.

Stable non-streaming response fields:

- `session_id`
- `message`
- `model`
- `correlation_id`

Stable stream event names:

- `session`
- `token`
- `error`
- `done`

The stream event payload is JSON in the SSE `data:` line. Clients must ignore
unknown fields inside known events.

---

## 4. Stable Memory Routes

| Method | Path | Scope | Contract |
|---|---|---|---|
| `POST` | `/api/v1/memory` | `memory:write` | Stores one typed memory item. |
| `GET` | `/api/v1/memory` | `memory:read` | Lists active memory items. |
| `DELETE` | `/api/v1/memory/{memory_id}` | `memory:write` | Soft-deletes one memory item. |

Stable memory fields:

- `id`
- `scope`
- `kind`
- `content`
- `source`
- `confidence`
- `metadata`
- `created_at`
- `updated_at`
- `expires_at`

The list response keeps the top-level `memories` array.

---

## 5. Stable Agent Routes

| Method | Path | Scope | Contract |
|---|---|---|---|
| `POST` | `/api/v1/agent/runs` | `agent:execute` | Creates one server-managed agent run. |
| `GET` | `/api/v1/agent/runs` | `agent:execute` | Lists server-managed agent runs. |
| `GET` | `/api/v1/agent/runs/{run_id}` | `agent:execute` | Returns run detail and step history. |
| `POST` | `/api/v1/agent/runs/{run_id}/plan` | `agent:execute` | Moves a received run into planning. |
| `POST` | `/api/v1/agent/runs/{run_id}/next` | `agent:execute` | Asks the planner for the next clarification, tool, or completion action. |
| `POST` | `/api/v1/agent/runs/{run_id}/cancel` | `agent:execute` | Cancels an active run. |
| `POST` | `/api/v1/agent/runs/{run_id}/tools` | `agent:write` | Proposes one structured tool call. |
| `GET` | `/api/v1/agent/runs/{run_id}/tools/active` | `agent:execute` | Returns the active tool proposal, if any. |
| `POST` | `/api/v1/agent/runs/{run_id}/approval` | `agent:approve` | Approves or rejects one pending tool call. |
| `POST` | `/api/v1/agent/runs/{run_id}/result` | `agent:write` | Submits one local tool execution result. |

Stable run fields:

- `id`
- `goal`
- `status`
- `step_count`
- `max_steps`
- `version`
- `workspace_id`
- `created_at`
- `updated_at`

Stable planner `action` values:

- `clarify`
- `tool`
- `complete`

Stable approval decisions:

- `approved`
- `rejected`

Clients must treat unknown future run statuses or policy decisions as
non-terminal unless documented otherwise.

---

## 6. Stable Security, Settings, and n8n Routes

| Method | Path | Scope | Contract |
|---|---|---|---|
| `GET` | `/api/v1/security/audit` | `system:read` | Lists masked security audit entries with filters. |
| `GET` | `/api/v1/settings` | `system:read` | Returns runtime settings and policy summaries with secrets masked. |
| `PUT` | `/api/v1/settings` | `agent:approve` | Updates supported runtime settings and persists them to the configured settings env file. |
| `POST` | `/api/v1/settings/test-email` | `agent:approve` | Sends an operator test email. |
| `POST` | `/api/v1/settings/send-summary` | `agent:approve` | Sends the daily summary email immediately. |
| `GET` | `/api/v1/n8n/health` | `system:read` | Returns n8n configured/healthy/degraded/unreachable status. |

Settings responses expose booleans such as `n8n_token_configured` and
`email_smtp_password_configured`; they do not expose stored secret values.

---

## 7. Stable Token Scopes

The v1.0 token file format is version `1` and stores SHA-256 token digests only.
Raw bearer tokens are shown to clients once and must not be committed.

Stable scopes:

| Scope | Capability |
|---|---|
| `system:read` | Read readiness, runtime status, settings summaries, n8n health, and audit. |
| `chat:use` | Use chat and streaming chat endpoints. |
| `knowledge:read` | Reserved for knowledge search clients. |
| `memory:read` | Read memory items. |
| `memory:write` | Create or delete memory items. |
| `agent:execute` | Create, inspect, plan, cancel, and continue agent runs. |
| `agent:write` | Propose tools and submit tool results. |
| `agent:approve` | Approve/reject tool calls and update operational settings. |

Recommended client grants:

| Client | Scopes |
|---|---|
| Monitoring | `system:read` |
| Chat UI or simple n8n chat workflow | `chat:use`, optionally `system:read` |
| n8n read-only research workflow | `system:read`, `chat:use`, `memory:read` |
| Local Windows agent client | `system:read`, `chat:use`, `knowledge:read`, `memory:read`, `memory:write`, `agent:execute`, `agent:write`, `agent:approve` |

n8n workflows must not receive `agent:approve` unless a future release
documents a separate approval boundary.

---

## 8. Stable Configuration Variables

These `KELVIN_` variables are stable for v1.0 deployments.

| Variable | Purpose |
|---|---|
| `KELVIN_ENVIRONMENT` | Runtime environment label. |
| `KELVIN_LOG_LEVEL` | Logging threshold. |
| `KELVIN_LOG_FORMAT` | `json` or `console`. |
| `KELVIN_API_HOST` | Bind host. |
| `KELVIN_API_PORT` | Bind port. |
| `KELVIN_API_AUTH_MODE` | `disabled` for trusted loopback development, `required` for production or LAN-accessible deployments. |
| `KELVIN_API_TOKEN_FILE` | Path to the hashed token file. |
| `KELVIN_LLM_PROVIDER` | Provider selector. v1.0 supports `ollama`. |
| `KELVIN_OLLAMA_BASE_URL` | Ollama endpoint. |
| `KELVIN_OLLAMA_MODEL` | Chat/planner model. |
| `KELVIN_OLLAMA_EMBEDDING_MODEL` | Embedding model. |
| `KELVIN_EMBEDDING_DIMENSION` | Embedding vector size. |
| `KELVIN_OLLAMA_TIMEOUT` | Ollama request timeout in seconds. |
| `KELVIN_SYSTEM_PROMPT` | Optional default assistant behavior override. |
| `KELVIN_DATABASE_URL` | Optional PostgreSQL connection string. |
| `KELVIN_DATABASE_CONNECT_TIMEOUT` | PostgreSQL connection timeout in seconds. |
| `KELVIN_RAG_ENABLED` | Enables RAG context. |
| `KELVIN_RAG_COLLECTION` | RAG collection name. |
| `KELVIN_RAG_RESULT_LIMIT` | RAG result count. |
| `KELVIN_N8N_URL` | Optional n8n base URL. |
| `KELVIN_N8N_TOKEN` | Optional token used when Kelvin delegates notification delivery to n8n. |
| `KELVIN_EMAIL_NOTIFICATIONS_ENABLED` | Enables notification delivery. |
| `KELVIN_EMAIL_PROVIDER_MODE` | `smtp` or `n8n`. |
| `KELVIN_EMAIL_SMTP_HOST` | SMTP host. |
| `KELVIN_EMAIL_SMTP_PORT` | SMTP port. |
| `KELVIN_EMAIL_SMTP_USERNAME` | Optional SMTP username. |
| `KELVIN_EMAIL_SMTP_PASSWORD` | Optional SMTP password. |
| `KELVIN_EMAIL_SMTP_USE_TLS` | SMTP TLS toggle. |
| `KELVIN_EMAIL_SENDER` | Notification sender address. |
| `KELVIN_EMAIL_RECIPIENT` | Notification recipient address. |
| `KELVIN_EMAIL_DAILY_SUMMARY_TIME` | Daily summary time in `HH:MM`. |
| `KELVIN_EMAIL_ON_APPROVAL_REQUIRED` | Sends approval-required notifications. |
| `KELVIN_EMAIL_ON_RUN_COMPLETED` | Sends completed-run notifications. |
| `KELVIN_EMAIL_ON_RUN_FAILED` | Sends failed-run notifications. |
| `KELVIN_EMAIL_ON_DAILY_SUMMARY` | Sends daily summary notifications. |
| `KELVIN_AGENT_WORKSPACE_IDS` | Opaque workspace IDs accepted by the backend. |

Windows client variables are client-local and are not server settings:

- `KELVIN_API_URL`
- `KELVIN_API_TIMEOUT_SECONDS`
- `KELVIN_WORKSPACE_ID`
- `KELVIN_WORKSPACE_PATH`

---

## 9. Stable Local UI Routes

The local operational UI is a supported operator surface for v1.0:

- `/ui`
- `/ui/runs`
- `/ui/approvals`
- `/ui/audit`
- `/ui/settings`
- `/ui/n8n`

The exact HTML, CSS, and JavaScript module internals are not a public API.
Operators should rely on the visible workflow documented in
`docs/operational-runbooks.md`.

When `KELVIN_API_AUTH_MODE=required`, the UI must let the local operator provide
a raw bearer token for the current browser session. The token is attached as
`Authorization: Bearer <token>` to protected API calls and is kept in
`sessionStorage`, not in server-rendered HTML, Git, or permanent local storage.

---

## 10. Intentionally Unstable or Internal Surfaces

These are not frozen as v1.0 public contracts:

- Python module paths under `backend/src/kelvin_assistant`.
- Internal repository, service, adapter, and port class names.
- Database table layout and migration internals.
- Generated OpenAPI schema component names.
- Static asset filenames under `/static`.
- Exact wording of human-readable `detail`, `reason`, and `error` strings.
- n8n exported workflow node IDs, positions, and editor metadata.
- Development-only scripts unless they are explicitly referenced by a runbook.

Internal surfaces may change in any minor patch when the stable route, schema,
scope, and configuration behavior remains compatible.
