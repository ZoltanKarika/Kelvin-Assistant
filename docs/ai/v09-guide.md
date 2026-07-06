# v0.9 Messaging — Implementation Guide

This document tracks the progress of v0.9 and provides step-by-step
instructions for the Gemini CLI to implement two-way messaging integrations
via n8n workflows.

Related documents:
- [Fejlesztési roadmap](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/roadmap.md) — milestone definitions and acceptance criteria.
- [v0.7 Safe n8n Foundation](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/n8n-integration.md) — architecture, security boundaries, and credential rules.

---

## Current Progress

### Remaining

| Step | Item | Depends on | Branch suggestion | Status |
|---|---|---|---|---|
| **1** | Database Schema for Chat Sessions & Message Logging | — | `feat/v0.9-database-schema` | ⬜ |
| **2** | Message Deduplication & Idempotency logic | #1 | `feat/v0.9-deduplication` | ⬜ |
| **3** | User and Channel Allowlist Enforcement | — | `feat/v0.9-allowlist` | ⬜ |
| **4** | Normalized Incoming Message API Endpoint | #1, #2, #3 | `feat/v0.9-incoming-api` | ⬜ |
| **5** | Connected Audit Logs (Chat -> n8n -> Agent Run) | #4 | `feat/v0.9-audit-logs` | ⬜ |
| **6** | Windows CLI Local Write Approval Safeguard | — | `feat/v0.9-local-approval` | ⬜ |
| **7** | Matrix/Mattermost Local Integration Workflow | #4 | `feat/v0.9-matrix-workflow` | ⬜ |
| **8** | Slack Cloud Integration Workflow | #4 | `feat/v0.9-slack-workflow` | ⬜ |
| **9** | n8n Credential Store Integration Verification | — | `feat/v0.9-credentials` | ⬜ |
| **10** | Full v0.9 Messaging Verification & Integration Tests | #1-#9 | `feat/v0.9-verification` | ⬜ |

---

## Step-by-Step Instructions

Each step below is designed as a single PR. Work one step at a time.

---

### Step 1: Database Schema for Chat Sessions & Message Logging

**Goal:** Create the database tables to map external chat conversations (platform, channel, thread, user) to Kelvin sessions and store incoming message IDs.

**What to do:**
1. Create a migration or schema update adding a `chat_sessions` table mapping `(platform, external_channel_id, external_user_id)` to a Kelvin `session_id`.
2. Create an `incoming_messages` log table containing columns: `id` (UUID), `platform`, `external_message_id`, `received_at`.
3. Update database adapters to query and write to these tables.

**Commit message:**
```text
feat(db): add chat_sessions and incoming_messages tables
```

---

### Step 2: Message Deduplication & Idempotency logic

**Goal:** Implement robust logic to ignore duplicate webhook triggers sent by messaging platforms.

**What to do:**
1. Build a helper/service checking if an `(platform, external_message_id)` pair already exists in the `incoming_messages` table.
2. If it exists, return/skip processing immediately.
3. If it does not exist, log it and proceed.

**Commit message:**
```text
feat(messaging): implement message deduplication logic
```

---

### Step 3: User and Channel Allowlist Enforcement

**Goal:** Guard the messaging interface by ensuring only authorized users and channels can interact with Kelvin.

**What to do:**
1. Add settings configuration for `allowed_chat_users: tuple[str, ...]` and `allowed_chat_channels: tuple[str, ...]`.
2. Build middleware or a dependency check rejecting requests originating from non-allowlisted users or channels.

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
     "platform": "slack|matrix|mattermost",
     "message_id": "string",
     "channel_id": "string",
     "user_id": "string",
     "text": "string"
   }
   ```
2. Integrate allowlist checks, deduplication, and map it to a session.
3. Respond with a normalized Kelvin message response structure.

**Commit message:**
```text
feat(api): implement normalized incoming messaging endpoint
```

---

### Step 5: Connected Audit Logs (Chat -> n8n -> Agent Run)

**Goal:** Keep audit logs traceable from the external message down to the agent run.

**What to do:**
1. Update the security audit database model to link `external_message_id` and `n8n_execution_id` (via headers/payload) to any agent runs triggered by a message.
2. Ensure audit logs are fully queryable.

**Commit message:**
```text
feat(audit): connect chat message and n8n execution IDs to agent runs
```

---

### Step 6: Windows CLI Local Write Approval Safeguard

**Goal:** Enforce that write operations proposed via external chat trigger a local validation prompt on the Windows client and cannot execute silently.

**What to do:**
1. Harden tool execution policies: any write operation proposed in a session initiated via an external messaging platform must mark the status as "Awaiting local approval".
2. The local `kelvin` CLI client must retrieve and prompt for manual review on these runs.

**Commit message:**
```text
feat(cli): require local user approval for write tools triggered via chat
```

---

### Step 7: Matrix/Mattermost Local Integration Workflow

**Goal:** Build the n8n workflow for local, self-hosted chat platforms.

**What to do:**
1. Create `infrastructure/n8n/workflows/chat_matrix.json` (or Mattermost equivalent).
2. Ensure webhook handles incoming user text, normalizes it, sends it to `/api/v1/messaging/incoming` (with header authentication), and posts the response back.

**Commit message:**
```text
chore(n8n): add Matrix integration workflow
```

---

### Step 8: Slack Cloud Integration Workflow

**Goal:** Build the n8n workflow for Slack integration.

**What to do:**
1. Create `infrastructure/n8n/workflows/chat_slack.json`.
2. Connect Slack Events API to n8n, handle URL verification, normalize messages, and invoke the Kelvin API.

**Commit message:**
```text
chore(n8n): add Slack integration workflow
```

---

### Step 9: n8n Credential Store Integration Verification

**Goal:** Verify credentials security configuration.

**What to do:**
1. Audit workflow files to ensure Slack OAuth, Matrix logins, and other external credentials exist solely inside n8n's encrypted store, never inside the Kelvin codebase.

**Commit message:**
```text
test(security): audit workflows for zero-secret exposure
```

---

### Step 10: Full v0.9 Messaging Verification & Integration Tests

**Goal:** Write integration tests verifying the full flow under simulated messaging inputs.

**What to do:**
1. Create `tests/integration/test_messaging.py`.
2. Mock n8n payloads to `/api/v1/messaging/incoming` and verify deduplication, allowlist blocks, and session routing.

**Commit message:**
```text
test(integration): verify two-way messaging pipeline
```

---

## v0.9 Acceptance Criteria Mapping

| Acceptance Criterion | Step |
|---|---|
| n8n kommunikációs node-ok használata | #7, #8 |
| Bejövő üzenetek normalizálása | #4 |
| Chatcsatorna, beszélgetésszál Kelvin sessionhöz rendelése | #1, #4 |
| Engedélyezett felhasználók és csatornák allowlistje | #3 |
| Üzenetazonosítók deduplikálása és újrapróbálhatóság | #2 |
| Első felhős workflow Slackhez | #8 |
| Első helyi workflow Matrix/Mattermost | #7 |
| Hozzáférési tokenek kizárólag az n8n store-ban | #9 |
| Auditkapcsolat (külső üzenet -> n8n -> Kelvin agent) | #5 |
| Távoli chatből indított író művelet helyi Windows jóváhagyást igényel | #6 |
