#!/bin/bash
# Run a headless Blender instance with the official Blender Lab MCP add-on
# listening on a local TCP socket. The `blender` MCP server (see .mcp.json)
# relays tool calls such as `execute_blender_code` to this instance.
#
# Usage: scripts/blender-mcp-server.sh {start|stop|restart|status} [file.blend]
set -euo pipefail

BLENDER="${BLENDER_PATH:-blender}"
HOST="${BLENDER_MCP_HOST:-127.0.0.1}"
PORT="${BLENDER_MCP_PORT:-9876}"
RUN_DIR="${BLENDER_MCP_RUN_DIR:-/tmp/blender-mcp}"
PID_FILE="$RUN_DIR/blender.pid"
LOG_FILE="$RUN_DIR/blender.log"

# Send a trivial request through the add-on's socket protocol
# (JSON terminated by a null byte) and check that Blender answers.
ping() {
  python3 - "$HOST" "$PORT" <<'PY' >/dev/null 2>&1
import json, socket, sys
req = json.dumps({"type": "execute", "code": "result = {'ok': True}", "strict_json": True}) + "\0"
with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=10) as s:
    s.sendall(req.encode())
    buf = b""
    while b"\0" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
resp = json.loads(buf.partition(b"\0")[0])
sys.exit(0 if resp.get("status") == "ok" else 1)
PY
}

start() {
  if ping; then
    echo "Blender MCP add-on already listening on $HOST:$PORT"
    return 0
  fi
  mkdir -p "$RUN_DIR"
  # Detach completely (own session, no inherited stdio) so the process
  # outlives the calling shell or hook.
  setsid nohup "$BLENDER" --background --online-mode ${1:+"$1"} \
    --command blender_mcp --host "$HOST" --port "$PORT" \
    >"$LOG_FILE" 2>&1 </dev/null &
  echo $! >"$PID_FILE"
  for _ in $(seq 1 60); do
    if ping; then
      echo "Blender MCP add-on listening on $HOST:$PORT (pid $(cat "$PID_FILE"), log $LOG_FILE)"
      return 0
    fi
    if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  echo "Blender MCP add-on failed to start, see $LOG_FILE:" >&2
  tail -n 20 "$LOG_FILE" >&2 || true
  return 1
}

stop() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    kill "$(cat "$PID_FILE")"
    echo "Stopped Blender (pid $(cat "$PID_FILE"))"
  else
    echo "Blender MCP add-on is not running (no live pid file)"
  fi
  rm -f "$PID_FILE"
}

case "${1:-}" in
  start) start "${2:-}" ;;
  stop) stop ;;
  restart) stop; sleep 1; start "${2:-}" ;;
  status)
    if ping; then echo "running on $HOST:$PORT"; else echo "not running"; exit 1; fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status} [file.blend]" >&2
    exit 2
    ;;
esac
