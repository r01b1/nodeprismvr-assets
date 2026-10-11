#!/bin/bash
# Run a headless Blender instance with the official Blender Lab MCP add-on
# listening on a local TCP socket. The `blender` MCP server (see .mcp.json)
# relays tool calls such as `execute_blender_code` to this instance.
#
# The scene is kept in a snapshot file: `save` writes it (a PostToolUse hook
# calls this after every `execute_blender_code`), and `start` reopens it, so a
# Blender that was stopped, e.g. by the cloud VM pausing, continues where it was.
#
# Usage: scripts/blender-mcp-server.sh {start|stop|restart|status|save} [file.blend]
set -euo pipefail

BLENDER="${BLENDER_PATH:-blender}"
HOST="${BLENDER_MCP_HOST:-127.0.0.1}"
PORT="${BLENDER_MCP_PORT:-9876}"
RUN_DIR="${BLENDER_MCP_RUN_DIR:-/tmp/blender-mcp}"
PID_FILE="$RUN_DIR/blender.pid"
LOG_FILE="$RUN_DIR/blender.log"
SNAPSHOT="${BLENDER_MCP_SNAPSHOT:-$(cd "$(dirname "$0")/.." && pwd)/.blender-session/scene.blend}"

# Run Python code in Blender through the add-on's socket protocol (JSON
# terminated by a null byte). Fails unless Blender answers with "ok".
blender_exec() {
  python3 - "$HOST" "$PORT" "$1" <<'PY'
import json, socket, sys
host, port, code = sys.argv[1], int(sys.argv[2]), sys.argv[3]
req = json.dumps({"type": "execute", "code": code, "strict_json": True}) + "\0"
with socket.create_connection((host, port), timeout=10) as s:
    s.sendall(req.encode())
    buf = b""
    while b"\0" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
resp = json.loads(buf.partition(b"\0")[0])
if resp.get("status") != "ok":
    sys.exit("Blender error: {}".format(resp.get("message")))
PY
}

ping() {
  blender_exec "result = {}" >/dev/null 2>&1
}

# Save a copy of the current scene to the snapshot, and remember which file
# the scene was opened from (the snapshot replaces that path after a restore).
save() {
  local snapshot
  mkdir -p "$(dirname "$SNAPSHOT")"
  snapshot="$(python3 -c 'import sys; print(repr(sys.argv[1]))' "$SNAPSHOT")"
  blender_exec "
import bpy
if bpy.data.filepath != $snapshot:
    with open($snapshot + '.source', 'w') as f:
        f.write(bpy.data.filepath)
bpy.ops.wm.save_as_mainfile(filepath=$snapshot, copy=True)
result = {}
"
}

start() {
  local file="${1:-}"
  if ping; then
    echo "Blender MCP add-on already listening on $HOST:$PORT"
    return 0
  fi
  if [ -z "$file" ] && [ -f "$SNAPSHOT" ]; then
    file="$SNAPSHOT"
  fi
  # A .blend passed as argument loads without window context in `--command`
  # mode (no bpy.context.active_object etc.), so open it with Python instead,
  # keeping the startup file's UI.
  local open_file=()
  if [ -n "$file" ]; then
    open_file=(--python-expr "import bpy; bpy.ops.wm.open_mainfile(filepath=$(python3 -c 'import sys; print(repr(sys.argv[1]))' "$file"), load_ui=False)")
  fi
  mkdir -p "$RUN_DIR"
  # Detach completely (own session, no inherited stdio) so the process
  # outlives the calling shell or hook.
  setsid nohup "$BLENDER" --background --online-mode "${open_file[@]}" \
    --command blender_mcp --host "$HOST" --port "$PORT" \
    >"$LOG_FILE" 2>&1 </dev/null &
  echo $! >"$PID_FILE"
  for _ in $(seq 1 60); do
    if ping; then
      echo "Blender MCP add-on listening on $HOST:$PORT (pid $(cat "$PID_FILE"), log $LOG_FILE)"
      if [ "$file" = "$SNAPSHOT" ]; then
        local source
        source="$(cat "$SNAPSHOT.source" 2>/dev/null || true)"
        echo "Restored the scene snapshot saved $(date -r "$SNAPSHOT" '+%Y-%m-%d %H:%M:%S %Z')" \
          "${source:+(the scene was opened from $source; save it there explicitly)}"
      fi
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
    save || echo "Could not save the scene snapshot before stopping" >&2
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
  save) save ;;
  status)
    if ping; then echo "running on $HOST:$PORT"; else echo "not running"; exit 1; fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|save} [file.blend]" >&2
    exit 2
    ;;
esac
