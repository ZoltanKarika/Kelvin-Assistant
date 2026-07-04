#!/usr/bin/env bash
# backup-kelvin-db.sh - Safely backup the Kelvin PostgreSQL database

set -eo pipefail

# Load environment variables if .env exists
if [ -f "../.env" ]; then
  export $(grep -v '^#' ../.env | xargs)
elif [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

DB_URL=${KELVIN_DATABASE_URL:-$DATABASE_URL}

if [ -z "$DB_URL" ]; then
  echo "Error: KELVIN_DATABASE_URL is not set" >&2
  exit 1
fi

BACKUP_DIR="./data/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/kelvin_backup_$TIMESTAMP.sql"

echo "Backing up Kelvin database..."
pg_dump "$DB_URL" > "$BACKUP_FILE"

echo "Backup complete: $BACKUP_FILE"
