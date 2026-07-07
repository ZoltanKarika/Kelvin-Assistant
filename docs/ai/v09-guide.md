# v0.9 Messaging — Implementation Guide

This document tracks the progress of v0.9 and provides step-by-step instructions for implementing two-way messaging workflows through n8n.

Related documents:

- [Fejlesztési roadmap](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/roadmap.md) — milestone definitions and acceptance criteria.
- [v0.7 Safe n8n Foundation](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/n8n-integration.md) — architecture, security boundaries, and credential rules.
- [v0.8 AI Security & Integration Hardening](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/ai/v08-guide.md) — firewall rules, context guards, and security gating.

---

## Current Progress

### Steps Table

| Step | Item | Depends on | Branch suggestion | Status |
|---|---|---|---|---|
| **1** | Message Domain Model & Channel Policy | — | `feat/v0.9-message-domain` | ⏳ |
| **2** | Inbound Message Route & Normalizer | #1 | `feat/v0.9-inbound-route` | ⏳ |
| **3** | Message Deduplication Middleware | #2 | `feat/v0.9-message-dedup` | ⏳ |
| **4** | Session Binding (Thread-to-Session Resolver) | #2 | `feat/v0.9-session-binding` | ⏳ |
| **5** | Rate Limiting for Messaging | #2 | `feat/v0.9-rate-limiting` | ⏳ |
| **6** | Extended Audit Logs for Messaging | #4 | `feat/v0.9-messaging-audit` | ⏳ |
| **7** | First n8n Slack Workflow (Incoming & Reply) | #1–#6 | `feat/v0.9-slack-workflow` | ⏳ |
| **8** | Optional WhatsApp Business Workflow | #7 | `feat/v0.9-whatsapp-workflow` | ⏳ |
| **9** | First Local Workflow (Matrix or Mattermost) | #7 | `feat/v0.9-local-messaging` | ⏳ |
| **10** | Error Handling & Fallback Replies | #7 | `feat/v0.9-messaging-resilience` | ⏳ |
| **11** | End-to-End Testing & Roadmap Verification | #7–#10 | `chore/v0.9-completion` | ⏳ |

---

## Step-by-Step Instructions

Each step below is designed as a single PR. Work one step at a time.

---

### Step 1: Message Domain Model & Channel Policy

**Goal:** Create domain models for external messaging, and enforce user/channel allowlists to restrict access to trusted platforms and users.

**What to do:**

1. Create `backend/src/kelvin_assistant/domain/messaging.py` with:
   - `ExternalMessage` value object containing: `platform`, `channel_id`, `thread_id`, `user_id`, `message_id`, `text`.
   - `ChannelPolicy` configuration mapping platforms to lists of allowed channel/user IDs.
   - `is_authorized(platform: str, channel_id: str, user_id: str) -> bool` check against configured lists.
2. Load messaging configuration in `backend/src/kelvin_assistant/config/` (add `KELVIN_ALLOWED_CHANNELS` and `KELVIN_ALLOWED_USERS` as environment configurations or JSON config files).
3. Create unit tests in `tests/unit/domain/test_messaging.py`.

**Commit message:**

```text
feat(domain): implement message domain model and channel policy allowlists
```

---

### Step 2: Inbound Message Route & Normalizer

**Goal:** Add a dedicated REST API endpoint that receives, validates, and normalizes incoming message payloads from n8n.

**What to do:**

1. Create a new router `backend/src/kelvin_assistant/api/messaging_routes.py`:
   - POST `/api/v1/messages/inbound` route accepting `InboundMessageRequest` schema.
   - Inject the messaging dependency and scope validate (must have `kelvin:read` or a new `messaging:inbound` scope).
   - Use `ChannelPolicy` to authorize the incoming message source.
2. Register the router in `backend/src/kelvin_assistant/api/app.py`.
3. Create integration tests in `tests/integration/api/test_messaging_routes.py`.

**Commit message:**

```text
feat(api): add inbound message route and payload normalization
```

---

### Step 3: Message Deduplication Middleware

**Goal:** Implement a deduplication check to prevent replay attacks or duplicate processing of external events (especially Slack retries).

**What to do:**

1. Create `backend/src/kelvin_assistant/application/message_dedup.py`:
   - `MessageDeduplicator` utilizing PostgreSQL or an in-memory/Redis cache to track processed `(platform, message_id)` keys.
   - Save successful processing tokens with an expiration window (e.g., 24 hours).
2. Integrate this validator in the inbound message route before parsing the request or as a specialized check inside `messaging_routes.py`.
3. Create unit tests in `tests/unit/application/test_message_dedup.py`.

**Commit message:**

```text
feat(application): implement message deduplication logic for external events
```

---

### Step 4: Session Binding (Thread-to-Session Resolver)

**Goal:** Resolve or bind an external platform channel and thread ID to a unique Kelvin `Session`.

**What to do:**

1. Create `backend/src/kelvin_assistant/application/session_resolver.py`:
   - `resolve_session(platform: str, channel_id: str, thread_id: str | None) -> UUID`
   - Maps the unique external channel/thread coordinates to a persistent `SessionID`. If no session exists, it creates one.
   - Apply configurable idle session timeout (after which a new session is initialized).
2. Update the chat dispatch in `messaging_routes.py` to forward normalized messages to the respective resolved session.
3. Write unit tests in `tests/unit/application/test_session_resolver.py`.

**Commit message:**

```text
feat(application): implement thread-to-session resolution logic
```

---

### Step 5: Rate Limiting for Messaging

**Goal:** Add rate-limiting capabilities on a per-user and per-channel basis to prevent DoS attacks via external platforms.

**What to do:**

1. Create `backend/src/kelvin_assistant/api/messaging_rate_limiter.py` that checks requests per user/channel within window limits.
2. Integrate the rate limiter with `/api/v1/messages/inbound`.
3. Create unit tests verifying rate limits are enforced and return standard HTTP 429 errors.

**Commit message:**

```text
feat(api): implement message rate limiting for inbound events
```

---

### Step 6: Extended Audit Logs for Messaging

**Goal:** Extend the PostgreSQL audit log schema to link the external message metadata, n8n run identifier, and the Kelvin agent session execution.

**What to do:**

1. Update audit schemas and models in `backend/src/kelvin_assistant/ports/` and `domain/` to support external platform audit fields: `external_message_id`, `n8n_run_id`, `channel_id`.
2. Ensure `InputGuard` and `OutputGuard` decisions are tied into these audit structures without logging the masked sensitive secrets.
3. Write database integration tests in `tests/integration/test_messaging_audit.py`.

**Commit message:**

```text
feat(observability): extend audit logs to track external messaging identifiers
```

---

### Step 7: First n8n Slack Workflow (Incoming & Reply)

**Goal:** Build and export the first cloud-integrated n8n workflow for Slack that normalizes payloads, handles slack retries (3-second rules), sends payloads to Kelvin, and relays responses.

**What to do:**

1. Construct the Slack workflow in the self-hosted n8n editor.
2. Setup immediate Slack acknowledgment (to satisfy the 3-second reply limit).
3. Call the normalized `/api/v1/messages/inbound` endpoint.
4. Export the n8n workflow JSON, strip credentials, and save it in `infrastructure/n8n/workflows/slack_messaging.json`.
5. Add configuration instructions to `docs/n8n-credential-setup.md`.

**Commit message:**

```text
chore(n8n): add secretless slack messaging workflow configuration
```

---

### Step 8: Optional WhatsApp Business Workflow

**Goal:** Implement a WhatsApp Business Platform workflow for remote interaction.

**What to do:**

1. Design the n8n WhatsApp workflow mapping user incoming text to Kelvin.
2. Handle the Meta webhook verification request challenge.
3. Export the workflow JSON to `infrastructure/n8n/workflows/whatsapp_messaging.json`.
4. Document Meta API and phone number registration details.

**Commit message:**

```text
chore(n8n): add optional whatsapp business platform workflow
```

---

### Step 9: First Local Workflow (Matrix or Mattermost)

**Goal:** Build a local self-hosted messaging workflow using Matrix or Mattermost to support local, offline-first operation.

**What to do:**

1. Create a Matrix or Mattermost n8n integration workflow.
2. Export the workflow to `infrastructure/n8n/workflows/local_messaging.json`.
3. Document local setup configuration parameters in `docs/n8n-credential-setup.md`.

**Commit message:**

```text
chore(n8n): add local matrix/mattermost offline messaging workflow
```

---

### Step 10: Error Handling & Fallback Replies

**Goal:** Ensure external messaging failures do not block Kelvin, and configure n8n error workflows to reply gracefully on target platforms.

**What to do:**

1. Setup an n8n Error Trigger workflow that replies with a standard "Kelvin is currently offline or did not respond in time" message when Kelvin backend returns errors or times out.
2. Implement fallback paths to guarantee local Windows CLI/API functionality works unaffected during external messaging service outages.
3. Document troubleshooting steps.

**Commit message:**

```text
docs: document messaging resilience guidelines and configure n8n error triggers
```

---

### Step 11: End-to-End Testing & Roadmap Verification

**Goal:** Validate all acceptance criteria, verify backup/restore compatibility for messaging configurations, and finalize the roadmap.

**What to do:**

1. Run full end-to-end flow checks (Slack/Matrix message -> n8n -> Kelvin -> response).
2. Perform mock prompt injection attacks over Slack to ensure they are blocked by `InputGuard` and audited safely.
3. Update `docs/roadmap.md` and mark v0.9 as complete.

**Commit message:**

```text
docs: finalize v0.9 milestone and update development roadmap
```

---

## v0.9 Acceptance Criteria Mapping

| Acceptance Criterion | Step |
|---|---|
| elsődlegesen n8n kommunikációs node-ok használata | #7, #8, #9 |
| bejövő üzenetek normalizálása Kelvin API-kérésre | #2 |
| chatcsatorna, beszélgetésszál és felhasználó Kelvin sessionhöz rendelése | #4 |
| engedélyezett felhasználók és csatornák allowlistje | #1, #2 |
| üzenetazonosítók deduplikálása és újrapróbálható feldolgozás | #3 |
| első felhős workflow Slackhez | #7 |
| opcionális WhatsApp Business Platform workflow | #8 |
| első helyi workflow Matrix vagy Mattermost rendszerhez | #9 |
| hozzáférési tokenek kizárólag az n8n credential store-ban | #7, #8, #9 |
| auditkapcsolat a külső üzenet, az n8n workflow és a Kelvin agentfutás között | #6 |
| távoli chatből indított állapotváltoztatás helyi jóváhagyást igényel | #11 |
| a külső szolgáltatás kiesése nem akadályozza a helyi chat működését | #10 |
