# Render inspection views of objects in the running Blender, for visual checks.
#
# Runs inside Blender. Through the MCP server's `execute_blender_code`:
#
#     path = "/home/user/nodeprismvr-assets/scripts/render_views.py"
#     exec(compile(open(path).read(), path, "exec"))
#     result = render_views(["Crystal"], "/tmp/views/crystal", wireframe=True)
#
# Then look at result["sheet"] (all views in one labelled image) or at the
# single views in result["views"]. The scene is restored afterwards.

import math
import os
import time

import bpy
import numpy as np
from mathutils import Euler, Vector

# label, azimuth (0 = front, camera on -Y; 90 = right), elevation, orthographic
DEFAULT_VIEWS = (
    ("front", 0, 0, True),
    ("right", 90, 0, True),
    ("back", 180, 0, True),
    ("left", -90, 0, True),
    ("top", 0, 90, True),
    ("bottom", 0, -90, True),
    ("3/4 front-left", -40, 25, False),
    ("3/4 back-right", 140, 25, False),
)

_TEMP_PREFIX = "_inspect_"
_LENS_MM = 50.0
_SENSOR_MM = 36.0


def _view_rotation(azimuth, elevation):
    if elevation >= 89.9:
        return Euler((0.0, 0.0, 0.0))
    if elevation <= -89.9:
        return Euler((math.pi, 0.0, 0.0))
    az, el = math.radians(azimuth), math.radians(elevation)
    to_camera = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    return (-to_camera).to_track_quat("-Z", "Y").to_euler()


def _world_corners(objects, depsgraph):
    corners = []
    for ob in objects:
        ob_eval = ob.evaluated_get(depsgraph)
        corners.extend(ob_eval.matrix_world @ Vector(c) for c in ob_eval.bound_box)
    return corners


def _frame_camera(cam, corners, center, rotation, ortho, zoom, margin=1.1):
    rot = rotation.to_matrix()
    right, up, back = rot.col[0], rot.col[1], rot.col[2]
    rel = [c - center for c in corners]
    xs = [r.dot(right) for r in rel]
    ys = [r.dot(up) for r in rel]
    zs = [r.dot(back) for r in rel]
    radius = max(r.length for r in rel) or 1.0
    cam.rotation_euler = rotation
    cam.data.clip_start = radius * 0.01
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys), 1e-4) * margin / zoom
        mid = center + right * (max(xs) + min(xs)) / 2 + up * (max(ys) + min(ys)) / 2
        distance = radius * 3.0
    else:
        cam.data.type = "PERSP"
        cam.data.lens = _LENS_MM
        cam.data.sensor_width = _SENSOR_MM
        tan_half = (_SENSOR_MM / 2) / _LENS_MM
        distance = max(max(abs(x), abs(y)) / tan_half + z for x, y, z in zip(xs, ys, zs, strict=True)) * margin / zoom
        mid = center
    cam.data.clip_end = distance + radius * 4.0
    cam.location = mid + back * distance


def _wire_material():
    mat = bpy.data.materials.new(_TEMP_PREFIX + "wire")
    mat.diffuse_color = (1.0, 0.35, 0.0, 1.0)  # Used by the Workbench engine.
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 0.35, 0.0, 1.0)
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat


def _add_wire_overlays(objects, collection, depsgraph, thickness):
    mat = _wire_material()
    for ob in objects:
        if ob.type != "MESH":
            continue
        mesh = bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph))
        mesh.name = _TEMP_PREFIX + ob.name
        mesh.materials.clear()
        mesh.materials.append(mat)
        wire = bpy.data.objects.new(_TEMP_PREFIX + ob.name, mesh)
        wire.matrix_world = ob.matrix_world
        collection.objects.link(wire)
        mod = wire.modifiers.new("wire", "WIREFRAME")
        mod.thickness = thickness
        mod.use_replace = True
        mod.use_even_offset = True


def _contact_sheet(paths, labels, sheet_path, columns=4, gap=4):
    tiles = []
    for path in paths:
        img = bpy.data.images.load(path, check_existing=False)
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        tiles.append(px.reshape(h, w, 4))
        bpy.data.images.remove(img)
    h, w = tiles[0].shape[:2]
    columns = min(columns, len(tiles))
    rows = math.ceil(len(tiles) / columns)
    sheet_w, sheet_h = columns * w + (columns + 1) * gap, rows * h + (rows + 1) * gap
    sheet = np.full((sheet_h, sheet_w, 4), 0.08, dtype=np.float32)
    sheet[..., 3] = 1.0
    for i, tile in enumerate(tiles):
        row, col = divmod(i, columns)
        x = gap + col * (w + gap)
        y = gap + (rows - 1 - row) * (h + gap)  # Blender images start bottom-left.
        sheet[y:y + h, x:x + w] = tile
    img = bpy.data.images.new(_TEMP_PREFIX + "sheet", sheet_w, sheet_h, alpha=True)
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw = sheet_path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)

    # Labels in the top-left corner of each tile.
    import blf
    import imbuf
    buf = imbuf.load(sheet_path)
    font = 0
    with blf.bind_imbuf(font, buf, display_name="sRGB"):
        blf.size(font, max(12, h // 24))
        for i, label in enumerate(labels):
            row, col = divmod(i, columns)
            x = gap + col * (w + gap) + 8
            y = gap + (rows - 1 - row) * (h + gap) + h - 8 - max(12, h // 24)
            blf.color(font, 0.0, 0.0, 0.0, 1.0)
            blf.position(font, x + 1, y - 1, 0)
            blf.draw_buffer(font, label)
            blf.color(font, 1.0, 1.0, 1.0, 1.0)
            blf.position(font, x, y, 0)
            blf.draw_buffer(font, label)
    imbuf.write(buf, filepath=sheet_path)


def render_views(
    objects=None,
    out_dir="/tmp/blender-views",
    size=512,
    views=DEFAULT_VIEWS,
    wireframe=False,
    isolate=True,
    focus=None,
    zoom=1.0,
    engine="BLENDER_EEVEE",
    samples=4,
    transparent=False,
):
    """
    Render *objects* (names; default: all visible meshes) from several angles.

    *views* holds (label, azimuth, elevation, orthographic) tuples; azimuth 0
    looks at the front (camera on -Y), 90 at the right side. *wireframe*
    overlays the evaluated topology in orange. *focus* (a world-space point)
    and *zoom* (>1 moves closer) frame details instead of the whole object.
    *samples* sets the EEVEE render samples (4 is plenty for checks).
    *transparent* renders without background (alpha) instead of grey.
    Colours use the "Standard" view transform, like three.js without tone
    mapping. Returns the paths of the single views and of a contact sheet.
    """
    start = time.time()
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    if objects:
        targets = [bpy.data.objects[name] for name in objects]
    else:
        targets = [ob for ob in view_layer.objects if ob.type == "MESH" and ob.visible_get()]
    if not targets:
        raise ValueError("No objects to render")
    os.makedirs(out_dir, exist_ok=True)

    render = scene.render
    saved = {
        "camera": scene.camera,
        "world": scene.world,
        "engine": render.engine,
        "res": (render.resolution_x, render.resolution_y, render.resolution_percentage),
        "filepath": render.filepath,
        "transparent": render.film_transparent,
        "format": (render.image_settings.file_format, render.image_settings.color_mode),
        "view": (scene.view_settings.view_transform, scene.view_settings.look,
                 scene.view_settings.exposure, scene.view_settings.gamma),
        "hide_render": {ob.name: ob.hide_render for ob in scene.objects},
        "eevee_samples": scene.eevee.taa_render_samples,
        # Metadata Blender writes into images (file path, date, camera, ...).
        "stamp": {name: getattr(render, name) for name in dir(render) if name.startswith("use_stamp")},
    }

    temp = bpy.data.collections.new(_TEMP_PREFIX + "views")
    scene.collection.children.link(temp)
    paths = []
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        corners = _world_corners(targets, depsgraph)
        bb_min = Vector(tuple(min(c[i] for c in corners) for i in range(3)))
        bb_max = Vector(tuple(max(c[i] for c in corners) for i in range(3)))
        center = Vector(focus) if focus else (bb_min + bb_max) / 2
        size_vec = bb_max - bb_min

        if isolate:
            target_names = {ob.name for ob in targets}
            for ob in scene.objects:
                if ob.name not in target_names:
                    ob.hide_render = True
        if wireframe:
            _add_wire_overlays(targets, temp, depsgraph, thickness=max(size_vec.length * 0.003, 1e-4))

        cam = bpy.data.objects.new(_TEMP_PREFIX + "camera", bpy.data.cameras.new(_TEMP_PREFIX + "camera"))
        temp.objects.link(cam)
        # Sun lights parented to the camera light every view the same way.
        for name, strength, rot in (("key", 2.5, (-35, -35, 0)), ("fill", 0.8, (10, 50, 0)), ("rim", 1.5, (220, 0, 0))):
            light = bpy.data.objects.new(_TEMP_PREFIX + name, bpy.data.lights.new(_TEMP_PREFIX + name, "SUN"))
            light.data.energy = strength
            light.parent = cam
            light.rotation_euler = Euler([math.radians(a) for a in rot])
            temp.objects.link(light)

        world = bpy.data.worlds.new(_TEMP_PREFIX + "world")
        if world.node_tree is None:
            world.use_nodes = True
        world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.22, 0.22, 0.24, 1.0)
        scene.world = world

        scene.camera = cam
        render.engine = engine
        render.resolution_x = render.resolution_y = size
        render.resolution_percentage = 100
        render.film_transparent = transparent
        for name in saved["stamp"]:
            setattr(render, name, False)
        render.image_settings.file_format = "PNG"
        render.image_settings.color_mode = "RGBA"
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0
        scene.eevee.taa_render_samples = samples

        view_corners = corners
        if focus:
            # Frame a cube around the focus point instead of the whole object.
            half = size_vec.length / 2
            view_corners = [center + Vector((x, y, z)) * half for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]

        for label, azimuth, elevation, ortho in views:
            _frame_camera(cam, view_corners, center, _view_rotation(azimuth, elevation), ortho, zoom)
            path = os.path.join(out_dir, label.replace("/", "-").replace(" ", "_") + ".png")
            render.filepath = path
            bpy.ops.render.render(write_still=True)
            paths.append(path)

        sheet = os.path.join(out_dir, "sheet.png")
        _contact_sheet(paths, [v[0] for v in views], sheet)
    finally:
        scene.camera = saved["camera"]
        scene.world = saved["world"]
        render.engine = saved["engine"]
        render.resolution_x, render.resolution_y, render.resolution_percentage = saved["res"]
        render.filepath = saved["filepath"]
        render.film_transparent = saved["transparent"]
        render.image_settings.file_format, render.image_settings.color_mode = saved["format"]
        (scene.view_settings.view_transform, scene.view_settings.look,
         scene.view_settings.exposure, scene.view_settings.gamma) = saved["view"]
        scene.eevee.taa_render_samples = saved["eevee_samples"]
        for name, value in saved["stamp"].items():
            setattr(render, name, value)
        for name, hidden in saved["hide_render"].items():
            if name in scene.objects:
                scene.objects[name].hide_render = hidden
        for ob in list(temp.objects):
            data = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Camera):
                    bpy.data.cameras.remove(data)
                elif isinstance(data, bpy.types.Light):
                    bpy.data.lights.remove(data)
        bpy.data.collections.remove(temp)
        for mat in [m for m in bpy.data.materials if m.name.startswith(_TEMP_PREFIX) and m.users == 0]:
            bpy.data.materials.remove(mat)
        for world in [w for w in bpy.data.worlds if w.name.startswith(_TEMP_PREFIX) and w.users == 0]:
            bpy.data.worlds.remove(world)

    return {
        "sheet": sheet,
        "views": paths,
        "objects": [ob.name for ob in targets],
        "bbox_min": list(bb_min),
        "bbox_size": list(size_vec),
        "seconds": round(time.time() - start, 1),
    }
