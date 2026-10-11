# nodeprismvr-assets

3D assets for the nodeprismvr three.js app, modelled in Blender through the
official Blender Lab MCP server (https://www.blender.org/lab/mcp-server/).

## Blender and MCP in this repo

- In cloud sessions, the SessionStart hook (`.claude/hooks/session-start.sh`)
  installs Blender 5.2.2 LTS and the MCP add-on 1.0.3 (`scripts/setup-blender.sh`),
  then starts a headless Blender that serves the add-on's socket on
  127.0.0.1:9876 (`scripts/blender-mcp-server.sh`).
- `.mcp.json` registers the `blender` MCP server (official, pinned to the v1.0.3
  commit). Its tools appear as `mcp__blender__*`.
- If a tool reports it cannot connect to Blender, run
  `scripts/blender-mcp-server.sh start`. `status` checks it, the log is
  `/tmp/blender-mcp/blender.log`.
- Blender has no GUI here: the screenshot and `jump_to_*` tools do not work.
  Model with `execute_blender_code`; inspect with the `get_*` summary tools
  and look at the asset with renders (see "Visual checks").
- EEVEE, Cycles (CPU) and Workbench all render headless (Mesa llvmpipe).
  `render_thumbnail_to_path` and `render_viewport_to_path` write into
  Blender's temp dir, so use the `filepath` they return. To render to a chosen
  path, set `scene.render.filepath` and call `bpy.ops.render.render(write_still=True)`.
- The headless scene only lives in memory. Save a `.blend` when the work
  should survive a restart.

## Visual checks

Look at the asset regularly while modelling, not only at the end.
`scripts/render_views.py` renders an object from several angles into one
labelled contact sheet, then restores the scene:

```python
path = "/home/user/nodeprismvr-assets/scripts/render_views.py"
exec(compile(open(path).read(), path, "exec"))
result = render_views(["Crystal"], "/tmp/views/crystal", wireframe=True,
                      engine="BLENDER_WORKBENCH")
```

Then open `result["sheet"]` with the Read tool.

- Default views: front, right, back, left, top, bottom (orthographic, for
  proportions) and two perspective 3/4 views.
- `engine="BLENDER_WORKBENCH"` with `wireframe=True` takes about 2 s for all
  views. Use it after each modelling step to check shape and topology.
- The default EEVEE engine takes about a minute and shows materials with
  three.js-like colours (Standard view transform). Use it before exporting.
- For details, pass `focus=(x, y, z)` and `zoom=3`, and optionally custom
  `views=(("label", azimuth, elevation, orthographic), ...)`.
- Write renders outside the repo (scratchpad or `/tmp`). Send the user a sheet
  with SendUserFile when they should see progress.

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
