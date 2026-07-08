# v0.9 Kelvin UI & Email Notifications - Implementation Guide

This document tracks the progress of v0.9 and provides step-by-step instructions for building Kelvin's first operational UI and email notification layer.

Related documents:

- [Fejlesztési roadmap](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/roadmap.md) - milestone definitions and acceptance criteria.
- [v0.7 Safe n8n Foundation](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/n8n-integration.md) - architecture, security boundaries, and credential rules.
- [v0.8 AI Security & Integration Hardening](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/ai/v08-guide.md) - firewall rules, context guards, and security gating.

---

## Current Progress

v0.9 is complete. The table below is retained as the implementation history and
is aligned with `docs/roadmap.md`.

### Steps Table

| Step | Item | Depends on | Branch suggestion | Status |
|---|---|---|---|---|
| **1** | UI Shell & Navigation Foundation | - | `feat/v0.9-ui-shell` | done |
| **2** | Agent Runs Dashboard | #1 | `feat/v0.9-runs-dashboard` | done |
| **3** | Local Approval Queue | #1, #2 | `feat/v0.9-approval-queue` | done |
| **4** | Audit Log Viewer | #1, #2, #3 | `feat/v0.9-audit-viewer` | done |
| **5** | Settings & Safety Controls | #1 | `feat/v0.9-settings` | done |
| **6** | n8n Status Panel | #1 | `feat/v0.9-n8n-status` | done |
| **7** | Email Notification Settings | #5 | `feat/v0.9-email-settings` | done |
| **8** | Approval Pending Email Notifications | #3, #7 | `feat/v0.9-approval-emails` | done |
| **9** | Run Completed/Failed Email Notifications | #2, #7 | `feat/v0.9-run-emails` | done |
| **10** | Daily Summary Email | #2, #4, #7 | `feat/v0.9-daily-summary` | done |
| **11** | UI & Email End-to-End Verification | #1-#10 | `feat/v0.9-ui-email-verification` | done |

---

## Scope

v0.9 focuses on Kelvin becoming easier and safer to operate locally.

In scope:

- a usable UI for runs, approvals, audit, settings, and n8n status;
- email notifications for approval pending, run completed, run failed, and daily summary events;
- preserving all existing local approval and audit guarantees.

Out of scope for v0.9:

- Slack integration;
- WhatsApp integration;
- Matrix or Mattermost chat integration;
- generic two-way messaging APIs.

Chat integrations can return in a later milestone after the UI approval and audit workflows are stable.

---

## Step-by-Step Instructions

Each step below is designed as a single PR. Work one step at a time.

---

### Step 1: UI Shell & Navigation Foundation

**Goal:** Replace the minimal chat-only UI surface with an operational Kelvin UI shell that can host dashboards and control panels.

**What to do:**

1. Create a clear app layout with navigation for Runs, Approvals, Audit, Settings, and n8n.
2. Keep the existing chat entrypoint available without breaking `/ui`.
3. Add reusable frontend components for page headers, tables, filters, status badges, empty states, and error states.
4. Ensure the UI works on desktop and reasonable tablet widths.
5. Add smoke tests for the UI route and static asset loading.

**Commit message:**

```text
feat(ui): add Kelvin operational UI shell
```

---

### Step 2: Agent Runs Dashboard

**Goal:** Show agent runs in a scannable dashboard so the user can understand what Kelvin is doing.

**What to do:**

1. Add or reuse an API endpoint for listing recent agent runs with status, created time, updated time, goal summary, and current step count.
2. Build a Runs page with filters for active, awaiting approval, completed, failed, and cancelled runs.
3. Add a run detail view showing goal, status timeline, tool calls, observations, and final result where available.
4. Keep sensitive content masked consistently with the existing `OutputGuard` and audit rules.
5. Add API and UI tests for run listing and detail rendering.

**Commit message:**

```text
feat(ui): add agent runs dashboard
```

---

### Step 3: Local Approval Queue

**Goal:** Make pending write approvals visible and actionable in the UI while preserving local user control.

**What to do:**

1. Add an Approvals page listing runs or tool calls awaiting local approval.
2. Show the proposed action, target path or resource, risk level, and diff/preview where available.
3. Add explicit Approve and Reject actions backed by existing approval policy APIs or new narrowly scoped endpoints.
4. Require confirmation for higher-risk operations.
5. Add tests proving write operations cannot skip the approval queue.

**Commit message:**

```text
feat(ui): add local approval queue
```

---

### Step 4: Audit Log Viewer

**Goal:** Provide a readable audit trail for security decisions, agent runs, n8n calls, and approval actions.

**What to do:**

1. Add an Audit page with filters by event type, severity, run ID, correlation ID, and time range.
2. Display audit entries without exposing raw secrets, credentials, or blocked sensitive prompts.
3. Link audit entries back to related run detail pages when possible.
4. Add pagination or incremental loading for larger audit sets.
5. Add tests for masking and audit filtering.

**Commit message:**

```text
feat(ui): add audit log viewer
```

---

### Step 5: Settings & Safety Controls

**Goal:** Give the user a safe place to inspect and adjust Kelvin's operational settings.

**What to do:**

1. Add a Settings page showing model/runtime status, API base URLs, approval policy state, email notification settings status, and n8n connection settings.
2. Keep secrets write-only or masked; never display raw tokens or passwords.
3. Add validation for editable settings.
4. Add a read-only safety summary for tool policy, API scopes, and online integration boundaries.
5. Add tests for settings validation and secret masking.

**Commit message:**

```text
feat(ui): add settings and safety controls
```

---

### Step 6: n8n Status Panel

**Goal:** Show whether the n8n automation layer is reachable and healthy without making n8n required for local Kelvin use.

**What to do:**

1. Add a lightweight backend health check for configured n8n endpoints or documented workflow health URLs.
2. Build an n8n page/panel showing reachability, last successful check, configured base URL, and known workflow status where available.
3. Make failures non-blocking: local chat, runs, approvals, and audit must still work when n8n is down.
4. Add tests for healthy, degraded, and unreachable n8n states.

**Commit message:**

```text
feat(ui): add n8n status panel
```

---

### Step 7: Email Notification Settings

**Goal:** Configure email notifications without exposing SMTP credentials or provider tokens.

**What to do:**

1. Add settings for notification recipients, enabled notification types, daily summary time, and provider mode.
2. Store email credentials outside Git and keep exported configuration secretless.
3. Add a test email action that sends a minimal non-sensitive test message.
4. Document local SMTP or n8n-based email delivery configuration in `docs/n8n-credential-setup.md` or a dedicated email setup guide.
5. Add tests for validation and secret masking.

**Commit message:**

```text
feat(notifications): add email notification settings
```

---

### Step 8: Approval Pending Email Notifications

**Goal:** Notify the user when Kelvin needs local approval for a pending write or high-risk operation.

**What to do:**

1. Emit an email notification when a run enters `awaiting_approval`.
2. Include run ID, goal summary, risk level, requested action summary, and a link or instruction to review it in the local UI.
3. Do not include raw diffs or sensitive file content in the email body.
4. Deduplicate repeated approval reminders for the same pending action.
5. Add tests for notification triggering and content redaction.

**Commit message:**

```text
feat(notifications): email pending approvals
```

---

### Step 9: Run Completed/Failed Email Notifications

**Goal:** Notify the user when important agent runs complete or fail.

**What to do:**

1. Emit completion emails for selected run types or user-configured notification rules.
2. Emit failure emails with run ID, failure category, safe summary, and next-step guidance.
3. Keep sensitive prompts, credentials, and raw tool output out of email bodies.
4. Add tests for completed, failed, cancelled, and notification-disabled cases.

**Commit message:**

```text
feat(notifications): email run completion and failure events
```

---

### Step 10: Daily Summary Email

**Goal:** Send a daily operational summary so the user can track Kelvin activity without opening the UI.

**What to do:**

1. Generate a daily summary containing run counts, failed runs, pending approvals, notable audit events, and n8n health status.
2. Make the summary time and recipients configurable.
3. Ensure the summary contains only safe, redacted content.
4. Add a manual "send summary now" action for testing.
5. Add tests for summary generation, empty-day summaries, and redaction.

**Commit message:**

```text
feat(notifications): add daily summary email
```

---

### Step 11: UI & Email End-to-End Verification

**Goal:** Verify that the UI and email notification layer work together without weakening Kelvin's safety model.

**What to do:**

1. Run full backend and frontend quality checks.
2. Verify the UI can show active runs, completed runs, failed runs, pending approvals, audit logs, settings, and n8n health.
3. Verify approval pending, run completed, run failed, and daily summary emails with secretless test credentials.
4. Verify n8n outage does not block local UI, chat, agent runs, approval review, or audit viewing.
5. Update `docs/roadmap.md` and mark v0.9 as complete.

**Commit message:**

```text
test(integration): verify Kelvin UI and email notifications
```

---

## v0.9 Acceptance Criteria Mapping

| Acceptance Criterion | Step |
|---|---|
| Kelvin has a usable operational UI as the primary control surface | #1 |
| Agent runs are visible with status, timeline, and details | #2 |
| Pending approvals are visible and can be approved or rejected locally | #3 |
| Audit entries are searchable, readable, linked to runs, and safely redacted | #4 |
| Runtime, safety, email, and n8n settings are inspectable without leaking secrets | #5, #7 |
| n8n health is visible but n8n outages do not block local Kelvin use | #6, #11 |
| Approval pending emails are sent without sensitive diffs or secrets | #8 |
| Run completed and failed emails are sent with safe summaries | #9 |
| Daily summary emails report runs, pending approvals, audit highlights, and n8n status | #10 |
| Existing local approval and audit guarantees remain enforced end to end | #3, #4, #11 |
