<!-- Submitting an asset? Fill in the checklist. For other changes, delete it. -->

## Asset submission

- **Asset id:** `your-asset-id`
- **What it is:**

Checklist:

- [ ] `library/<id>/<id>.glb`: glTF 2.0 binary, +Y up, 1 unit = 1 metre, standing on y = 0, Principled BSDF materials, self-contained (no external files)
- [ ] `library/<id>/preview.webp`: 512 × 512, transparent background
- [ ] `library/<id>/meta.json` with `id`, `name`, `description`, `tags`, `author`
- [ ] `sources/<id>/<id>.blend`: the Blender source
- [ ] The pull request changes nothing outside `library/<id>/` and `sources/<id>/`
- [ ] I dedicate this asset to the public domain under CC0 1.0

An automatic check validates the files. The maintainer reviews the asset in 3D
on the review page and approves it by merging.
