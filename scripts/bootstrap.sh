#!/usr/bin/env bash
# Idempotent local bootstrap for Aura.
#
#   ./scripts/bootstrap.sh
#
# Creates .env when missing, starts PostgreSQL and Gitea, creates the Gitea
# admin user, generates an API token, and starts the core containers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="$ROOT/.env"
COMPOSE=(docker compose)

log() { printf '[aura] %s\n' "$*"; }
fail() { printf '[aura] ERROR: %s\n' "$*" >&2; exit 1; }

random_secret() {
  openssl rand -hex 24
}

set_env_value() {
  local key="$1" value="$2"
  if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
    # Portable in-place replacement without requiring GNU sed flags.
    local tmp
    tmp="$(mktemp)"
    awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k{print k"="v; next} {print}' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

get_env_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true
}

# 1. Create .env with generated secrets.
if [[ ! -f "$ENV_FILE" ]]; then
  log "creating .env from .env.example"
  cp "$ROOT/.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  set_env_value AURA_POSTGRES_PASSWORD "$(random_secret)"
  set_env_value AURA_GITEA_PASSWORD "$(random_secret)"
  set_env_value AURA_DATABASE_URL "postgresql+asyncpg://aura:$(get_env_value AURA_POSTGRES_PASSWORD)@127.0.0.1:5433/aura"
fi
chmod 600 "$ENV_FILE"

PG_PASSWORD="$(get_env_value AURA_POSTGRES_PASSWORD)"
GITEA_USER="$(get_env_value AURA_GITEA_USER)"
[[ -n "$GITEA_USER" ]] || GITEA_USER=aura
GITEA_PASSWORD="$(get_env_value AURA_GITEA_PASSWORD)"

# 2. Start the database and Gitea.
log "starting PostgreSQL and Gitea"
"${COMPOSE[@]}" up -d db gitea

log "waiting for Gitea"
for _ in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:3000/api/v1/version" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "http://127.0.0.1:3000/api/v1/version" >/dev/null 2>&1 \
  || fail "Gitea did not become healthy; run: docker compose logs gitea"

# 3. Create the admin user (ignore "already exists").
if [[ -n "$GITEA_PASSWORD" ]]; then
  log "ensuring Gitea admin user '$GITEA_USER'"
  "${COMPOSE[@]}" exec -T --user git gitea gitea admin user create \
    --username "$GITEA_USER" \
    --password "$GITEA_PASSWORD" \
    --email "${GITEA_USER}@aura.local" \
    --admin \
    --must-change-password=false >/dev/null 2>&1 || true
fi

# 4. Generate an API token when none exists.
TOKEN="$(get_env_value AURA_GITEA_TOKEN)"
if [[ -z "$TOKEN" ]]; then
  log "generating Gitea API token"
  TOKEN_NAME="aura-api-$(date +%s)"
  TOKEN_OUTPUT="$("${COMPOSE[@]}" exec -T --user git gitea gitea admin user generate-access-token \
    --username "$GITEA_USER" \
    --token-name "$TOKEN_NAME" \
    --scopes all 2>&1 || true)"
  # Gitea prints the token as the last token-shaped word on stdout.
  TOKEN="$(printf '%s\n' "$TOKEN_OUTPUT" | grep -oE '[A-Za-z0-9_-]{30,}' | tail -1 || true)"
  if [[ -n "$TOKEN" ]]; then
    set_env_value AURA_GITEA_TOKEN "$TOKEN"
    log "Gitea API token stored in .env"
  else
    log "WARNING: could not generate an API token automatically."
    log "Create one at http://127.0.0.1:3000/user/settings/applications and set AURA_GITEA_TOKEN in .env"
  fi
fi

# 5. Generate a Gitea Actions runner registration token when missing.
RUNNER_TOKEN="$(get_env_value AURA_RUNNER_TOKEN)"
if [[ -z "$RUNNER_TOKEN" ]]; then
  RUNNER_OUTPUT="$("${COMPOSE[@]}" exec -T --user git gitea gitea actions generate-runner-token 2>&1 || true)"
  RUNNER_TOKEN="$(printf '%s\n' "$RUNNER_OUTPUT" | grep -oE '[A-Za-z0-9_-]{30,}' | tail -1 || true)"
  if [[ -n "$RUNNER_TOKEN" ]]; then
    set_env_value AURA_RUNNER_TOKEN "$RUNNER_TOKEN"
    log "Gitea Actions runner token stored in .env"
  fi
fi

# 6. Ensure everything is up.
log "starting core containers"
"${COMPOSE[@]}" up -d

log "ready"
log "  Gitea:   http://127.0.0.1:3000"
log "  Next:    make backend   (terminal 1)"
log "           make web       (terminal 2)"
log "       or  make up        (background)"
