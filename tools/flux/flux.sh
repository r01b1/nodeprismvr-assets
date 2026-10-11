#!/bin/bash
# Generate an image with FLUX.2 [klein] 9B on the CPU (installed by
# tools/flux/setup-flux.sh). A random seed is used unless one is passed.
#
# Usage: tools/flux/flux.sh "prompt" out.png [sd-cli options, e.g. -W 768 -H 768 -s 42 -r reference.png]
set -euo pipefail

FLUX_DIR="${FLUX_DIR:-/opt/flux}"
SD_CLI="$FLUX_DIR/bin/sd-cli"
MODELS="$FLUX_DIR/models"

if [ $# -lt 2 ]; then
  echo "Usage: $0 \"prompt\" out.png [sd-cli options]" >&2
  exit 2
fi
for f in "$SD_CLI" "$MODELS/flux-2-klein-9b-Q4_K_M.gguf" "$MODELS/Qwen3-8B-Q4_K_M.gguf" "$MODELS/flux2-vae.safetensors"; do
  if [ ! -e "$f" ]; then
    echo "FLUX is not installed yet ($f is missing). The SessionStart hook installs it" \
      "in the background (log: /tmp/flux-setup.log); tools/flux/setup-flux.sh finishes it." >&2
    exit 1
  fi
done

prompt="$1"
out="$2"
shift 2
mkdir -p "$(dirname "$out")"
exec "$SD_CLI" \
  --diffusion-model "$MODELS/flux-2-klein-9b-Q4_K_M.gguf" \
  --llm "$MODELS/Qwen3-8B-Q4_K_M.gguf" \
  --vae "$MODELS/flux2-vae.safetensors" \
  --cfg-scale 1.0 --steps 4 -W 512 -H 512 -s -1 \
  --diffusion-fa --mmap -t "$(nproc)" \
  -p "$prompt" -o "$out" "$@"
