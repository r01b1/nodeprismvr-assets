# nodeprismvr-assets
assets for the nodeprismvr project

A free (CC0) library of 3D assets for the NodePrism VR three.js app. Models
are built in [Blender](https://www.blender.org/), here mostly through the
official [Blender Lab MCP server](https://www.blender.org/lab/mcp-server/), and
published as glTF binary (`.glb`).

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
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";

const base = "https://r01b1.github.io/nodeprismvr-assets/library/";
const index = await (await fetch(base + "index.json")).json();
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const gltf = await loader.loadAsync(base + index.assets[0].file);
scene.add(gltf.scene);
```

Assets are glTF 2.0 binary, +Y up, 1 unit = 1 metre, origin at the base.
Dense meshes may be compressed: `KHR_mesh_quantization` loads as is,
`EXT_meshopt_compression` needs the `MeshoptDecoder` above (it ships with
three.js). Each asset's `extensions` in `index.json` lists what it uses.
Each asset folder holds the `.glb`, a `preview.webp` and a `meta.json`; the
Blender sources are in `sources/`.

## Repository layout

| Path | Contents |
| --- | --- |
| `library/` | The published assets: `<id>/<id>.glb`, `<id>/preview.webp`, `<id>/meta.json`, and `library.json` (library-wide fields) |
| `sources/` | Blender source file of each asset |
| `site/` | The gallery website and the review page |
| `tools/` | Tooling to build and publish assets (Blender, FLUX, library) |
| `docs/` | Style lines: shared materials, motifs and budgets (`styles.md`) |
| `.claude/`, `.mcp.json`, `CLAUDE.md` | Configuration for building assets with Claude Code |

## Contributing assets

Assets are submitted as pull requests and reviewed before they enter the
library. A submission adds one folder per asset and changes nothing else:

```
library/<id>/<id>.glb       glTF 2.0 binary, +Y up, 1 unit = 1 metre, standing on y = 0,
                            Principled BSDF materials, self-contained, ideally < 20k triangles
library/<id>/preview.webp   512 x 512, transparent background
library/<id>/meta.json      {"id", "name", "description", "tags", "author"}
sources/<id>/<id>.blend     the Blender source
```

Asset ids and tags are lowercase kebab-case. Triangle counts, sizes and
materials are read from the GLB automatically. `tools/blender/library_export.py`,
run inside Blender, writes all of these files.

Every submission is checked automatically (files, glTF-Validator, budgets).
The maintainer then looks at it in 3D on the
[review page](https://r01b1.github.io/nodeprismvr-assets/review.html) and
approves it by merging the pull request. By contributing an asset you dedicate
it to the public domain under CC0 1.0.

## Tooling: how assets are made

| File | Purpose |
| --- | --- |
| `.mcp.json` | Registers the `blender` MCP server (Blender Lab `blender_mcp` v1.0.3, run with `uvx`), with a 10-minute tool timeout instead of the cloud environment's 60 s. |
| `tools/blender/setup-blender.sh` | Installs Blender 5.2.2 LTS (Linux x64), the Blender Lab MCP add-on 1.0.3 and the EGL/Mesa libraries for headless rendering. Downloads are checked against pinned SHA-256 sums. |
| `tools/blender/blender-mcp-server.sh` | `start` / `stop` / `restart` / `status` / `save` for a headless Blender that serves the add-on's socket on `127.0.0.1:9876`. `save` snapshots the scene to `.blender-session/scene.blend`, `start` reopens that snapshot. |
| `tools/blender/render_views.py` | Runs inside Blender: renders an object from 8 angles (optionally with a wireframe overlay or zoomed on a detail) into one labelled contact sheet for visual checks. `tools/blender/render_views_cli.py` runs the same on a saved `.blend` from the command line, for renders too long for an MCP call. |
| `tools/flux/setup-flux.sh`, `tools/flux/flux.sh` | FLUX.2 [klein] 9B (4-bit, via stable-diffusion.cpp on the CPU) for inspiration images. The setup builds `sd-cli` and downloads about 11 GB of weights (pinned revisions and SHA-256 sums) to `/opt/flux`; `flux.sh "prompt" out.png` generates a 512x512 image in about 11 minutes. FLUX Non-Commercial License. |
| `tools/blender/library_export.py` | Export an asset from Blender into `library/` and `sources/` (GLB, WebP preview, meta.json, .blend source). |
| `tools/gltf/optimize_glb.mjs` | Compresses a GLB with glTF Transform and meshoptimizer: `--mode quantize` (`KHR_mesh_quantization`, no decoder needed) or `--mode meshopt` (`EXT_meshopt_compression`, needs three.js's `MeshoptDecoder`). Install with `npm ci --prefix tools/gltf`. |
| `tools/library/` | `build_library_index.py` builds the catalogue from meta.json and the GLBs (`glb_stats.py`); `check_submission.py` and `validate_glb.mjs` check pull requests (`.github/workflows/check-submission.yml`). |
| `site/`, `tools/library/build_site.sh`, `.github/workflows/pages.yml` | The gallery and review pages; the workflow assembles them with the library and the catalogue and deploys them to GitHub Pages on every push to `main`. |
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
  `tools/blender/setup-blender.sh`.
- MCP server: change the commit in `.mcp.json` to the commit of the new
  `blender_mcp` release tag.

## License

- Assets (`library/`, `sources/`): [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/),
  public domain, see [LICENSE-ASSETS](LICENSE-ASSETS).
- Everything else (tools, website, configuration): MIT, see [LICENSE](LICENSE).
- FLUX.2 [klein] 9B, used for inspiration images, is not part of this
  repository; the setup script downloads it under the FLUX Non-Commercial License.
