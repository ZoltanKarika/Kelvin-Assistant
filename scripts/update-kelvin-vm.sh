#!/usr/bin/env bash
# update-kelvin-vm.sh - Update the Kelvin systemd deployment on the VM.

set -euo pipefail

APP_DIR="/opt/kelvin-assistant"
APP_USER="kelvin"
BRANCH="main"
SERVICE_NAME="kelvin-api"
SKIP_UV_SYNC=0
SKIP_DB_SCHEMA=0

usage() {
  cat <<'EOF'
Usage: scripts/update-kelvin-vm.sh [options]

Update the Kelvin VM deployment in /opt/kelvin-assistant:
  1. fetch origin
  2. switch to main
  3. fast-forward pull
  4. sync locked production dependencies
  5. apply idempotent database schemas when KELVIN_DATABASE_URL is configured
  6. restart kelvin-api
  7. print service status

Options:
  --app-dir PATH       Repository path on the VM. Default: /opt/kelvin-assistant
  --app-user USER      Service/repository owner. Default: kelvin
  --branch BRANCH      Branch to deploy. Default: main
  --service NAME       systemd service to restart. Default: kelvin-api
  --skip-uv-sync       Skip uv sync, useful for static-only hotfixes.
  --skip-db-schema     Skip database schema application.
  -h, --help           Show this help.

Run on the Kelvin VM, for example:
  cd /opt/kelvin-assistant
  sudo ./scripts/update-kelvin-vm.sh
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --app-dir)
      APP_DIR="${2:?Missing value for --app-dir}"
      shift 2
      ;;
    --app-user)
      APP_USER="${2:?Missing value for --app-user}"
      shift 2
      ;;
    --branch)
      BRANCH="${2:?Missing value for --branch}"
      shift 2
      ;;
    --service)
      SERVICE_NAME="${2:?Missing value for --service}"
      shift 2
      ;;
    --skip-uv-sync)
      SKIP_UV_SYNC=1
      shift
      ;;
    --skip-db-schema)
      SKIP_DB_SCHEMA=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

log() {
  printf '\n==> %s\n' "$1"
}

run_as_app_user() {
  if [ "$(id -un)" = "$APP_USER" ]; then
    "$@"
  else
    sudo -u "$APP_USER" -H "$@"
  fi
}

run_in_app_dir() {
  run_as_app_user bash -lc "cd '$APP_DIR' && $*"
}

strip_optional_quotes() {
  local value="$1"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

read_env_file_value() {
  local key="$1"
  local env_file="$APP_DIR/.env"

  if [ ! -f "$env_file" ]; then
    return 1
  fi

  local line
  line="$(run_as_app_user bash -lc "grep -m1 -E '^${key}=' '$env_file' || true")"
  if [ -z "$line" ]; then
    return 1
  fi

  strip_optional_quotes "${line#*=}"
}

discover_database_url() {
  if [ -n "${KELVIN_DATABASE_URL:-}" ]; then
    printf '%s' "$KELVIN_DATABASE_URL"
    return 0
  fi

  local service_environment
  service_environment="$(systemctl show "$SERVICE_NAME" -p Environment --value)"
  if [ -n "$service_environment" ]; then
    local value
    value="$(printf '%s\n' "$service_environment" | tr ' ' '\n' | sed -n 's/^KELVIN_DATABASE_URL=//p' | head -n 1)"
    if [ -n "$value" ]; then
      strip_optional_quotes "$value"
      return 0
    fi
  fi

  read_env_file_value "KELVIN_DATABASE_URL"
}

apply_database_schemas() {
  local database_url="$1"

  if ! command -v psql >/dev/null 2>&1; then
    echo "Error: psql is required to apply database schemas." >&2
    exit 1
  fi

  run_as_app_user psql \
    "$database_url" \
    --set=ON_ERROR_STOP=1 \
    --file="$APP_DIR/infrastructure/sql/003_create_agent_audit_schema.sql"
  run_as_app_user psql \
    "$database_url" \
    --set=ON_ERROR_STOP=1 \
    --file="$APP_DIR/infrastructure/sql/004_create_security_audit_schema.sql"
}

if [ ! -d "$APP_DIR/.git" ]; then
  echo "Error: $APP_DIR is not a Git repository." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "Error: sudo is required for service restart and user switching." >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "Error: systemctl is required on the Kelvin VM." >&2
  exit 1
fi

log "Checking repository state"
dirty_output="$(run_in_app_dir "git status --porcelain --untracked-files=no")"
if [ -n "$dirty_output" ]; then
  echo "Error: tracked files in $APP_DIR have local changes:" >&2
  echo "$dirty_output" >&2
  echo "Commit, stash, or revert them before updating." >&2
  exit 1
fi

log "Fetching origin"
run_in_app_dir "git fetch origin"

log "Switching to $BRANCH"
run_in_app_dir "git switch '$BRANCH'"

log "Pulling latest origin/$BRANCH"
run_in_app_dir "git pull --ff-only origin '$BRANCH'"

if [ "$SKIP_UV_SYNC" -eq 0 ]; then
  log "Syncing locked production dependencies"
  run_in_app_dir "uv sync --locked --no-dev"
else
  log "Skipping uv sync"
fi

if [ "$SKIP_DB_SCHEMA" -eq 0 ]; then
  log "Applying database schemas"
  database_url="$(discover_database_url || true)"
  if [ -z "$database_url" ]; then
    echo "KELVIN_DATABASE_URL was not found; skipping database schema application."
  else
    apply_database_schemas "$database_url"
  fi
else
  log "Skipping database schemas"
fi

log "Restarting $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

log "Service status"
sudo systemctl status "$SERVICE_NAME" --no-pager --lines=20

log "Update complete"
