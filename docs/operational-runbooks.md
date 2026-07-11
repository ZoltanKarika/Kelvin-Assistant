# v1.0 Operational Runbooks

This document gives the local Kelvin operator repeatable daily checks for the
UI, email notifications, n8n status, approvals, audit, and troubleshooting.

Use these runbooks after install, after upgrade, after restore, and during
normal operation.

---

## 1. Daily Operator Check

Start from the Kelvin operational UI:

```text
http://<VM_IP>:8000/ui
```

For local development:

```text
http://127.0.0.1:8000/ui
```

Daily checklist:

1. Confirm `kelvin-api` is running.
2. Check `/status` for the aggregate runtime state.
3. Open the UI and, when production auth is enabled, use the header API token
   button to enter an operator token for this browser session.
4. Verify Runs, Approvals, Audit, Settings, and n8n pages load.
5. Review failed or stuck agent runs.
6. Resolve or reject pending approvals.
7. Check recent blocked audit entries.
8. Verify email notification settings and send a test email after config changes.
9. Check n8n status if delegated notifications or workflows are enabled.

PowerShell endpoint check:

```powershell
Invoke-RestMethod http://<VM_IP>:8000/health
Invoke-RestMethod http://<VM_IP>:8000/status
Invoke-RestMethod http://<VM_IP>:8000/ready
Invoke-RestMethod http://<VM_IP>:8000/ready/database
Invoke-RestMethod http://<VM_IP>:8000/version
```

Expected result:

- `/health` is `ok`.
- `/status` is `ready`, or `degraded` only for an understood optional component.
- `/ready` is HTTP 200 when Ollama and the configured model are available.
- `/ready/database` is HTTP 200 when PostgreSQL is configured for persistence.

---

## 2. Runs Page

UI page:

```text
/ui/runs
```

Use this page to inspect agent run state and execution history.

What to check:

- `received`, `planning`, `executing`, and `observing` runs should continue to a
  terminal state.
- `awaiting_approval` runs should have a matching item on `/ui/approvals`.
- `failed` runs should have enough detail to decide whether to retry, fix
  configuration, or inspect audit logs.
- `completed` runs should show the tool timeline and results.

Operator actions:

- Use filters to focus on active, failed, or completed runs.
- Open a run and inspect the timeline before rerunning related work.
- Use **Cancel** only for active runs that are stuck, obsolete, or unsafe to
  continue.
- Follow run links from `/ui/audit` when investigating blocked guard events.

Escalate when:

- Multiple runs fail with the same model or database error.
- A run remains active after the backend has restarted.
- A completed run has unexpected write-tool output.

---

## 3. Approvals Page

UI page:

```text
/ui/approvals
```

Use this page for local human review of write, destructive, or privileged tool
proposals. n8n must not receive `agent:approve`; approval is a Kelvin operator
responsibility.

Before approving:

1. Verify the run goal still matches the current operator intent.
2. Read the tool name, risk, reason, expected effect, and policy reason.
3. Inspect the proposed arguments.
4. For destructive or privileged work, confirm the high-risk checkbox only after
   reading the details.
5. Reject anything that targets an unexpected workspace, path, host, or action.

After approval:

- Return to `/ui/runs` and confirm the run moves out of `awaiting_approval`.
- Review tool output when execution completes.
- Check `/ui/audit` if the run later fails due to a guard decision.

After rejection:

- Confirm the run becomes cancelled.
- Record the reason externally if the rejection is part of an operational
  incident.

---

## 4. Audit Page

UI page:

```text
/ui/audit
```

Use this page to review input and output guard decisions. Audit entries should
show masked content only.

Filters:

- `event_type`: use `input_guard` or `output_guard` to narrow guard type.
- `decision`: use blocked entries to investigate denied or unsafe behavior.
- `run_id`: use when investigating a specific agent run.
- `correlation_id`: use when tracing a request across systems.

Daily review:

1. Filter to blocked decisions.
2. Check whether the blocked request came from a user, n8n, RAG, memory, or an
   agent run.
3. Confirm masked content does not expose raw tokens, private keys, database
   passwords, SMTP passwords, or external AI keys.
4. Link back to the run when `run_id` is present.

Escalate when:

- Raw secrets appear in audit content.
- Many blocks appear from the same n8n workflow or client token.
- A blocked event corresponds to an unexpected write-tool attempt.

---

## 5. Settings Page

UI page:

```text
/ui/settings
```

Use this page to inspect runtime, safety, email, and n8n configuration. Secret
fields should show presence only; they should not display raw configured values.

Safe settings checks:

- Ollama base URL and model match the intended runtime.
- n8n URL is set only when the automation layer is intentionally enabled.
- n8n token and SMTP password fields show configured placeholders, not raw
  values.
- Email notifications are enabled only when recipient and provider settings are
  verified.
- Allowed scopes and workspace IDs match the intended local policy.

After changing settings:

1. Save changes.
2. Reopen the page and confirm secret fields still show placeholders.
3. Run `/status` and `/ready`.
4. If email changed, send a test email.
5. If n8n changed, open `/ui/n8n` and refresh health.

Production reminder:

- `KELVIN_API_AUTH_MODE=required` and a hashed token file are mandatory for LAN
  or production access.
- The UI stores the operator API token only in browser session storage. Close the
  browser tab or clear the token from the header control after shared-machine
  use.
- Keep real `.env`, token files, SMTP passwords, and n8n tokens outside Git.

### UI API Token Steps After Rotation

Use this after rotating an operator token in
`/etc/kelvin-assistant/api-tokens.json`:

1. Restart `kelvin-api` after saving the new `token_sha256`.
2. Open `http://<VM_IP>:8000/ui` in Chrome.
3. Click **API token** in the header.
4. Paste the new raw token only, without `RAW_TOKEN=` and without quotes.
5. Press OK.
6. Confirm the header button changes to **API token: set**.
7. Open Runs, Approvals, Audit, Settings, and n8n.
8. Confirm each protected page loads data instead of the missing-token error.
9. Remove the old token digest from the VM token file after all clients work.

Use the raw token only in clients. Store only the SHA-256 digest in the VM token
file. If the raw token is pasted into chat or any shared place, rotate it again.

---

## 6. Email Notification Runbook

Kelvin supports two provider modes:

- `smtp`: Kelvin sends email directly through SMTP.
- `n8n`: Kelvin sends a notification payload to an n8n webhook, and n8n handles
  delivery.

Notification types:

- approval required;
- run completed;
- run failed;
- daily summary.

### Test Email

Use `/ui/settings`:

1. Enable email notifications.
2. Set provider mode.
3. Configure recipient.
4. Save settings.
5. Click **Test email**.
6. Confirm delivery in the mailbox, Mailpit, or n8n execution history.

Expected:

- The test email contains no run details, diffs, tokens, or passwords.
- The UI shows a success toast.

### Pending Approval Email

To verify approval notifications:

1. Enable approval-required notifications.
2. Start or wait for a run that proposes a write, destructive, or privileged
   tool.
3. Confirm the run appears on `/ui/approvals`.
4. Confirm one approval notification is sent for the pending tool call.
5. Confirm the email links the operator back to the local UI.

Expected:

- The notification includes run ID, goal, risk, tool name, and reason.
- The notification does not include raw tool arguments or diffs.
- Duplicate notifications are not sent repeatedly for the same tool call.

### Run Result Email

To verify completed or failed run notifications:

1. Enable completed and failed run notifications.
2. Complete one safe run and intentionally inspect one failed run scenario.
3. Confirm the notification links to `/ui/runs`.
4. Confirm known secret patterns are masked in the body.

Expected:

- Completion messages summarize the run without raw model responses.
- Failure messages summarize the category without raw logs.
- Tokens, private keys, database URLs, and credential URLs are masked.

### Daily Summary

Use `/ui/settings`:

1. Enable daily summary notifications.
2. Set `HH:MM` summary time.
3. Save settings.
4. Click **Send daily summary** for a manual verification.

Expected:

- The summary includes counts for runs, failed runs, pending approvals, blocked
  audit events, and n8n status.
- The summary omits raw prompts, model responses, tool diffs, and secrets.

---

## 7. n8n Runbook

UI page:

```text
/ui/n8n
```

Use this page to check the optional automation layer.

Health states:

- `healthy`: Kelvin can reach n8n.
- `degraded`: n8n responded with a server-side problem.
- `unreachable`: Kelvin cannot connect.
- `unconfigured`: n8n is not configured, which is acceptable when automation is
  not in use.

Operator checks:

1. Open `/ui/n8n`.
2. Confirm base URL is expected.
3. Click refresh after changing n8n settings.
4. If delegated email is enabled, verify the notification webhook workflow is
   active in n8n.
5. On the automation VM, verify containers:

   ```bash
   sudo docker compose ps
   curl --fail http://127.0.0.1:5678/healthz
   ```

6. Verify the editor remains reachable only through the intended local tunnel:

   ```bash
   sudo ss -ltnp | grep 5678
   ```

Expected:

- `127.0.0.1:5678` is acceptable on the automation VM.
- `0.0.0.0:5678` or a LAN IP bound directly to `5678` is a security issue.
- Kelvin remains usable when n8n is down.

---

## 8. n8n Outage Procedure

When `/ui/n8n` shows unreachable or degraded:

1. Confirm whether n8n is required for the current workflow.
2. Check Kelvin local features first:

   ```powershell
   Invoke-RestMethod http://<VM_IP>:8000/health
   Invoke-RestMethod http://<VM_IP>:8000/status
   Invoke-RestMethod http://<VM_IP>:8000/ready
   Invoke-RestMethod http://<VM_IP>:8000/ready/database
   ```

3. Verify local UI pages still load:

   - `/ui/runs`
   - `/ui/approvals`
   - `/ui/audit`
   - `/ui/settings`

4. On the automation VM, inspect:

   ```bash
   cd /opt/kelvin-automation
   sudo docker compose ps
   sudo docker compose logs --tail=100 n8n
   sudo docker compose logs --tail=100 db
   ```

5. If delegated email is enabled and n8n is down, temporarily switch email
   provider mode to `smtp` or accept notification delay.
6. Do not grant broader Kelvin scopes to n8n as a workaround.
7. Do not expose the n8n editor publicly to restore access.

Acceptable degraded mode:

- Kelvin chat, runs, approvals, audit, settings, health, readiness, and local
  SMTP notifications continue to work.
- n8n-specific workflow execution and delegated notification delivery may be
  unavailable until the automation VM is healthy.

---

## 9. Troubleshooting Matrix

| Symptom | First check | Likely cause | Action |
|---|---|---|---|
| `/ui/runs` cannot load runs | `/health`, browser console, API auth | API down or token/auth issue | Check `kelvin-api` status and auth config. |
| Runs stay `awaiting_approval` | `/ui/approvals` | Pending human decision | Approve or reject after inspecting arguments. |
| Approval email not received | `/ui/settings`, SMTP or n8n logs | Notification disabled, bad recipient, provider down | Send test email and inspect provider logs. |
| Daily summary missing | Summary toggle and time | Disabled toggle or provider failure | Click **Send daily summary** manually. |
| `/ui/audit` empty | Audit filters | Filters too narrow or no guard events | Reset filters and load more. |
| Raw secret appears in UI/email/audit | Security baseline | Masking regression or unsafe content path | Stop sharing the output and open a security bug. |
| `/ui/n8n` unreachable | Automation VM compose status | n8n down, tunnel missing, URL wrong | Check Compose, tunnel, and Settings n8n URL. |
| n8n works but Kelvin calls fail | Token scopes | Missing Kelvin scope or revoked token | Verify hashed token file and n8n credential. |
| `/ready` fails but `/health` works | Ollama runtime | Model unavailable or host firewall | Check Ollama, model name, and Windows firewall. |
| `/ready/database` fails | PostgreSQL | DB down or bad `KELVIN_DATABASE_URL` | Check PostgreSQL service and connection string. |

---

## 10. Evidence to Record for v1.0 Verification

For final v1.0 verification, record:

- Date, operator, branch or release version.
- `/health`, `/status`, `/ready`, `/ready/database`, and `/version` outputs.
- UI pages checked: Runs, Approvals, Audit, Settings, n8n.
- Email provider mode tested.
- Test email result.
- Approval notification result.
- Run completed or failed notification result.
- Daily summary result.
- n8n health state and Compose status when configured.
- Any accepted degraded mode and why it is acceptable.

Do not paste raw tokens, SMTP passwords, n8n encryption keys, private keys, or
full `.env` files into verification notes.
