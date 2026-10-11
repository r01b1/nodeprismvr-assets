# nodeprismvr-assets

3D assets for the nodeprismvr three.js app, modelled in Blender through the
official Blender Lab MCP server (https://www.blender.org/lab/mcp-server/).

## Blender and MCP in this repo

- In cloud sessions, the SessionStart hook (`.claude/hooks/session-start.sh`)
  installs Blender 5.2.2 LTS and the MCP add-on 1.0.3 (`tools/blender/setup-blender.sh`),
  then starts a headless Blender that serves the add-on's socket on
  127.0.0.1:9876 (`tools/blender/blender-mcp-server.sh`).
- `.mcp.json` registers the `blender` MCP server (official, pinned to the v1.0.3
  commit). Its tools appear as `mcp__blender__*`.
- If a tool reports it cannot connect to Blender, run
  `tools/blender/blender-mcp-server.sh start`. `status` checks it, the log is
  `/tmp/blender-mcp/blender.log`.
- Blender has no GUI here: the screenshot and `jump_to_*` tools do not work.
  Model with `execute_blender_code`; inspect with the `get_*` summary tools
  and look at the asset with renders (see "Visual checks").
- EEVEE, Cycles (CPU) and Workbench all render headless (Mesa llvmpipe).
  `render_thumbnail_to_path` and `render_viewport_to_path` write into
  Blender's temp dir, so use the `filepath` they return. To render to a chosen
  path, set `scene.render.filepath` and call `bpy.ops.render.render(write_still=True)`.

## Keeping the scene

- After a few idle minutes the cloud VM pauses: files stay, but Blender is
  stopped. So after every `execute_blender_code` call a PostToolUse hook saves
  a copy of the scene to `.blender-session/scene.blend` (gitignored, takes
  about 0.1 s), and `tools/blender/blender-mcp-server.sh start` reopens it. The
  SessionStart hook output says when a snapshot was restored.
- After a restore, `bpy.data.filepath` is the snapshot. If the scene came from
  another file, the hook output names it; save there explicitly.
- A VM that stays paused long enough is reclaimed, and the snapshot is lost
  with it. Save asset work as `sources/<id>/<id>.blend` and commit and push
  it at milestones, e.g. when a modelling step is done.

## Time limits and long renders

- The cloud environment sets `MCP_TOOL_TIMEOUT=60000` (60 s). `.mcp.json`
  raises it for the `blender` server with `"timeout": 600000`; that takes
  effect when a session starts.
- The official MCP server itself stops waiting for Blender after 300 s per
  call. The headless Blender also handles one call at a time and is blocked
  until the call finishes.
- Run anything that may take longer than a few minutes (final renders, high
  resolutions or samples, Cycles) in its own Blender process instead:
  1. Snapshot the scene with `execute_blender_code`:
     `bpy.ops.wm.save_as_mainfile(filepath="/tmp/jobs/crystal.blend", copy=True)`
  2. Render with Bash and `run_in_background`, for example
     `blender --background /tmp/jobs/crystal.blend --python tools/blender/render_views_cli.py -- --out /tmp/views/crystal --size 1024 --samples 64`
     or a plain render with `blender --background /tmp/jobs/crystal.blend -o /tmp/renders/crystal_ -F PNG -f 1`.
  3. Wait for the background task's notification, then look at the images.

## Visual checks

Look at the asset regularly while modelling, not only at the end.
`tools/blender/render_views.py` renders an object from several angles into one
labelled contact sheet, then restores the scene:

```python
path = "/home/user/nodeprismvr-assets/tools/blender/render_views.py"
exec(compile(open(path).read(), path, "exec"))
result = render_views(["Crystal"], "/tmp/views/crystal", wireframe=True,
                      engine="BLENDER_WORKBENCH")
```

Then open `result["sheet"]` with the Read tool.

- Default views: front, right, back, left, top, bottom (orthographic, for
  proportions) and two perspective 3/4 views.
- `engine="BLENDER_WORKBENCH"` with `wireframe=True` takes about 2 s for all
  views. Use it after each modelling step to check shape and topology.
- The default EEVEE engine (`samples=4`) takes about 25 s for all views at
  `size=384` and shows materials with three.js-like colours (Standard view
  transform). Use it before exporting. More samples or larger sizes take
  proportionally longer; see "Time limits and long renders".
- For details, pass `focus=(x, y, z)` and `zoom=3`, and optionally custom
  `views=(("label", azimuth, elevation, orthographic), ...)`.
- Write renders outside the repo (scratchpad or `/tmp`). Send the user a sheet
  with SendUserFile when they should see progress.

## Inspiration images with FLUX

FLUX.2 [klein] 9B (Black Forest Labs, 4-bit quantized) generates reference
and inspiration images on the CPU, through stable-diffusion.cpp.

- The SessionStart hook runs `tools/flux/setup-flux.sh` in the background: it
  builds `/opt/flux/bin/sd-cli` and downloads about 11 GB of weights to
  `/opt/flux/models` (log: `/tmp/flux-setup.log`). In a fresh VM that takes
  several minutes; Blender is usable meanwhile.
- Generate with `tools/flux/flux.sh "prompt" /tmp/flux/name.png [sd-cli options]`,
  e.g. `-s 42` for a fixed seed (default: random), `-b 4` for several
  variants, or `-r reference.png` to edit an image. Run it with Bash
  `run_in_background`, then look at the result with Read and send it to the
  user with SendUserFile.
- It is slow on this CPU-only VM: a 512x512 image (the default) takes about
  11 minutes (4 steps at about 2.5 minutes each, plus 30 s text encoding and
  20 s decoding), and peaks at about 11 GB RAM. Larger sizes scale with the
  pixel count (1024x1024 would take well over half an hour). Blender stays
  usable meanwhile, but renders are slower while FLUX runs.
- Licence: FLUX Non-Commercial License. Fine for this free, open asset
  library; the generated images may be used freely. If the project ever turns
  commercial, switch to FLUX.2 [klein] 4B (Apache 2.0).
- Images are inspiration and reference for modelling in Blender; keep them
  outside the repo unless the user wants one committed.

## Asset library

The library is the point of this repo: GLB files that anyone can browse and
download, and that the NodePrism app will load by URL.

- Layout: `library/<id>/<id>.glb`, `library/<id>/preview.webp` and
  `library/<id>/meta.json`; Blender sources in `sources/<id>/<id>.blend`;
  library-wide fields in `library/library.json`. Asset ids are lowercase
  kebab-case.
- `meta.json` holds only `id`, `name`, `description`, `tags`, `author`.
  `tools/library/build_library_index.py` reads triangles, vertices, size and
  materials from the GLB (`tools/library/glb_stats.py`) and the date added
  from git, and writes the catalogue `index.json` when the site is built. The
  catalogue is not committed, so submissions never conflict over it.
- Publishing an asset ourselves:
  1. Build it in a scene that holds only this asset (the export also saves the
     whole scene as its source), and check it with "Visual checks".
  2. Export with `tools/blender/library_export.py` through `execute_blender_code`:
     ```python
     path = "/home/user/nodeprismvr-assets/tools/blender/library_export.py"
     ns = {}
     exec(compile(open(path).read(), path, "exec"), ns)
     result = ns["export_asset"]("crystal-cluster", ["CrystalCluster"], name="Crystal Cluster",
                                 description="...", tags=["crystal", "nature"])
     ```
     It writes the GLB, a 512 px WebP preview with transparent background, the
     meta.json and the .blend source. Look at the preview before going on.
  3. Validate: `node tools/library/validate_glb.mjs library/<id>/<id>.glb`
     (run `npm ci --prefix tools/library` once), and three.js
     `GLTFLoader.parseAsync` in Node.
  4. Optionally preview the site: `tools/library/build_site.sh`, then
     `python3 -m http.server -d _site` and load it in Chromium with Playwright.
  5. Commit and push to `main`; `.github/workflows/pages.yml` builds the
     catalogue and deploys the site.
- Community submissions are pull requests. `.github/workflows/check-submission.yml`
  runs `tools/library/check_submission.py` from the base branch against the
  pull request: only `library/<id>/` and `sources/<id>/` may change, files and
  meta.json must be complete, the glTF-Validator must pass, and budgets
  (100k triangles / 10 MB hard, 20k / 2 MB warning), self-containment and
  placement on y = 0 are checked. The admin looks at the asset in 3D on
  `site/review.html` (open submissions, loaded straight from the pull request)
  and approves by merging or rejects by closing on GitHub.
- Public URLs: gallery `https://r01b1.github.io/nodeprismvr-assets/`, review
  page `.../review.html`, catalogue `.../library/index.json`, files
  `.../library/<id>/<id>.glb`. Files are also on
  `https://raw.githubusercontent.com/r01b1/nodeprismvr-assets/main/library/...`
  (not the catalogue, which is built at deploy). All allow cross-origin loading.
- Apps may reference published ids and file names: do not rename or delete
  them without asking.
- Test site changes in Chromium and in WebKit (the Safari engine; the user
  browses with Safari), at desktop and phone sizes. Playwright's WebKit is not
  preinstalled: `PLAYWRIGHT_BROWSERS_PATH=<dir> npx playwright install webkit`,
  then `npx playwright install-deps webkit`.
- `site/` is static (no build step): `viewer.js` is the shared three.js viewer
  (three.js from jsDelivr, pinned), `app.js` the gallery, `review.js` the
  review page (public GitHub API, 60 anonymous requests per hour).

## Sessions and roles

Work is split between two cloud sessions:

- **Leitung** (supervisor): maintains the tooling (`tools/`, `site/`,
  `.claude/`, `.github/`, `.mcp.json`, docs), assigns asset tasks to the
  workshop and checks its results.
- **Werkstatt** (workshop): builds assets. It changes only `library/<id>/`
  and `sources/<id>/`, submits each asset as a pull request from a branch
  `claude/asset-<id>`, never merges itself, and reports tooling problems to
  the Leitung instead of fixing them.

The user approves assets by merging their pull requests after looking at them
on the review page.

## Public repository

- The repo is public, and the community may send assets as pull requests.
  Everything pushed stays in the history forever: never commit secrets,
  tokens or personal data, and check new binary files for embedded metadata
  (`render_views` strips Blender's render stamps).
- Review pull requests that touch `tools/`, `.claude/`, `.mcp.json` or
  `.github/` with care: those run in our sessions and in CI.
- Licences: assets in `library/` and `sources/` are CC0 1.0
  (`LICENSE-ASSETS`, `library/library.json`); the rest is MIT (`LICENSE`).

## Asset defaults for three.js

Adjust these when the app needs something else.

- Export glTF 2.0 binary (`.glb`) with `bpy.ops.export_scene.gltf(export_format="GLB")`,
  keeping the exporter's +Y up conversion. 1 Blender unit = 1 metre.
- Apply modifiers on export (`export_apply=True`). Leave clean transforms and
  put the origin at the pivot the app needs, e.g. the base of the object.
- Materials: Principled BSDF only, so they map to `MeshStandardMaterial` /
  `MeshPhysicalMaterial`. Name objects, meshes and materials meaningfully,
  because three.js sees those names.
- It is a VR app, so keep polygon and texture budgets small.
- After exporting, check that the file loads: run the Khronos glTF-Validator
  (npm `gltf-validator`) and three.js `GLTFLoader.parseAsync` in Node.
