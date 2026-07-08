# Backup and Restore Guide

This guide documents the procedures for backing up, restoring, and verifying
both the Kelvin VM (`kelvin-ai`) and the automation VM (`kelvin-automation`).
For v1.0, a restore is not complete until Kelvin health, readiness, UI, audit,
and n8n checks pass.

---

## 1. Kelvin Assistant VM (`kelvin-ai`)

The Kelvin Assistant database contains knowledge records, memory stores, agent
runs, approvals, and audit logs. Treat the SQL dump as sensitive operational
data even though it must not contain raw API tokens or n8n credential secrets.

### Database Backup

To back up the PostgreSQL database on the Kelvin VM:

1. Run the backup helper script from the repository root:

   ```bash
   ./scripts/backup-kelvin-db.sh
   ```

   This will output a timestamped SQL dump in `./data/backups/kelvin_backup_YYYYMMDD_HHMMSS.sql`.

2. Alternatively, run the dump manually:

   ```bash
   pg_dump "postgresql://<user>:<password>@localhost:5432/kelvin_assistant" > kelvin_backup.sql
   ```

3. Record the backup file path, size, timestamp, and target database in the
   restore log:

   ```bash
   ls -lh ./data/backups/kelvin_backup_YYYYMMDD_HHMMSS.sql
   ```

4. Store the dump somewhere separate from the VM disk. Do not store raw API
   tokens, `.env` files, or n8n encryption keys inside the same unprotected
   archive.

### Database Restore

To restore the database from a SQL dump:

1. Stop the Kelvin API before replacing the database:

   ```bash
   sudo systemctl stop kelvin-api
   ```

2. Re-create the empty database if it was dropped:

   ```bash
   dropdb kelvin_assistant
   createdb kelvin_assistant
   ```

3. Restore the SQL dump:

   ```bash
   psql "postgresql://<user>:<password>@localhost:5432/kelvin_assistant" < kelvin_backup.sql
   ```

4. Re-apply any repository SQL migrations that are newer than the dump:

   ```bash
   psql "$KELVIN_DATABASE_URL" --file=infrastructure/sql/001_create_knowledge_schema.sql
   psql "$KELVIN_DATABASE_URL" --file=infrastructure/sql/002_create_memory_schema.sql
   psql "$KELVIN_DATABASE_URL" --file=infrastructure/sql/003_create_agent_audit_schema.sql
   psql "$KELVIN_DATABASE_URL" --file=infrastructure/sql/004_create_security_audit_schema.sql
   ```

5. Start Kelvin again:

   ```bash
   sudo systemctl start kelvin-api
   ```

### Kelvin Post-Restore Verification

Run these checks from a trusted host after restoring the Kelvin database:

```powershell
Invoke-RestMethod http://<VM_IP>:8000/health
Invoke-RestMethod http://<VM_IP>:8000/status
Invoke-RestMethod http://<VM_IP>:8000/ready
Invoke-RestMethod http://<VM_IP>:8000/ready/database
Invoke-RestMethod http://<VM_IP>:8000/version
```

Expected results:

- `/health` returns `status: ok`.
- `/status` returns `ready` when required services are configured and available.
  `degraded` is acceptable only when optional components, such as n8n, are not
  configured.
- `/ready` returns HTTP 200 only when the configured LLM provider and model are
  available.
- `/ready/database` returns HTTP 200 and `provider: postgresql`.
- `/version` matches the deployed release.

Then open `http://<VM_IP>:8000/ui` and verify:

- Runs page loads and recent restored agent runs are visible.
- Approvals page loads without server errors.
- Audit page can search or list restored audit entries.
- Settings page masks configured secrets.
- n8n page shows configured or unconfigured status without blocking local Kelvin
  UI use.

Optional SQL spot checks:

```bash
psql "$KELVIN_DATABASE_URL" -c "select count(*) from knowledge_documents;"
psql "$KELVIN_DATABASE_URL" -c "select count(*) from memory_items;"
psql "$KELVIN_DATABASE_URL" -c "select count(*) from agent_runs;"
psql "$KELVIN_DATABASE_URL" -c "select count(*) from agent_tool_proposals;"
psql "$KELVIN_DATABASE_URL" -c "select count(*) from agent_tool_results;"
psql "$KELVIN_DATABASE_URL" -c "select count(*) from security_audit_logs;"
```

If a table is intentionally empty in the source environment, record that fact in
the restore log before accepting the restore.

---

## 2. Automation VM (`kelvin-automation`)

The automation VM runs n8n and its PostgreSQL database under Docker Compose.

### n8n Encryption Key (CRITICAL)

Before backing up data, you **must** back up your `N8N_ENCRYPTION_KEY`.

- **Where it is:** Located in your `.env` file on the automation VM.
- **Why it is critical:** If you lose this key, you will not be able to decrypt
  stored credentials after a restore, forcing you to re-create all credentials
  manually.
- **Action:** Save this key in a secure password manager or offline vault
  separate from your data backups.

Do not commit the key, include it in workflow JSON exports, or paste it into
LLM prompts. Restore it before starting n8n against restored database data.

### n8n PostgreSQL Backup

The database contains workflows, execution histories, and credential mappings.
To take a database dump from the running container:

```bash
docker compose exec -t db pg_dump -U postgres n8n > n8n_backup.sql
```

### n8n PostgreSQL Restore

To restore the database from a dump:

1. Re-create the empty database inside the container:

   ```bash
   docker compose exec -t db dropdb -U postgres n8n
   docker compose exec -t db createdb -U postgres n8n
   ```

2. Restore the SQL dump:

   ```bash
   docker compose exec -T db psql -U postgres n8n < n8n_backup.sql
   ```

### n8n Volume (File Storage) Backup

The `n8n_data` volume contains local files, executions cache, and custom nodes.
To back up the files:

```bash
# Create a tarball of the volume directory
tar -czvf n8n_data_backup.tar.gz /var/lib/docker/volumes/n8n_n8n_data/_data
```

### n8n Post-Restore Verification

After restoring the n8n database, volume, and `N8N_ENCRYPTION_KEY`:

1. Start the Compose stack:

   ```bash
   docker compose up -d
   ```

2. Verify containers are healthy:

   ```bash
   docker compose ps
   docker compose logs --tail=100 n8n
   ```

3. Log into n8n and verify:

   - Workflows are present.
   - Credentials are green and do not show decryption errors.
   - Kelvin credential sends `Authorization: Bearer <raw-token>` but exported
     workflows still contain no raw token.
   - Health check workflow runs successfully.

4. In Kelvin, call the n8n health endpoint or open `/ui/n8n` and confirm the
   automation layer is reported as configured or reachable.

---

## 3. Hyper-V Checkpoint Policy

Hyper-V checkpoints are useful for quick rollbacks during upgrades, but they are
**not** a replacement for database backups.

### Golden Rules

1. **Short-lived only:** Use checkpoints only before performing high-risk
   operations, such as updating the OS, upgrading Docker, or changing Compose
   stack versions.
2. **Delete immediately:** Delete the checkpoints as soon as you verify the
   system works, within 24-48 hours.
3. **No database archives:** Keeping checkpoints long-term degrades VM disk
   performance due to difference disks (`.avhdx`) and consumes massive host
   storage.

### How to cleanup checkpoints

In the Hyper-V Manager:

1. Select the VM.
2. Under the **Checkpoints** list, right-click the checkpoint.
3. Select **Delete Checkpoint Subtree**.

---

## 4. Data Retention Expectations

Use retention settings that match the local risk profile and available storage.
The defaults below are v1.0 operating expectations, not hard-coded product
limits.

| Data | Suggested retention | Notes |
|---|---:|---|
| Kelvin SQL dumps | 30-90 days | Keep at least one known-good offline copy. Encrypt archives outside the VM. |
| n8n SQL dumps and volume archives | 30-90 days | Must be paired with the matching `N8N_ENCRYPTION_KEY`. |
| Kelvin audit records | 180-365 days | Prefer pruning only after exporting compliance evidence. |
| Agent run history and approvals | 90-180 days | Keep longer when runs document operational decisions. |
| Application logs | 14-30 days | Rotate with systemd/journald or the host log policy. |
| Generated artifacts and downloads | 7-30 days | Remove temporary outputs that are no longer needed. |
| Local temp files and `.pytest_temp` | 1-7 days | Never use temp folders as backup storage. |
| Hyper-V checkpoints | 24-48 hours | Delete after restore or upgrade acceptance. |

Before deleting any audit or run history, confirm that backup archives covering
the deletion window exist and are restorable. Retention cleanup must not remove
API token definitions, `.env` files, or n8n encryption keys unless they have
already been replaced and separately vaulted.

---

## 5. Full Restore Verification Procedure

To verify a full system restore:

1. Restore the VMs from the appliance export if completely lost.
2. Restore the `.env` files containing `N8N_ENCRYPTION_KEY` and connection
   strings.
3. Restore the PostgreSQL dumps using the restore commands above.
4. Start the Docker Compose stack on the automation VM.
5. Start `kelvin-api` on the Kelvin VM.
6. Run the Kelvin post-restore verification checklist.
7. Run the n8n post-restore verification checklist.
8. Record the backup file paths, restore target, endpoint results, UI checks,
   and any accepted degraded modes.

### Restore Acceptance Criteria

Accept the restore only when all applicable criteria are true:

- Kelvin `/health`, `/status`, `/ready`, `/ready/database`, and `/version`
  results match the expected deployment state.
- The UI loads Runs, Approvals, Audit, Settings, and n8n pages without server
  errors.
- Restored knowledge, memory, agent run, approval, and audit data are visible or
  verified by SQL spot checks.
- n8n workflows and credentials decrypt successfully with the restored
  `N8N_ENCRYPTION_KEY`.
- Exported workflow files and restore logs contain no raw API tokens, n8n
  encryption key, SMTP password, or external AI provider key.
- Retention cleanup, if performed, is documented with the date range and backup
  archive that protects the deleted records.

If any required check fails, keep the restored environment isolated, preserve
the failed restore logs, and retry from the last known-good backup instead of
promoting the environment.
