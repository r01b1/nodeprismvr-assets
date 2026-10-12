"""
Read statistics from a glTF binary (.glb) file with the standard library only:
triangles, vertices, bounding box in glTF axes (+Y up, metres), materials,
extensions and external references.
"""

import json
import math
import struct

_GLB_MAGIC = 0x46546C67  # "glTF"
_CHUNK_JSON = 0x4E4F534A
_IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]  # column-major
_NORMALIZED_MAX = {5120: 127, 5121: 255, 5122: 32767, 5123: 65535}  # BYTE ... UNSIGNED_SHORT


def read_gltf_json(path):
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 20:
        raise ValueError("file too short for a GLB")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != _GLB_MAGIC or version != 2:
        raise ValueError("not a glTF 2.0 binary (.glb) file")
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != _CHUNK_JSON:
        raise ValueError("first GLB chunk is not JSON")
    return json.loads(data[20:20 + chunk_length])


def _mat_mul(a, b):
    # Column-major 4x4 multiply: a @ b.
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def _node_matrix(node):
    if "matrix" in node:
        return [float(v) for v in node["matrix"]]
    tx, ty, tz = node.get("translation", (0, 0, 0))
    qx, qy, qz, qw = node.get("rotation", (0, 0, 0, 1))
    sx, sy, sz = node.get("scale", (1, 1, 1))
    rot = [
        1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy + qz * qw), 2 * (qx * qz - qy * qw), 0,
        2 * (qx * qy - qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz + qx * qw), 0,
        2 * (qx * qz + qy * qw), 2 * (qy * qz - qx * qw), 1 - 2 * (qx * qx + qy * qy), 0,
        0, 0, 0, 1,
    ]
    scale = [sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, sz, 0, 0, 0, 0, 1]
    m = _mat_mul(rot, scale)
    m[12], m[13], m[14] = tx, ty, tz
    return m


def _accessor_bounds(accessor):
    """min and max of an accessor as floats (quantized meshes store normalized integers)."""
    lo, hi = accessor["min"], accessor["max"]
    if accessor.get("normalized"):
        # KHR_mesh_quantization: min/max hold the stored integers, which decode
        # to c / 127, c / 255, c / 32767 or c / 65535 (signed values clamp at -1).
        scale = _NORMALIZED_MAX[accessor["componentType"]]
        lo, hi = ([max(v / scale, -1.0) for v in values] for values in (lo, hi))
    return lo, hi


def _transform(m, p):
    x, y, z = p
    return tuple(m[r] * x + m[4 + r] * y + m[8 + r] * z + m[12 + r] for r in range(3))


def _primitive_triangles(gltf, prim):
    mode = prim.get("mode", 4)
    if "indices" in prim:
        count = gltf["accessors"][prim["indices"]]["count"]
    else:
        count = gltf["accessors"][prim["attributes"]["POSITION"]]["count"]
    if mode == 4:
        return count // 3
    if mode in (5, 6):
        return max(count - 2, 0)
    return 0  # points and lines


def glb_stats(path):
    gltf = read_gltf_json(path)
    triangles = vertices = 0
    materials = set()
    lo = [math.inf] * 3
    hi = [-math.inf] * 3

    def visit(index, parent):
        nonlocal triangles, vertices
        node = gltf["nodes"][index]
        world = _mat_mul(parent, _node_matrix(node))
        if "mesh" in node:
            for prim in gltf["meshes"][node["mesh"]]["primitives"]:
                position = gltf["accessors"][prim["attributes"]["POSITION"]]
                triangles += _primitive_triangles(gltf, prim)
                vertices += position["count"]
                if "material" in prim:
                    material = gltf["materials"][prim["material"]]
                    materials.add(material.get("name") or "material_{}".format(prim["material"]))
                pmin, pmax = _accessor_bounds(position)
                corners = [(x, y, z) for x in (pmin[0], pmax[0])
                           for y in (pmin[1], pmax[1]) for z in (pmin[2], pmax[2])]
                for corner in corners:
                    p = _transform(world, corner)
                    for i in range(3):
                        lo[i] = min(lo[i], p[i])
                        hi[i] = max(hi[i], p[i])
        for child in node.get("children", []):
            visit(child, world)

    scene = gltf.get("scenes", [{}])[gltf.get("scene", 0)]
    for root in scene.get("nodes", []):
        visit(root, _IDENTITY)
    if triangles == 0:
        raise ValueError("the scene contains no triangles")

    external = [item["uri"] for key in ("buffers", "images") for item in gltf.get(key, [])
                if "uri" in item and not item["uri"].startswith("data:")]
    return {
        "triangles": triangles,
        "vertices": vertices,
        "materials": sorted(materials),
        "bounds": {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi]},
        "dimensions": {axis: round(hi[i] - lo[i], 4) for i, axis in enumerate("xyz")},
        "extensions": sorted(gltf.get("extensionsUsed", [])),
        "external_uris": external,
        "generator": gltf.get("asset", {}).get("generator", ""),
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(glb_stats(sys.argv[1]), indent=2))
