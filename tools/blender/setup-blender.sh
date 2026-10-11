#!/bin/bash
# Install Blender (official Linux x64 build) and the official Blender Lab MCP
# add-on (https://www.blender.org/lab/mcp-server/) for headless use.
# Idempotent: steps that are already done are skipped.
#
# Usage: tools/blender/setup-blender.sh
set -euo pipefail

BLENDER_VERSION="5.2.2"
BLENDER_SHA256="84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168"
MCP_ADDON_VERSION="1.0.3"
MCP_ADDON_SHA256="a7a9da816192502e5a0a202a396444e266b47d8fc4f74ad4698048bd43040707"

BLENDER_SERIES="${BLENDER_VERSION%.*}"
BLENDER_DIR="/opt/blender-$BLENDER_VERSION-linux-x64"
BLENDER_URL="https://download.blender.org/release/Blender$BLENDER_SERIES/blender-$BLENDER_VERSION-linux-x64.tar.xz"
MCP_ADDON_URL="https://projects.blender.org/lab/blender_mcp/releases/download/v$MCP_ADDON_VERSION/mcp-$MCP_ADDON_VERSION.zip"
MCP_ADDON_MANIFEST="$HOME/.config/blender/$BLENDER_SERIES/extensions/user_default/mcp/blender_manifest.toml"

log() { echo "[setup-blender] $*" >&2; }

# Download $1 to $2 and check it against the sha256 $3.
fetch() {
  curl -fsSL --retry 4 --retry-delay 2 -o "$2" "$1"
  echo "$3  $2" | sha256sum --check --quiet
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if [ ! -x "$BLENDER_DIR/blender" ]; then
  log "Installing Blender $BLENDER_VERSION into $BLENDER_DIR"
  fetch "$BLENDER_URL" "$tmp/blender.tar.xz" "$BLENDER_SHA256"
  # Extract next to the target and rename, so an interrupted run never
  # leaves a half-extracted install that looks complete.
  rm -rf "$BLENDER_DIR.partial"
  mkdir -p "$BLENDER_DIR.partial"
  tar -xJf "$tmp/blender.tar.xz" -C "$BLENDER_DIR.partial" --strip-components=1
  mv "$BLENDER_DIR.partial" "$BLENDER_DIR"
fi
ln -sfn "$BLENDER_DIR" /opt/blender
ln -sf /opt/blender/blender /usr/local/bin/blender

# EEVEE, Workbench and viewport renders need an OpenGL context even in
# background mode; Mesa's llvmpipe provides one without a GPU.
GL_PACKAGES=(libegl1 libegl-mesa0 libgbm1 libgl1-mesa-dri)
installed_count="$(dpkg-query -W -f='${Status}\n' "${GL_PACKAGES[@]}" 2>/dev/null | grep -c '^install ok installed$' || true)"
if [ "$installed_count" -ne "${#GL_PACKAGES[@]}" ]; then
  log "Installing EGL/Mesa libraries for headless rendering"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >&2
  apt-get install -y -qq --no-install-recommends "${GL_PACKAGES[@]}" >&2
fi

if ! grep -qx "version = \"$MCP_ADDON_VERSION\"" "$MCP_ADDON_MANIFEST" 2>/dev/null; then
  log "Installing Blender MCP add-on $MCP_ADDON_VERSION"
  fetch "$MCP_ADDON_URL" "$tmp/mcp-$MCP_ADDON_VERSION.zip" "$MCP_ADDON_SHA256"
  "$BLENDER_DIR/blender" --background --command extension install-file \
    -r user_default --enable "$tmp/mcp-$MCP_ADDON_VERSION.zip" >&2
fi

log "Blender $BLENDER_VERSION with MCP add-on $MCP_ADDON_VERSION is installed"
