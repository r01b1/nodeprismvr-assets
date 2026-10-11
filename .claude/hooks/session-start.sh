#!/bin/bash
# SessionStart hook for Claude Code cloud sessions: install Blender with the
# official Blender Lab MCP add-on and start the headless Blender instance
# that the `blender` MCP server from .mcp.json talks to.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

"$CLAUDE_PROJECT_DIR/scripts/setup-blender.sh"
"$CLAUDE_PROJECT_DIR/scripts/blender-mcp-server.sh" start
