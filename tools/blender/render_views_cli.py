# Command-line entry for render_views.py, for renders that take longer than
# an MCP tool call may run. Renders a saved .blend in its own Blender process:
#
#     blender --background scene.blend --python tools/blender/render_views_cli.py -- \
#         --out /tmp/views/crystal [--objects Crystal] [--engine BLENDER_EEVEE] \
#         [--size 1024] [--samples 64] [--wireframe] [--focus X Y Z] [--zoom 3]
#
# Prints the result of render_views() as JSON on the last line.

import argparse
import json
import os
import sys

_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_views.py")
exec(compile(open(_path).read(), _path, "exec"))

parser = argparse.ArgumentParser(prog="render_views_cli.py")
parser.add_argument("--out", required=True, help="Output directory.")
parser.add_argument("--objects", nargs="*", help="Object names (default: all visible meshes).")
parser.add_argument("--engine", default="BLENDER_EEVEE")
parser.add_argument("--size", type=int, default=512)
parser.add_argument("--samples", type=int, default=4)
parser.add_argument("--wireframe", action="store_true")
parser.add_argument("--focus", type=float, nargs=3)
parser.add_argument("--zoom", type=float, default=1.0)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

result = render_views(  # noqa: F821 (defined by render_views.py)
    args.objects,
    args.out,
    size=args.size,
    wireframe=args.wireframe,
    focus=args.focus,
    zoom=args.zoom,
    engine=args.engine,
    samples=args.samples,
)
print(json.dumps(result))
