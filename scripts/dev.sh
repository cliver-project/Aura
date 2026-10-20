#!/usr/bin/env bash
# Start, stop, or inspect the Aura backend and frontend dev servers.
#
#   ./scripts/dev.sh start|stop|status
#
# PID files live in var/pids, logs in var/logs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PID_DIR="$ROOT/var/pids"
LOG_DIR="$ROOT/var/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

is_running() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

wait_http() {
  local url="$1" name="$2"
  for _ in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      printf '[aura] %s is ready: %s\n' "$name" "$url"
      return 0
    fi
    sleep 1
  done
  printf '[aura] WARNING: %s did not respond in time; check %s\n' "$name" "$LOG_DIR" >&2
  return 1
}

start_backend() {
  if is_running "$BACKEND_PID"; then
    printf '[aura] backend already running (pid %s)\n' "$(cat "$BACKEND_PID")"
    return 0
  fi
  printf '[aura] applying database migrations\n'
  if ! (cd "$ROOT/backend" && uv run python -m aura.migrate upgrade head) \
    >>"$BACKEND_LOG" 2>&1; then
    printf '[aura] ERROR: database migration failed; see %s\n' "$BACKEND_LOG" >&2
    return 1
  fi
  printf '[aura] starting backend\n'
  (
    cd "$ROOT/backend"
    if [[ -x "$ROOT/backend/.venv/bin/uvicorn" ]]; then
      # Start the real process, not the uv wrapper: the PID file must point at
      # uvicorn so stop/restart cannot leave an orphan holding port 8000.
      nohup "$ROOT/backend/.venv/bin/uvicorn" aura.main:app --host 127.0.0.1 --port 8000 \
        >>"$BACKEND_LOG" 2>&1 &
    else
      nohup uv run uvicorn aura.main:app --host 127.0.0.1 --port 8000 \
        >>"$BACKEND_LOG" 2>&1 &
    fi
    echo $! >"$BACKEND_PID"
  )
  wait_http "http://127.0.0.1:8000/api/health" "backend" || true
}

start_frontend() {
  if is_running "$FRONTEND_PID"; then
    printf '[aura] frontend already running (pid %s)\n' "$(cat "$FRONTEND_PID")"
    return 0
  fi
  printf '[aura] starting frontend\n'
  (
    cd "$ROOT/frontend"
    if [[ -x "$ROOT/frontend/node_modules/.bin/vite" ]]; then
      nohup "$ROOT/frontend/node_modules/.bin/vite" --host 127.0.0.1 --port 5173 \
        >>"$FRONTEND_LOG" 2>&1 &
    else
      nohup pnpm dev --host 127.0.0.1 --port 5173 >>"$FRONTEND_LOG" 2>&1 &
    fi
    echo $! >"$FRONTEND_PID"
  )
  wait_http "http://127.0.0.1:5173" "frontend" || true
}

stop_one() {
  local pidfile="$1" name="$2"
  if is_running "$pidfile"; then
    local pid
    pid="$(cat "$pidfile")"
    printf '[aura] stopping %s (pid %s)\n' "$name" "$pid"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
}

status_one() {
  local pidfile="$1" name="$2" url="$3"
  if is_running "$pidfile"; then
    printf '  %-9s running (pid %s)\n' "$name" "$(cat "$pidfile")"
  else
    printf '  %-9s stopped\n' "$name"
  fi
  if curl -fsS "$url" >/dev/null 2>&1; then
    printf '  %-9s http OK  %s\n' "$name" "$url"
  else
    printf '  %-9s http --  %s\n' "$name" "$url"
  fi
}

case "${1:-start}" in
  start)
    start_backend
    start_frontend
    printf '[aura] UI: http://127.0.0.1:5173\n'
    ;;
  stop)
    stop_one "$FRONTEND_PID" frontend
    stop_one "$BACKEND_PID" backend
    ;;
  status)
    status_one "$BACKEND_PID" backend "http://127.0.0.1:8000/api/health"
    status_one "$FRONTEND_PID" frontend "http://127.0.0.1:5173"
    ;;
  restart)
    "$0" stop
    "$0" start
    ;;
  *)
    echo "usage: $0 {start|stop|status|restart}" >&2
    exit 2
    ;;
esac
