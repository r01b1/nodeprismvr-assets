# nodeprismvr-assets
assets for the nodeprismvr project

3D models are built in [Blender](https://www.blender.org/) through the official
[Blender Lab MCP server](https://www.blender.org/lab/mcp-server/) and exported
as glTF binary (`.glb`) for the three.js app.

## The library

Browse the assets at **https://r01b1.github.io/nodeprismvr-assets/**.

| What | URL |
| --- | --- |
| Gallery with 3D viewer | `https://r01b1.github.io/nodeprismvr-assets/` |
| Catalogue for apps | `https://r01b1.github.io/nodeprismvr-assets/library/index.json` |
| An asset | `https://r01b1.github.io/nodeprismvr-assets/library/<id>/<id>.glb` |

Paths in `index.json` are relative to the index file. Loading an asset in three.js:

```js
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const base = "https://r01b1.github.io/nodeprismvr-assets/library/";
const index = await (await fetch(base + "index.json")).json();
const gltf = await new GLTFLoader().loadAsync(base + index.assets[0].file);
scene.add(gltf.scene);
```

Assets are glTF 2.0 binary, +Y up, 1 unit = 1 metre, origin at the base.
Each asset folder holds the `.glb`, a `preview.webp` and a `meta.json`; the
Blender sources are in `sources/`.

## How the setup works

| File | Purpose |
| --- | --- |
| `.mcp.json` | Registers the `blender` MCP server (Blender Lab `blender_mcp` v1.0.3, run with `uvx`), with a 10-minute tool timeout instead of the cloud environment's 60 s. |
| `scripts/setup-blender.sh` | Installs Blender 5.2.2 LTS (Linux x64), the Blender Lab MCP add-on 1.0.3 and the EGL/Mesa libraries for headless rendering. Downloads are checked against pinned SHA-256 sums. |
| `scripts/blender-mcp-server.sh` | `start` / `stop` / `restart` / `status` / `save` for a headless Blender that serves the add-on's socket on `127.0.0.1:9876`. `save` snapshots the scene to `.blender-session/scene.blend`, `start` reopens that snapshot. |
| `scripts/render_views.py` | Runs inside Blender: renders an object from 8 angles (optionally with a wireframe overlay or zoomed on a detail) into one labelled contact sheet for visual checks. `scripts/render_views_cli.py` runs the same on a saved `.blend` from the command line, for renders too long for an MCP call. |
| `scripts/setup-flux.sh`, `scripts/flux.sh` | FLUX.2 [klein] 9B (4-bit, via stable-diffusion.cpp on the CPU) for inspiration images. The setup builds `sd-cli` and downloads about 11 GB of weights (pinned revisions and SHA-256 sums) to `/opt/flux`; `flux.sh "prompt" out.png` generates a 512x512 image in about 11 minutes. FLUX Non-Commercial License. |
| `scripts/library_export.py`, `scripts/build_library_index.py` | Export an asset from Blender into `library/` (GLB, preview, metadata, .blend source) and rebuild `library/index.json`. |
| `site/`, `scripts/build_site.sh`, `.github/workflows/pages.yml` | The gallery website; the workflow assembles it with the library and deploys it to GitHub Pages on every push to `main`. |
| `.claude/hooks/session-start.sh` | Claude Code cloud sessions only: runs the Blender scripts when a session starts and the FLUX setup in the background. |
| `.claude/settings.json` | Registers that hook, plus a PostToolUse hook that snapshots the scene after every `execute_blender_code`, so a paused cloud VM does not lose it. |

```
Claude Code ⇐ MCP/stdio ⇒ blender-mcp (uvx) ⇐ TCP 9876 ⇒ Blender --background + MCP add-on
```

In a fresh cloud container the hook takes about a minute (Blender download and
unpack); when everything is already installed it returns immediately.

The MCP server runs LLM-generated Python inside Blender without a sandbox.
That is fine in the throwaway cloud container; on your own machine, see the
[security note](https://www.blender.org/lab/mcp-server/) first.

## Using it on your own machine

1. Install Blender 5.1 or newer (5.2 LTS recommended).
2. Install the add-on: drag
   [mcp-1.0.3.zip](https://projects.blender.org/lab/blender_mcp/releases/download/v1.0.3/mcp-1.0.3.zip?repository=https%3A%2F%2Flab.blender.org%2F&blender_version_min=5.1.0)
   into Blender (twice: once to add the Blender Lab repository, once to
   install), then start the server from the add-on preferences.
3. Install [uv](https://docs.astral.sh/uv/). Claude Code picks up `.mcp.json`
   and asks once to approve the `blender` server. If `blender` is not on your
   `PATH`, set `BLENDER_PATH` for the `*_for_cli` tools.

## Updating versions

- Blender and add-on: change the versions and SHA-256 sums at the top of
  `scripts/setup-blender.sh`.
- MCP server: change the commit in `.mcp.json` to the commit of the new
  `blender_mcp` release tag.
