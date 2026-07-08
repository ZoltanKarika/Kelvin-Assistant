# v1.0 Stable - Implementation Guide

This document plans the v1.0 milestone. v1.0 should turn the completed local
Kelvin capabilities into a stable, documented offline AI platform that can be
installed, operated, verified, backed up, restored, and safely maintained.

Related documents:

- [Roadmap](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/roadmap.md) - milestone definitions and acceptance criteria.
- [Installation guide](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/installation.md) - current install and service setup notes.
- [Backup and restore](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/backup-restore.md) - data protection procedures.
- [v0.8 AI Security & Integration Hardening](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/ai/v08-guide.md) - security gates and audit foundations.
- [v0.9 Kelvin UI & Email Notifications](file:///c:/Users/Zoltan/Documents/Kelvin%20Assistant/docs/ai/v09-guide.md) - operational UI and email layer.

---

## Current Progress

v1.0 is planned. The table below defines small, reviewable PRs.

### Steps Table

| Step | Item | Depends on | Branch suggestion | Status |
|---|---|---|---|---|
| **1** | Release Readiness Gap Audit | - | `feat/v1.0-readiness-audit` | done |
| **2** | Installation & Upgrade Runbook | #1 | `feat/v1.0-install-runbook` | pending |
| **3** | Runtime & Service Hardening | #1, #2 | `feat/v1.0-runtime-hardening` | pending |
| **4** | Backup, Restore & Data Retention Verification | #1, #2 | `feat/v1.0-backup-restore` | pending |
| **5** | Security & Permission Baseline Verification | #1 | `feat/v1.0-security-baseline` | pending |
| **6** | Operational UI, Email & n8n Runbooks | #1, #3, #5 | `feat/v1.0-ops-runbooks` | pending |
| **7** | API, Client & Configuration Contract Freeze | #1, #3, #5 | `feat/v1.0-contract-freeze` | pending |
| **8** | Offline Release, Licensing & Version Package | #2, #4, #7 | `feat/v1.0-release-package` | pending |
| **9** | End-to-End Stable Release Verification | #1-#8 | `feat/v1.0-stable-verification` | pending |

---

## Scope

In scope:

- stable installation and upgrade documentation for the local Kelvin deployment;
- clear service, health, readiness, logging, and degraded-mode behavior;
- repeatable backup, restore, and data retention checks;
- verified security defaults for tokens, approvals, secrets, audit, and email;
- operational runbooks for UI, agent runs, approvals, audit, settings, n8n, and notifications;
- frozen v1 API/client/configuration contracts with documented compatibility rules;
- release notes, license inventory, and offline-friendly release verification.

Out of scope for v1.0:

- new chat platforms or broad two-way messaging product work;
- multi-user SaaS hosting;
- cloud-only features that weaken offline operation;
- major UI redesigns unrelated to stable operation.

---

## Step-by-Step Instructions

Each step should be one PR unless the implementation discovers a smaller split.

---

### Step 1: Release Readiness Gap Audit

**Goal:** Produce a factual inventory of what is already stable and what still
blocks v1.0.

**Result:** Completed in
[`docs/ai/v10-readiness-audit.md`](v10-readiness-audit.md).

**What to do:**

1. Review README, installation, architecture, roadmap, backup, n8n, token, UI,
   email, and security documentation.
2. Compare docs against the current code, tests, configuration examples, service
   files, and workflows.
3. Create a concise v1.0 gap checklist with owners, dependencies, and proposed
   verification commands.
4. Identify obsolete or contradictory docs.
5. Avoid changing runtime behavior in this PR.

**Commit message:**

```text
docs: audit v1.0 release readiness gaps
```

---

### Step 2: Installation & Upgrade Runbook

**Goal:** Make local installation, upgrade, and rollback steps repeatable.

**What to do:**

1. Update install docs for Windows host, Ubuntu VM, Python environment, service
   startup, database setup, Ollama, and optional n8n.
2. Add an upgrade path from the latest v0.9 state to v1.0.
3. Document rollback and recovery expectations for failed upgrades.
4. Ensure examples use secretless placeholders and point to `.env.example`.
5. Add or update smoke-test commands for a fresh local install.

**Commit message:**

```text
docs: add v1.0 install and upgrade runbook
```

---

### Step 3: Runtime & Service Hardening

**Goal:** Ensure Kelvin starts predictably and reports dependency health clearly.

**What to do:**

1. Verify startup behavior for FastAPI, Ollama, PostgreSQL, and optional n8n.
2. Confirm `/health`, `/ready`, and `/version` responses distinguish healthy,
   degraded, and unavailable dependencies.
3. Review service files and logging defaults for restart behavior and useful
   operator diagnostics.
4. Add tests for missing optional dependencies and required dependency failures.
5. Document the expected local degraded modes.

**Commit message:**

```text
feat(runtime): harden v1.0 service readiness
```

---

### Step 4: Backup, Restore & Data Retention Verification

**Goal:** Prove Kelvin data can be protected and restored without leaking secrets.

**What to do:**

1. Verify documented PostgreSQL, knowledge, memory, audit, agent run, and n8n
   backup steps.
2. Add a restore verification checklist with expected health/readiness results.
3. Document retention expectations for logs, audit records, generated artifacts,
   and local temp files.
4. Ensure secret material and n8n encryption keys are handled separately.
5. Add automated or scripted checks where practical.

**Commit message:**

```text
docs: verify v1.0 backup and restore process
```

---

### Step 5: Security & Permission Baseline Verification

**Goal:** Reconfirm that v1.0 preserves Kelvin's local safety model.

**What to do:**

1. Verify scoped API tokens, approval gates, write-tool policy, output masking,
   input/context guards, and audit logging.
2. Confirm email and UI surfaces never expose raw secrets or sensitive diffs.
3. Test approval bypass attempts and blocked high-risk operations.
4. Document the default secure configuration and known limits.
5. Add regression tests for any missing safety coverage.

**Commit message:**

```text
test(security): verify v1.0 permission baseline
```

---

### Step 6: Operational UI, Email & n8n Runbooks

**Goal:** Give the operator a clear checklist for daily local operation.

**What to do:**

1. Document how to inspect runs, pending approvals, audit entries, settings, and
   n8n status in the UI.
2. Document test email, pending approval email, run result email, and daily
   summary verification.
3. Verify n8n outage behavior remains non-blocking for local Kelvin features.
4. Add UI/email/n8n troubleshooting guidance.
5. Keep credentials masked in all examples.

**Commit message:**

```text
docs: add v1.0 operational runbooks
```

---

### Step 7: API, Client & Configuration Contract Freeze

**Goal:** Define what is stable for v1.0 consumers.

**What to do:**

1. Review versioned API routes, request/response schemas, client docs, and token
   scopes.
2. Mark stable contracts and document compatibility expectations.
3. List intentionally unstable or internal surfaces.
4. Verify `.env.example`, API token examples, and n8n workflow examples match
   the stable contract.
5. Add schema or route regression tests where needed.

**Commit message:**

```text
docs(api): freeze v1.0 API and configuration contracts
```

---

### Step 8: Offline Release, Licensing & Version Package

**Goal:** Prepare a release package that can be reviewed without internet access.

**What to do:**

1. Update release notes and version references.
2. Verify `LICENSE`, `NOTICE`, and third-party notices are current.
3. Confirm dependency pins and lockfiles are suitable for a reproducible local
   install.
4. Document offline verification steps and required local model assets.
5. Capture known limitations and post-1.0 follow-up candidates.

**Commit message:**

```text
docs: prepare v1.0 release package
```

---

### Step 9: End-to-End Stable Release Verification

**Goal:** Mark v1.0 complete only after the platform is verified end to end.

**What to do:**

1. Run the full backend, frontend/static, typing, formatting, and test suite.
2. Verify install/upgrade, service startup, health/readiness, UI operation,
   approvals, audit, email notifications, n8n outage behavior, backup, and
   restore.
3. Update `docs/roadmap.md` and this guide to mark v1.0 complete.
4. Record final verification commands and results.
5. Prepare the final v1.0 PR summary.

**Commit message:**

```text
test(integration): verify v1.0 stable release
```

---

## v1.0 Acceptance Criteria Mapping

| Acceptance Criterion | Step |
|---|---|
| Current docs and implementation gaps are known and tracked | #1 |
| Installation, upgrade, rollback, and smoke tests are documented | #2 |
| Services start reliably and report health/readiness clearly | #3 |
| Backup, restore, and retention processes are verified | #4 |
| Security defaults, approvals, masking, and audit guarantees hold | #5 |
| UI, email, and n8n operations have usable local runbooks | #6 |
| API, client, token, and configuration contracts are stable | #7 |
| Release notes, license inventory, and offline verification are ready | #8 |
| Full regression and operational verification pass before completion | #9 |
