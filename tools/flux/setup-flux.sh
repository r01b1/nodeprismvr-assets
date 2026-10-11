#!/bin/bash
# Install the FLUX.2 [klein] 9B image generator for CPU use: stable-diffusion.cpp
# built from source, plus quantized weights (about 11 GB). Idempotent: steps
# that are already done are skipped.
#
# Licence: FLUX.2 [klein] 9B is under the FLUX Non-Commercial License, see
# https://huggingface.co/black-forest-labs/FLUX.2-klein-9B.
#
# Usage: tools/flux/setup-flux.sh
set -euo pipefail

SDCPP_COMMIT="2988060a4338a5dcd94721c964a8e87003c1ac8b"
FLUX_DIR="${FLUX_DIR:-/opt/flux}"

# Hugging Face repo, revision, file in the repo, local name, SHA-256.
MODEL_FILES=(
  "unsloth/FLUX.2-klein-9B-GGUF fde8634245fe6b749a221c25b34672b5b8fbd079 flux-2-klein-9b-Q4_K_M.gguf flux-2-klein-9b-Q4_K_M.gguf 5489463ed96056b0bb5472abb5d1bba7055e48d574e37877acb43b407465e26f"
  "unsloth/Qwen3-8B-GGUF a6adef130ffb23ddaf1a62fec9dced968c9bc482 Qwen3-8B-Q4_K_M.gguf Qwen3-8B-Q4_K_M.gguf 120307ba529eb2439d6c430d94104dabd578497bc7bfe7e322b5d9933b449bd4"
  "black-forest-labs/FLUX.2-klein-4B e7b7dc27f91deacad38e78976d1f2b499d76a294 vae/diffusion_pytorch_model.safetensors flux2-vae.safetensors ca70d2202afe6415bdbcb8793ba8cd99fd159cfe6192381504d6c4d3036e0f04"
)

log() { echo "[setup-flux] $*" >&2; }

fetch_model() {
  local repo="$1" rev="$2" path="$3" name="$4" sha="$5"
  local dest="$FLUX_DIR/models/$name"
  [ -f "$dest" ] && return 0
  log "Downloading $repo/$path"
  curl -fsSL --retry 4 --retry-delay 2 -o "$dest.partial" "https://huggingface.co/$repo/resolve/$rev/$path"
  echo "$sha  $dest.partial" | sha256sum --check --quiet
  mv "$dest.partial" "$dest"
}

# The binary is built for this machine's CPU (AVX-512 etc.); rebuild when the
# VM comes back on a CPU with different features.
build_sdcpp() {
  local src="$FLUX_DIR/stable-diffusion.cpp"
  local cpu
  cpu="$(grep -m1 '^flags' /proc/cpuinfo | sha256sum | cut -c1-16)"
  if [ -x "$FLUX_DIR/bin/sd-cli" ] && [ "$(cat "$FLUX_DIR/bin/.built-for" 2>/dev/null)" = "$SDCPP_COMMIT $cpu" ]; then
    return 0
  fi
  log "Building stable-diffusion.cpp $SDCPP_COMMIT"
  if [ ! -d "$src/.git" ]; then
    git init -q "$src"
    git -C "$src" remote add origin https://github.com/leejet/stable-diffusion.cpp.git
  fi
  git -C "$src" fetch -q --depth 1 origin "$SDCPP_COMMIT"
  git -C "$src" checkout -q --force FETCH_HEAD
  git -C "$src" submodule update -q --init --recursive --depth 1
  rm -rf "$src/build"
  cmake -S "$src" -B "$src/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON >&2
  cmake --build "$src/build" --config Release -j"$(nproc)" --target sd-cli >&2
  mkdir -p "$FLUX_DIR/bin"
  cp "$src/build/bin/sd-cli" "$FLUX_DIR/bin/sd-cli"
  echo "$SDCPP_COMMIT $cpu" >"$FLUX_DIR/bin/.built-for"
}

mkdir -p "$FLUX_DIR/models"
# One setup at a time; a second run waits and then finds everything done.
exec 9>"$FLUX_DIR/.setup.lock"
flock 9
pids=()
build_sdcpp &
pids+=($!)
for spec in "${MODEL_FILES[@]}"; do
  # shellcheck disable=SC2086 # Split the spec into its fields.
  fetch_model $spec &
  pids+=($!)
done
fail=0
for pid in "${pids[@]}"; do
  wait "$pid" || fail=1
done
if [ "$fail" -ne 0 ]; then
  log "Setup failed"
  exit 1
fi
log "FLUX.2 [klein] 9B is installed in $FLUX_DIR"
