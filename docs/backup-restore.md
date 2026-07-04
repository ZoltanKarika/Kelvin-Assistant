# Backup and Restore Guide

This guide documents the procedures for backing up and restoring both the Kelvin VM (`kelvin-ai`) and the automation VM (`kelvin-automation`).

---

## 1. Kelvin Assistant VM (`kelvin-ai`)

The Kelvin Assistant database contains the agent runs, memory stores, and audit logs.

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

### Database Restore
To restore the database from a SQL dump:
1. Re-create the empty database if it was dropped:
   ```bash
   dropdb kelvin_assistant
   createdb kelvin_assistant
   ```
2. Restore the SQL dump:
   ```bash
   psql "postgresql://<user>:<password>@localhost:5432/kelvin_assistant" < kelvin_backup.sql
   ```

---

## 2. Automation VM (`kelvin-automation`)

The automation VM runs n8n and its PostgreSQL database under Docker Compose.

### n8n Encryption Key (CRITICAL)
Before backing up data, you **must** back up your `N8N_ENCRYPTION_KEY`.
* **Where it is:** Located in your `.env` file on the automation VM.
* **Why it is critical:** If you lose this key, you will not be able to decrypt your stored credentials (like API keys) in n8n after a restore, forcing you to re-create all credentials manually.
* **Action:** Save this key in a secure password manager or offline vault separate from your data backups.

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

---

## 3. Hyper-V Checkpoint Policy

Hyper-V checkpoints are useful for quick rollbacks during upgrades, but they are **not** a replacement for database backups.

### Golden Rules
1. **Short-lived only:** Use checkpoints only before performing high-risk operations (e.g. updating OS, upgrading Docker version, or changing Compose stack versions).
2. **Delete immediately:** Delete the checkpoints as soon as you verify the system works (within 24–48 hours).
3. **No database archives:** Keeping checkpoints long-term degrades VM disk performance (due to difference disks `.avhdx`) and consumes massive host storage.

### How to cleanup checkpoints
In the Hyper-V Manager:
1. Select the VM.
2. Under the **Checkpoints** list, right-click the checkpoint.
3. Select **Delete Checkpoint Subtree**.

---

## 4. Full Restore Verification Procedure

To verify a full system restore:
1. Restore the VMs from the appliance export (if completely lost).
2. Restore the `.env` files containing `N8N_ENCRYPTION_KEY` and connection strings.
3. Restore the PostgreSQL dumps using the restore commands above.
4. Start the Docker Compose stack on the automation VM.
5. Log into n8n and verify that:
   - Workflows are present.
   - Credentials are green (not showing decryption errors).
   - Health check workflow runs successfully.
