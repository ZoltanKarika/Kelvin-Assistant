# v0.7 Safe n8n Foundation — Implementation Guide

This document tracks the progress of v0.7 and provides step-by-step
instructions for the Gemini CLI to implement the remaining work.

Related documents:

- `docs/roadmap.md` — milestone definitions and acceptance criteria.
- `docs/n8n-integration.md` — architecture, security boundaries, credential
  rules, and the implementation order.
- `docs/decisions/0013-self-hosted-n8n-automation.md` — ADR for n8n.
- `docs/decisions/0014-scoped-api-tokens.md` — ADR for API scopes.

---

## Current Progress

### Completed

| # | Item | PR/Commit | Status |
|---|------|-----------|--------|
| 1 | Automation VM created (Ubuntu 24.04) | Manual | ✅ |
| 2 | Docker Engine + Compose on automation VM | Manual | ✅ |
| 3 | n8n + PostgreSQL Compose stack | PR #56 | ✅ |
| 4 | Encryption key, secrets, owner account | Manual | ✅ |
| 5 | Reboot auto-start verified | Manual | ✅ |
| 6 | Scoped API token core (`domain/auth`, `ports/auth`, adapter) | PR #52 | ✅ |
| 7 | All API endpoints secured with scope checks | PR #53, #54, #55 | ✅ |
| 8 | `api-tokens.example.json` reference file | PR #54 | ✅ |
| 9 | Auth dependency tests | PR #54 | ✅ |
| 10 | Initial n8n workflows (health check, chat) | PR #56 | ✅ |
| 12 | n8n credential setup guide | #11 merged | ✅ |
| 13 | Minimum AI Firewall (input sanitizer) | — | ✅ |
| 14 | Correlation ID for workflow ↔ agent tracing | — | ✅ |
| 15 | First codebase updater workflow (full pipeline) | #12, #13 | ✅ |
| 16 | Source allowlist and rate limiting | #13 | ✅ |
| 17 | Backup/restore validation | #15 | ✅ |
| 18 | Update roadmap.md with v0.7 completion notes | #17 | ✅ |

---

## Step-by-Step Instructions

Each step below is designed as a single PR. Work one step at a time.

---

### Step 12: n8n Credential Setup Guide

**Goal:** Document how to create the Kelvin API token in n8n so that the
updater workflow can authenticate with the Kelvin API.

**What to do:**

1. Create `docs/n8n-credential-setup.md` with:
   - How to create an `api-tokens.json` file on the Kelvin VM
     (reference `api-tokens.example.json` for the format).
   - How to set `KELVIN_API_AUTH_MODE=required` and
     `KELVIN_API_TOKEN_FILE` in the Kelvin VM `.env`.
   - How to restart the Kelvin service.
   - How to create an "HTTP Header Auth" credential in n8n UI:
     - Header name: `Authorization`
     - Header value: `Bearer <token-value-from-api-tokens.json>`
   - How to test it: manually run the Health Check workflow.
   - Troubleshooting: common errors (401 = wrong token, 403 = wrong scope).

2. Update `infrastructure/n8n/README.md` to link to the new guide.

**Files to change:**

- `docs/n8n-credential-setup.md` [NEW]
- `infrastructure/n8n/README.md` [MODIFY — add link]

**Testing:** No code changes; review docs only.

**Commit message:**

```
docs: add n8n credential setup guide
```

---

### Step 13: Minimum AI Firewall (Input Sanitizer)

**Goal:** Build a lightweight input sanitizer that strips prompt injection
markers and masks secrets before external content is passed to the LLM.

This is the **most important remaining backend work** for v0.7.

**What to do:**

1. Create `backend/src/kelvin_assistant/domain/firewall.py`:
   - `sanitize_external_content(text: str) -> SanitizedContent` — wraps
     external text in data delimiters (e.g., `--- BEGIN EXTERNAL DATA ---`
     / `--- END EXTERNAL DATA ---`) so the LLM treats it as data, not
     instructions.
   - `mask_secrets(text: str) -> str` — regex-based masking of common secret
     patterns: API keys (`sk-...`, `ghp_...`), connection strings
     (`postgres://...`), `.env` values (`SECRET_KEY=...`), PEM blocks.
   - `detect_injection(text: str) -> list[str]` — returns a list of
     suspicious patterns found (e.g., "ignore previous instructions",
     "system:", tool-call syntax). This is informational, not blocking.

2. Create `tests/unit/domain/test_firewall.py`:
   - Test secret masking for each pattern type.
   - Test that external content wrapping produces correct delimiters.
   - Test injection detection catches known patterns.
   - Test that clean content passes through unchanged.

**Key design decisions:**

- This is a **domain module** — no FastAPI or adapter dependencies.
- v0.7 is detection + masking only; hard blocking is v0.8.
- Use `dataclass` for `SanitizedContent` with fields: `text`, `source_url`,
  `fetched_at`, `injection_warnings`.

**Files to change:**

- `backend/src/kelvin_assistant/domain/firewall.py` [NEW]
- `tests/unit/domain/test_firewall.py` [NEW]

**Testing:**

```bash
uv run pytest tests/unit/domain/test_firewall.py -v
uv run ruff check backend tests scripts
uv run mypy backend/src tests scripts
```

**Commit message:**

```
feat(domain): add minimum AI Firewall input sanitizer

- External content wrapping with data delimiters.
- Secret pattern masking (API keys, connection strings, PEM blocks).
- Prompt injection detection (informational, not blocking).
```

---

### Step 14: Correlation ID for Workflow ↔ Agent Tracing

**Goal:** Add an optional `correlation_id` header to the Kelvin API so that
n8n workflow executions can be traced back to Kelvin chat/agent responses.

**What to do:**

1. Add middleware or dependency in `backend/src/kelvin_assistant/api/app.py`
   that reads the `X-Correlation-ID` request header (if present) or generates
   a new UUID.
2. Store it in the request state so it is available to all route handlers.
3. Include it in the JSON response body under `correlation_id`.
4. Log it in structured log entries.

**Files to change:**

- `backend/src/kelvin_assistant/api/app.py` [MODIFY]
- `backend/src/kelvin_assistant/api/chat_routes.py` [MODIFY — include in
  response]
- `tests/unit/api/test_correlation_id.py` [NEW]

**Testing:**

```bash
uv run pytest tests/unit/api/test_correlation_id.py -v
uv run pytest tests/ -q
```

**Commit message:**

```
feat(api): add X-Correlation-ID header support

- Reads correlation ID from request header or generates a new UUID.
- Includes correlation_id in JSON responses.
- Enables n8n workflow ↔ Kelvin request tracing.
```

---

### Step 15: First Codebase Updater Workflow (Full Pipeline)

**Goal:** Build the complete updater workflow in n8n (`updater_v1.json`) to automatically fetch codebase updates from an RSS feed, extract structured details using Gemini, and trigger a Kelvin agent run to implement the changes.

**Prerequisites:** Steps 12 and 13 must be completed first.

**What to do:**

1. Create `infrastructure/n8n/workflows/updater_v1.json` with nodes:
   - Manual Trigger (later: Schedule Trigger)
   - Set URLs (defines `api_url` and `rss_feed_url` dynamically)
   - RSS Feed Read (fetches from the feed URL)
   - Information Extractor (uses Google Gemini Chat Model to extract `update_type`, `target_component`, and `update_details` from the RSS content)
   - HTTP Request - Trigger Kelvin Agent Run (POST to `{{ $('Set URLs').item.json.api_url }}/api/v1/agent/runs` using the `agent:execute` credential to trigger a new agent run)

2. Update `infrastructure/n8n/README.md` to document the workflow.

**Important constraints:**

- The Google Gemini API key goes into n8n credential store, NOT into the workflow JSON. Use a placeholder credential reference in the exported JSON.
- The Kelvin token uses the HTTP Header Auth credential with `agent:execute` scope.
- All URLs use the Set node pattern (no `$env`).

**Files to change:**

- `infrastructure/n8n/workflows/updater_v1.json` [NEW]
- `infrastructure/n8n/README.md` [MODIFY]

**Testing:** Manual execution in n8n UI. Document results.

**Commit message:**

```
feat(n8n): add first codebase updater workflow v1

- RSS source -> Gemini information extraction -> Kelvin Agent execution pipeline.
- Uses Set node pattern for configurable URLs.
- Kelvin credential with agent:execute scope; Gemini key in n8n credential store.
```

---

### Step 16: Source Allowlist and Rate Limiting

**Goal:** Add a configurable allowlist of approved source URLs and basic
rate/cost limits for the updater workflow.

**What to do:**

1. Add to `backend/src/kelvin_assistant/config/settings.py`:
   - `allowed_sources: tuple[str, ...] = ()` — approved source URL prefixes.
   - `max_external_requests_per_hour: int = 100`
   - `max_ai_cost_per_day_usd: float = 1.0`

2. Add domain logic in `backend/src/kelvin_assistant/domain/firewall.py`:
   - `is_source_allowed(url: str, allowlist: tuple[str, ...]) -> bool`

3. Add tests in `tests/unit/domain/test_firewall.py`:
   - Test URL prefix matching.
   - Test empty allowlist blocks everything.
   - Test exact and wildcard prefix matches.

**Files to change:**

- `backend/src/kelvin_assistant/config/settings.py` [MODIFY]
- `backend/src/kelvin_assistant/domain/firewall.py` [MODIFY]
- `tests/unit/domain/test_firewall.py` [MODIFY]

**Testing:**

```bash
uv run pytest tests/unit/domain/test_firewall.py -v
uv run pytest tests/ -q
```

**Commit message:**

```
feat(domain): add source allowlist and rate limit settings

- URL prefix matching for approved external sources.
- Configurable request/hour and cost/day limits.
```

---

### Step 17: Backup/Restore Validation

**Goal:** Document and validate the backup and restore procedures for both
the Kelvin VM and the automation VM.

**What to do:**

1. Create `docs/backup-restore.md` with sections for:
   - Kelvin PostgreSQL dump and restore.
   - n8n PostgreSQL dump and restore.
   - n8n volume backup.
   - Encryption key backup (separate from data).
   - Hyper-V checkpoint usage and cleanup.
   - Full restore test procedure.

2. Add a `scripts/backup-kelvin-db.sh` helper script (optional).

**Files to change:**

- `docs/backup-restore.md` [NEW]
- `scripts/backup-kelvin-db.sh` [NEW, optional]

**Testing:** Manual — perform a backup and restore on the VMs.

**Commit message:**

```
docs: add backup and restore guide for Kelvin and n8n
```

---

### Step 18: Update Roadmap with v0.7 Completion Notes

**Goal:** Update `docs/roadmap.md` to mark v0.7 items as done and record
validation results.

**What to do:**

1. In `docs/roadmap.md`:
   - Change v0.7 status from `Tervezett` to `Kész`.
   - Add a "Production validáció" section listing what was verified.
   - Check off all acceptance criteria in the acceptance list.
2. In `docs/n8n-integration.md`:
   - Check off the acceptance criteria checklist items.
3. Update this file (`docs/ai/v07-guide.md`) to mark all items complete.

**Files to change:**

- `docs/roadmap.md` [MODIFY]
- `docs/n8n-integration.md` [MODIFY]
- `docs/ai/v07-guide.md` [MODIFY]

**Testing:** No code changes; review docs only.

**Commit message:**

```
docs: mark v0.7 Safe n8n Foundation as complete
```

---

## v0.7 Acceptance Criteria Mapping

Each roadmap acceptance criterion mapped to the step that satisfies it:

| Acceptance Criterion | Step |
|---|---|
| Separate automation VM with Ubuntu 24.04 | #1 (done) |
| n8n + PostgreSQL under Docker Compose | #3 (done) |
| No `latest` image tags | #3 (done) |
| n8n UI only from trusted network | #1 (done) |
| PostgreSQL port not published | #3 (done) |
| Encryption key and DB backup separable | #17 |
| Kelvin API uses token + scope auth | #7 (done) |
| Researcher workflow uses read-only credential | #15 |
| Online AI key not in Kelvin/Git/workflow export | #15 |
| Researcher workflow produces referenced proposal | #15 |
| Web prompt injection cannot trigger Kelvin tools | #13 |
| n8n cannot bypass Windows agent approval | #7 (done — scope separation) |
| Kelvin works when n8n is down | Architecture (done — separate VMs) |
| Reboot, backup, restore verified | #17 |
| Temporary checkpoints cleaned up | #17 |

---

## How to Use This Guide with the Gemini CLI

When starting a new session, tell the Gemini CLI:

```
Read docs/ai/v07-guide.md and implement step <N>.
```

The CLI will:

1. Read this file to understand context and progress.
2. Read the referenced design documents for architecture details.
3. Follow `docs/ai/implementation-rules.md` for the single-task workflow.
4. Follow `docs/ai/git-workflow.md` for branch and commit safety.
5. Run the quality checks from `GEMINI.md` after changes.
6. Summarize the changes and suggest a commit message.

After each step is merged, update the "Current Progress" table above to
mark the step as done.
