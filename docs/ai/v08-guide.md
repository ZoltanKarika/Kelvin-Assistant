# v0.8 AI Security & Integration Hardening — Implementation Guide

This document tracks the progress of v0.8 and provides step-by-step
instructions for the Gemini CLI to implement the AI Security Gateway
("Firewall for AI") and integration hardening.

Related documents:

- [Fejlesztési roadmap](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/roadmap.md) — milestone definitions and acceptance criteria.
- [v0.7 Safe n8n Foundation](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/n8n-integration.md) — architecture, security boundaries, and credential rules.

---

## Current Progress

### Remaining

| Step | Item | Depends on | Branch suggestion | Status |
|---|---|---|---|---|
| **1** | Input Guard & Prompt Injection Defense | — | `feat/v0.8-input-guard` | ✅ |
| **2** | Context Guard & Source Trust Boundaries | #1 | `feat/v0.8-context-guard` | ✅ |
| **3** | Output Guard & Secret Masking | #1 | `feat/v0.8-output-guard` | ✅ |
| **4** | Tool Guard & Secure Write Approvals | — | `feat/v0.8-tool-guard` | ✅ |
| **5** | Connected Audit Logs & Security Decisions | #1, #3 | `feat/v0.8-security-audit` | ✅ |
| **6** | API Hardening (Scope validation, Token rotation, Revocation) | — | `feat/v0.8-api-hardening` | ✅ |
| **7** | Network Resilience & Webhook/Source Allowlists | — | `feat/v0.8-network-resilience` | ✅ |
| **8** | Context Pruning & Secondary Credentials | — | `feat/v0.8-context-pruning` | ✅ |
| **9** | Kelvin Containerization Trial | — | `chore/v0.8-container-trial` | ✅ |
| **10** | Secretless Workflow Exports & Backup Verification | #9 | `chore/v0.8-completion` | ✅ |

---

## Step-by-Step Instructions

Each step below is designed as a single PR. Work one step at a time.

---

### Step 1: Input Guard & Prompt Injection Defense

**Goal:** Build a robust `InputGuard` that scans user prompts or n8n workflow
inputs for dangerous intent, credential requests, and prompt injection
techniques before passing them to the LLM.

**What to do:**

1. Create `backend/src/kelvin_assistant/domain/input_guard.py` with:
   - `detect_dangerous_intent(text: str) -> list[str]` — scans for phrases
     asking to run arbitrary commands, edit host files directly, delete files
     outside of workspace, or bypass security rules.
   - `detect_credential_requests(text: str) -> list[str]` — scans for
     requests asking to read `.env` files, read ssh private keys, extract
     passwords, or print database connection strings.
   - `detect_advanced_injection(text: str) -> list[str]` — scans for
     jailbreaks, system prompt overrides ("ignore previous instructions", "you
     are now a root shell"), and XML/HTML-style tag escape tricks.
   - `validate_input(text: str) -> InputValidationResult` — combines checks
     and returns an outcome (`ALLOW`, `BLOCK`) with detail warnings.
2. Integrate this validator in
   `backend/src/kelvin_assistant/api/chat_routes.py` and `agent_routes.py`.
3. Create unit tests in `tests/unit/domain/test_input_guard.py`.

**Commit message:**

```text
feat(domain): implement InputGuard prompt injection and intent checks
```

---

### Step 2: Context Guard & Source Trust Boundaries

**Goal:** Implement a `ContextGuard` that wraps external data (from web fetch,
RAG documents, or local memories) in strict, un-escapable delimiters so that
the LLM treats it purely as data and never executes instructions embedded in
it.

**What to do:**

1. Create `backend/src/kelvin_assistant/domain/context_guard.py` with:
   - Context wrapping with strict data delimiters.
   - Stripping or escaping markers that might look like LLM instructions or
     end-of-wrapper boundaries.
   - Verifying that any text injected from RAG/Memory is filtered by the
     `InputGuard` (Step 1) to check for embedded injection attacks.
2. Update the chat and agent services to run RAG/Memory results through the
   `ContextGuard` before constructing the final LLM prompt context.
3. Write unit tests in `tests/unit/domain/test_context_guard.py`.

**Commit message:**

```text
feat(domain): implement ContextGuard for data/instruction separation
```

---

### Step 3: Output Guard & Secret Masking

**Goal:** Build an `OutputGuard` that filters LLM responses before they are
returned to n8n or the CLI client, masking any accidentally generated secrets
(passwords, connection strings, API tokens).

**What to do:**

1. Create `backend/src/kelvin_assistant/domain/output_guard.py`:
   - Expand `mask_secrets` logic to scan for PEM private keys, PostgreSQL
     connection strings, database passwords, and Bearer API tokens.
   - Provide a clean replacements list to mask these with placeholder strings
     (e.g., `[MASKED_CONNECTION_STRING]`).
2. Integrate this filter in all outgoing chat and agent API response
   serializers in `chat_routes.py` and `agent_routes.py`.
3. Write unit tests in `tests/unit/domain/test_output_guard.py`.

**Commit message:**

```text
feat(domain): implement OutputGuard secret masking middleware
```

---

### Step 4: Tool Guard & Secure Write Approvals

**Goal:** Solidify the tool policy checks (`ToolGuard`) to ensure write
operations can never bypass local user approval on the Windows host CLI client.

**What to do:**

1. Update `backend/src/kelvin_assistant/application/tool_policy.py`:
   - Strengthen verification of arguments in `file.patch` and future write
     tools.
   - Enforce that write actions *always* map to `REQUIRE_APPROVAL` status
     and never automatically transition to `EXECUTING` state.
2. Update the CLI client `kelvin.exe` to enforce that it displays complete
   file diffs and rejects execution if approval is denied or bypassed.
3. Write tests in `tests/unit/application/test_tool_policy.py`.

**Commit message:**

```text
feat(application): enforce ToolGuard policy rules and write approvals
```

---

### Step 5: Connected Audit Logs & Security Decisions

**Goal:** Create a unified audit log system connecting n8n workflow runs, Kelvin
agent runs, and tool executions, while ensuring blocked secrets are not logged.

**What to do:**

1. Update PostgreSQL schema to add audit relation tables.
2. Log all `InputGuard` and `OutputGuard` decisions (what was blocked/allowed)
   without saving raw credentials or prompt text that failed injection checks
   (mask them before logging!).
3. Write tests in `tests/unit/ports/test_audit_logging.py`.

**Commit message:**

```text
feat(observability): implement unified audit logs with secret masking
```

---

### Step 6: API Hardening (Scope validation, Token rotation, Revocation)

**Goal:** Add a token rotation and revocation guide and enforce strict scope
validation rules on all endpoints (e.g. key scope restrictions).

**What to do:**

1. Create `docs/token-management.md` documenting key rotation, scope
   limitations, and token revocation via the `api-tokens.json` file.
2. Strengthen scope checking logic in
   `backend/src/kelvin_assistant/api/dependencies.py` to prevent scope bypass.
3. Write test cases validating scope errors.

**Commit message:**

```text
feat(api): harden API token scope checks and write rotation guide
```

---

### Step 7: Network Resilience & Webhook/Source Allowlists

**Goal:** Implement UFW-based or FastAPI-level allowlists for webhooks and
source prefixes. Add idempotency keys, retry headers, and client-side timeouts.

**What to do:**

1. Add FastAPI middleware to validate incoming request IP origins against an
   allowlist in `.env` (e.g. matching `KELVIN_ALLOWED_CLIENTS`).
2. Set up idempotency check middleware (e.g. checking a `X-Idempotency-Key`
   header for agent execution runs).
3. Write tests in `tests/unit/api/test_network_resilience.py`.

**Commit message:**

```text
feat(api): implement origin allowlist and request idempotency checks
```

---

### Step 8: Context Pruning & Secondary Credentials

**Goal:** Minimize context sent to the coder/updater model by stripping out
directories like `.git`, `.venv`, and temporary test folders. Configure
secondary API keys safely in n8n.

**What to do:**

1. Update `LocalReadToolClient` workspace utilities to prune files using
   standard gitignore patterns.
2. Add instructions to `docs/n8n-credential-setup.md` explaining how to
   configure secondary credentials (e.g. OpenAI, Anthropic, or external Gemini
   keys) with minimal privileges in n8n.

**Commit message:**

```text
feat(cli): prune project context files and add provider credentials guide
```

---

### Step 9: Kelvin Containerization Trial

**Goal:** Test containerizing the Kelvin FastAPI server using Docker Compose on
a separate development port, while keeping the production `systemd` setup
intact on the `kelvin-ai` VM.

**What to do:**

1. Create a `Dockerfile.backend` and a `docker-compose.test.yaml` in the
   repository root.
2. Document the containerization test procedure in
   `docs/containerization-test.md`.
3. Verify that the Dockerized server passes all unit and integration tests.

**Commit message:**

```text
chore(docker): add test Dockerfile and compose file for backend VM
```

---

### Step 10: Secretless Workflow Exports & Backup Verification

**Goal:** Export n8n workflows safely without credentials, perform a complete
backup/restore validation test, and mark the v0.8 milestone as complete in the
roadmaps.

**What to do:**

1. Export all n8n workflows to `infrastructure/n8n/workflows/` (ensuring no
   hardcoded tokens or secrets are contained in the JSON).
2. Perform a backup and full restore following `docs/backup-restore.md`.
3. Update `docs/roadmap.md`, `docs/n8n-integration.md`, and this file
   (`docs/ai/v08-guide.md`) to mark v0.8 as complete.

**Commit message:**

```text
docs: mark v0.8 milestone as complete and save final workflows
```

---

## v0.8 Acceptance Criteria Mapping

| Acceptance Criterion | Step |
|---|---|
| Teljes AI Security Gateway ("Firewall for AI") | #1, #2, #3, #4 |
| Input guard (dangerous intent, credential check, prompt injection) | #1 |
| Context guard (separating instructions from RAG/Memory data) | #2 |
| Output guard (masking secrets/passwords/tokens/connection strings) | #3 |
| Determinisztikus tool guard és kötelező jóváhagyás | #4 |
| Biztonsági döntések auditja titkok elmentése nélkül | #5 |
| n8n és Kelvin közötti kulcsrotáció, scope-vizsgálat és visszavonás | #6 |
| Idempotens kérések, timeout, retry és hibautak | #7 |
| Workflow-, agent- és eszközfutások összekapcsolt auditja | #5 |
| Engedélyezett workflow-k, források és webhookok allowlistje | #7 |
| Szűrt, minimalizált projektkontextus kódoló ágenshez | #8 |
| Opcionális képgeneráló és külső LLM credential útmutató | #8 |
| Kelvin FastAPI konténerizálási próba külön tesztkörnyezetben | #9 |
| n8n workflow-k exportja titkok nélkül | #10 |
| PostgreSQL-, Kelvin-, n8n-adatok és encryption key mentés/visszaállítás | #10 |
| Health check, naplózás és hibakeresési útmutató | #10 |
