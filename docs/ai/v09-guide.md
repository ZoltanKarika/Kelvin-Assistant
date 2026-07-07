# v0.9 Messaging — Implementation Guide

This document tracks the progress of v0.9 and provides step-by-step instructions for implementing two-way messaging integrations via n8n workflows.

Related documents:

- [Fejlesztési roadmap](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/roadmap.md) — milestone definitions and acceptance criteria.
- [v0.7 Safe n8n Foundation](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/n8n-integration.md) — architecture, security boundaries, and credential rules.
- [v0.8 AI Security & Integration Hardening](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/ai/v08-guide.md) — firewall rules, context guards, and security gating.

---

## Current Progress

### Steps Table

| Step | Item | Depends on | Branch suggestion | Status |
|---|---|---|---|---|
| **1** | Database Schema & Domain Model for Sessions & Logging | — | `feat/v0.9-database-schema` | ⏳ |
| **2** | Message Deduplication & Idempotency Logic | #1 | `feat/v0.9-deduplication` | ⏳ |
| **3** | User and Channel Allowlist Enforcement | — | `feat/v0.9-allowlist` | ⏳ |
| **4** | Normalized Incoming Message API Endpoint | #1, #2, #3 | `feat/v0.9-incoming-api` | ⏳ |
| **5** | Rate Limiting for Messaging | #4 | `feat/v0.9-rate-limiting` | ⏳ |
| **6** | Connected Audit Logs (Chat -> n8n -> Agent Run) | #4 | `feat/v0.9-audit-logs` | ⏳ |
| **7** | Windows CLI Local Write Approval Safeguard | — | `feat/v0.9-local-approval` | ⏳ |
| **8** | Matrix/Mattermost Local Integration Workflow | #4 | `feat/v0.9-matrix-workflow` | ⏳ |
| **9** | Slack Cloud Integration Workflow | #4 | `feat/v0.9-slack-workflow` | ⏳ |
| **10** | WhatsApp Business Workflow & Credential Auditing | #9 | `feat/v0.9-whatsapp-credentials` | ⏳ |
| **11** | Error Handling, Fallbacks & Full E2E Verification | #1–#10 | `feat/v0.9-verification` | ⏳ |

---

## Step-by-Step Instructions

Each step below is designed as a single PR. Work one step at a time.

---

### Step 1: Database Schema & Domain Model for Sessions & Logging

**Goal:** Create database tables and domain models under hexagonal architecture to map external chat conversations (platform, channel, thread, user) to Kelvin sessions and store incoming message IDs.

**What to do:**

1. Create a migration or schema update adding a `chat_sessions` table mapping `(platform, external_channel_id, external_user_id)` to a Kelvin `session_id`.
2. Create an `incoming_messages` log table containing columns: `id` (UUID), `platform`, `external_message_id`, `received_at`.
3. Create `backend/src/kelvin_assistant/domain/messaging.py` containing value objects: `ExternalMessage`, `ChannelIdentity`, `ThreadIdentity`.
4. Update database adapters in `backend/src/kelvin_assistant/adapters/` to query and write to these tables.
5. Create unit tests in `tests/unit/domain/test_messaging.py`.

**Commit message:**

```text
feat(db): add chat_sessions and incoming_messages tables and domain models
```

---

### Step 2: Message Deduplication & Idempotency Logic

**Goal:** Implement robust logic to ignore duplicate webhook triggers sent by messaging platforms (e.g., Slack retry attempts).

**What to do:**

1. Create `backend/src/kelvin_assistant/application/message_dedup.py`:
   - `MessageDeduplicator` checking if a `(platform, external_message_id)` pair already exists in the `incoming_messages` table.
   - If it exists, return/skip processing immediately.
   - If it does not exist, log it and proceed.
2. Create unit tests in `tests/unit/application/test_message_dedup.py`.

**Commit message:**

```text
feat(messaging): implement message deduplication logic
```

---

### Step 3: User and Channel Allowlist Enforcement

**Goal:** Guard the messaging interface by ensuring only authorized users and channels can interact with Kelvin.

**What to do:**

1. Add settings configuration for `allowed_chat_users: tuple[str, ...]` and `allowed_chat_channels: tuple[str, ...]`.
2. Build middleware or a dependency check/policy rejecting requests originating from non-allowlisted users or channels.
3. Write unit tests in `tests/unit/domain/test_channel_policy.py`.

**Commit message:**

```text
feat(security): enforce user and channel allowlist for chat incoming webhook
```

---

### Step 4: Normalized Incoming Message API Endpoint

**Goal:** Implement the FastAPI entrypoint that receives normalized requests from n8n.

**What to do:**

1. Add `/api/v1/messaging/incoming` handling payload:
   ```json
   {
     "platform": "slack|matrix|mattermost|whatsapp",
     "message_id": "string",
     "channel_id": "string",
     "user_id": "string",
     "text": "string"
   }
   ```
2. Integrate allowlist checks, deduplication, and map it to a session.
3. Respond with a normalized Kelvin message response structure.
4. Create integration tests in `tests/integration/api/test_messaging_routes.py`.

**Commit message:**

```text
feat(api): implement normalized incoming messaging endpoint
```

---

### Step 5: Rate Limiting for Messaging

**Goal:** Implement rate-limiting capabilities on a per-user and per-channel basis to prevent DoS attacks via external platforms.

**What to do:**

1. Create `backend/src/kelvin_assistant/api/messaging_rate_limiter.py` checking requests per user/channel within window limits.
2. Integrate the rate limiter with `/api/v1/messaging/incoming`.
3. Create unit tests verifying rate limits are enforced and return standard HTTP 429 errors.

**Commit message:**

```text
feat(api): implement message rate limiting for inbound events
```

---

### Step 6: Connected Audit Logs (Chat -> n8n -> Agent Run)

**Goal:** Keep audit logs traceable from the external message down to the agent run.

**What to do:**

1. Update the security audit database model to link `external_message_id` and `n8n_execution_id` (via headers/payload) to any agent runs triggered by a message.
2. Ensure audit logs are fully queryable and that sensitive content masked by `OutputGuard` is not stored in plaintext logs.
3. Write database integration tests in `tests/integration/test_messaging_audit.py`.

**Commit message:**

```text
feat(audit): connect chat message and n8n execution IDs to agent runs
```

---

### Step 7: Windows CLI Local Write Approval Safeguard

**Goal:** Enforce that write operations proposed via external chat trigger a local validation prompt on the Windows client and cannot execute silently.

**What to do:**

1. Harden tool execution policies: any write operation proposed in a session initiated via an external messaging platform must mark the status as "Awaiting local approval".
2. The local `kelvin` CLI client must retrieve and prompt for manual review on these runs.
3. Update `backend/src/kelvin_assistant/application/tool_policy.py` to assert this constraint.

**Commit message:**

```text
feat(cli): require local user approval for write tools triggered via chat
```

---

### Step 8: Matrix/Mattermost Local Integration Workflow

**Goal:** Build the n8n workflow for local, self-hosted chat platforms.

**What to do:**

1. Create `infrastructure/n8n/workflows/chat_matrix.json` (or Mattermost equivalent).
2. Ensure webhook handles incoming user text, normalizes it, sends it to `/api/v1/messaging/incoming` (with header authentication), and posts the response back.
3. Save configurations in `docs/n8n-credential-setup.md`.

**Commit message:**

```text
chore(n8n): add Matrix integration workflow
```

---

### Step 9: Slack Cloud Integration Workflow

**Goal:** Build the n8n workflow for Slack integration.

**What to do:**

1. Create `infrastructure/n8n/workflows/chat_slack.json`.
2. Connect Slack Events API to n8n, handle URL verification, normalize messages, and invoke the Kelvin API.

**Commit message:**

```text
chore(n8n): add Slack integration workflow
```

---

### Step 10: WhatsApp Business Workflow & Credential Auditing

**Goal:** Implement the WhatsApp Business Platform workflow and verify credentials security configuration.

**What to do:**

1. Create `infrastructure/n8n/workflows/chat_whatsapp.json`.
2. Connect Meta webhooks to n8n, handle verification requests, and route payloads.
3. Audit workflow files to ensure Slack OAuth, WhatsApp tokens, Matrix logins, and other external credentials exist solely inside n8n's encrypted store, never inside the Kelvin codebase.

**Commit message:**

```text
chore(n8n): add WhatsApp workflow and verify credentials store configuration
```

---

### Step 11: Error Handling, Fallbacks & Full E2E Verification

**Goal:** Configure error handling fallback flows and run full end-to-end flow checks under simulated messaging inputs.

**What to do:**

1. Setup an n8n Error Trigger workflow that replies with a standard "Kelvin is currently offline or did not respond in time" message when Kelvin backend returns errors or times out.
2. Implement fallback paths to guarantee local Windows CLI/API functionality works unaffected during external messaging service outages.
3. Mock n8n payloads to `/api/v1/messaging/incoming` and verify deduplication, allowlist blocks, and session routing under simulated inputs.
4. Perform mock prompt injection attacks over external messaging to ensure they are blocked by `InputGuard` and audited safely.
5. Update `docs/roadmap.md` and mark v0.9 as complete.

**Commit message:**

```text
test(integration): verify two-way messaging pipeline and resilience fallbacks
```

---

## v0.9 Acceptance Criteria Mapping

| Acceptance Criterion | Step |
|---|---|
| elsődlegesen n8n kommunikációs node-ok használata külön Kelvin-adapterek helyett | #8, #9, #10 |
| bejövő üzenetek normalizálása Kelvin verziózott API-kérésre | #4 |
| chatcsatorna, beszélgetésszál és felhasználó Kelvin sessionhöz rendelése | #1, #4 |
| engedélyezett felhasználók és csatornák allowlistje | #3, #4 |
| üzenetazonosítók deduplikálása és újrapróbálható feldolgozás | #2 |
| első felhős workflow Slackhez | #9 |
| opcionális WhatsApp Business Platform workflow | #10 |
| első helyi workflow Matrix vagy Mattermost rendszerhez | #8 |
| hozzáférési tokenek kizárólag az n8n credential store-ban | #10 |
| auditkapcsolat a külső üzenet, az n8n workflow és a Kelvin agentfutás között | #6 |
| távoli chatből indított állapotváltoztatás továbbra is helyi jóváhagyást igényel | #7 |
| a külső szolgáltatás kiesése nem akadályozza a helyi chat vagy agent működését | #11 |
