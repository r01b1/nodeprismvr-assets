# Export a finished asset into the library, inside the running Blender.
# Through the MCP server's `execute_blender_code`:
#
#     path = "/home/user/nodeprismvr-assets/scripts/library_export.py"
#     exec(compile(open(path).read(), path, "exec"))
#     result = export_asset("crystal-cluster", ["CrystalCluster"], name="Crystal Cluster",
#                           description="...", tags=["crystal", "nature"])
#
# Writes library/<id>/<id>.glb, library/<id>/preview.webp and
# library/<id>/meta.json, and saves the scene as sources/<id>/<id>.blend.
# Afterwards run scripts/build_library_index.py to update library/index.json.

import datetime
import inspect
import json
import os
import re
import tempfile

import bpy
from mathutils import Vector

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(inspect.currentframe().f_code.co_filename)))
_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _with_children(objects):
    result = []
    for ob in objects:
        result.append(ob)
        result.extend(ob.children_recursive)
    return list(dict.fromkeys(result))


def _stats(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    triangles = vertices = 0
    materials = set()
    corners = []
    for ob in objects:
        ob_eval = ob.evaluated_get(depsgraph)
        if ob.type == "MESH":
            mesh = ob_eval.to_mesh()
            mesh.calc_loop_triangles()
            triangles += len(mesh.loop_triangles)
            vertices += len(mesh.vertices)
            materials.update(m.name for m in mesh.materials if m)
            corners.extend(ob_eval.matrix_world @ v.co for v in mesh.vertices)
            ob_eval.to_mesh_clear()
    if not corners:
        raise ValueError("No mesh geometry to export")
    lo = Vector(tuple(min(c[i] for c in corners) for i in range(3)))
    hi = Vector(tuple(max(c[i] for c in corners) for i in range(3)))
    size = hi - lo
    # Blender is Z-up, glTF/three.js is Y-up (the exporter maps Z to Y, Y to -Z).
    return {
        "triangles": triangles,
        "vertices": vertices,
        "materials": sorted(materials),
        "dimensions": {"x": round(size.x, 4), "y": round(size.z, 4), "z": round(size.y, 4)},
    }


def _render_preview(objects, path):
    rv_path = os.path.join(_REPO, "scripts", "render_views.py")
    namespace = {}
    exec(compile(open(rv_path).read(), rv_path, "exec"), namespace)
    with tempfile.TemporaryDirectory() as tmp:
        result = namespace["render_views"](
            [ob.name for ob in objects if ob.type == "MESH"], tmp, size=512, samples=16,
            transparent=True, zoom=1.3, views=(("preview", -35, 20, False),))
        img = bpy.data.images.load(result["views"][0], check_existing=False)
        try:
            img.file_format = "WEBP"
            img.save(filepath=path, quality=90)
        finally:
            bpy.data.images.remove(img)


def export_asset(asset_id, objects, name, description="", tags=(), author="NodePrism"):
    """
    Export *objects* (names; children are included) as library asset *asset_id*
    (lowercase kebab-case). Returns the paths written and the asset's stats.
    """
    if not _ID_PATTERN.match(asset_id):
        raise ValueError("asset_id must be lowercase kebab-case, e.g. 'crystal-cluster'")
    obs = _with_children([bpy.data.objects[n] for n in objects])
    asset_dir = os.path.join(_REPO, "library", asset_id)
    source_dir = os.path.join(_REPO, "sources", asset_id)
    os.makedirs(asset_dir, exist_ok=True)
    os.makedirs(source_dir, exist_ok=True)
    glb = os.path.join(asset_dir, asset_id + ".glb")
    preview = os.path.join(asset_dir, "preview.webp")
    blend = os.path.join(source_dir, asset_id + ".blend")

    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for ob in obs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True)

    stats = _stats(obs)
    _render_preview(obs, preview)
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True, compress=True)

    meta = {
        "id": asset_id,
        "name": name,
        "description": description,
        "tags": sorted(set(tags)),
        "author": author,
        "created": datetime.date.today().isoformat(),
        "file": asset_id + ".glb",
        "preview": "preview.webp",
        "source": "sources/{0}/{0}.blend".format(asset_id),
        "generator": "Blender " + bpy.app.version_string,
        **stats,
    }
    meta_path = os.path.join(asset_dir, "meta.json")
    if os.path.exists(meta_path):
        # Keep the original creation date when re-exporting.
        with open(meta_path) as f:
            meta["created"] = json.load(f).get("created", meta["created"])
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    return {"glb": glb, "preview": preview, "meta": meta_path, "blend": blend,
            "glb_bytes": os.path.getsize(glb), **stats}
