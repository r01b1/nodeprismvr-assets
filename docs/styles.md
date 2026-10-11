# Style lines

Assets of one style line share materials, motifs and budgets, so they look
like a set. Asset ids start with the line's prefix.

## Neon Grid

Retro vector look in the spirit of Tron and Asteroids: dark glossy bodies
outlined by glowing cyan lines. Approved with `neon-grid-table`.

- **Ids and tags:** `neon-grid-<thing>`; tags `neon-grid`, `retro`,
  `low-poly` plus the kind (`furniture`, `seating`, ...).
- **Materials** (Principled BSDF, no textures, same names in every asset):

  | Material | Base colour (linear) | Metallic | Roughness | Emission |
  | --- | --- | --- | --- | --- |
  | `NeonGrid_Body` | 0.0033, 0.0060, 0.0144 | 0.3 | 0.35 | none |
  | `NeonGrid_Glow` | 0, 0.784, 1 | 0 | 0.4 | 0, 0.784, 1 at strength 3 (`KHR_materials_emissive_strength`) |

  A third material `NeonGrid_Accent` is allowed when a piece needs it.
- **Glow lines** are 45° chamfers along the silhouette edges (offset 1.2 cm,
  so about 1.7 cm wide) carrying `NeonGrid_Glow`. They cost no extra
  triangles. Undersides stay body-coloured.
- **Line motif:** raised strips 1.5 cm wide and 4 mm high, one per piece
  (crossbar on a chair back, line around a table apron, underline on a
  couch plinth).
- **Corner motif:** 45° corner chamfers in plan and elevation (seat front,
  table top, backrest top, armrests).
- **Geometry:** one object per asset, transforms applied, origin at the
  bottom centre, front towards Blender's -Y (+Z in three.js).
- **Budgets:** chair up to 300 triangles, table 500, couch 800; other pieces
  in proportion. No compression needed (the GLBs are 15 to 25 KB).
- **In the app:** the glow reads best with a bloom pass (e.g. three.js
  `UnrealBloomPass`); without one, the lines are flat cyan.

## Photoreal (in testing)

Photorealistic look without texture maps, each GLB under 100 KB. First test
asset: `photoreal-meteorite`.

- **Means:** detail in the geometry; vertex colours (`COLOR_0`) for colour
  variation and baked ambient occlusion; up to three materials, because
  roughness and metallic exist only per material; no textures, no emission.
- **Compression** with `tools/gltf/optimize_glb.mjs`: about 6,500 triangles
  fit in 100 KB with `--mode quantize` (no decoder in the app), about 17,000
  with `--mode meshopt` (apps need three.js's `MeshoptDecoder`). Which one the
  line uses is decided after the test.
- **Judging realism:** the look depends heavily on the app's lighting
  (environment map) and tone mapping. The site's viewer lights with a bright
  studio environment and no tone mapping, which makes dark materials look
  lighter than in a realistic scene.
