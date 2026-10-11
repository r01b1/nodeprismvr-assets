#!/bin/bash
# SessionStart hook for Claude Code cloud sessions: install Blender with the
# official Blender Lab MCP add-on and start the headless Blender instance
# that the `blender` MCP server from .mcp.json talks to. The FLUX image
# generator (about 11 GB of downloads) is set up in the background.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

setsid nohup "$CLAUDE_PROJECT_DIR/tools/flux/setup-flux.sh" >/tmp/flux-setup.log 2>&1 </dev/null &

"$CLAUDE_PROJECT_DIR/tools/blender/setup-blender.sh"
"$CLAUDE_PROJECT_DIR/tools/blender/blender-mcp-server.sh" start
