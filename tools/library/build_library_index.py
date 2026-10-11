#!/usr/bin/env python3
"""
Build the library catalogue (index.json) from library/library.json, each
library/<id>/meta.json and the asset files themselves.

meta.json holds only what a person writes (name, description, tags, author);
file sizes, triangles, vertices, dimensions and materials are read from the
GLB, and the date an asset was added comes from git. The catalogue is built
when the site is deployed and not committed, so submissions do not conflict.

Paths in the catalogue are relative to it (library/), so it works from GitHub
Pages and from a local preview alike.

Usage: tools/library/build_library_index.py [--out PATH]   (default: library/index.json)
"""

import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glb_stats import glb_stats  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIBRARY = os.path.join(REPO, "library")
ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
META_FIELDS = {"id", "name", "description", "tags", "author"}


def meta_problems(asset_id, meta):
    """Return the problems with a meta.json, as a list of messages."""
    problems = []
    if not ID_PATTERN.match(asset_id):
        problems.append("id {!r} must be lowercase kebab-case, e.g. 'crystal-cluster'".format(asset_id))
    if meta.get("id") != asset_id:
        problems.append("meta.json id {!r} does not match the folder name {!r}".format(meta.get("id"), asset_id))
    for key in ("name", "description", "author"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            problems.append("meta.json needs a non-empty {!r}".format(key))
    tags = meta.get("tags")
    if not isinstance(tags, list) or not tags or not all(isinstance(t, str) and ID_PATTERN.match(t) for t in tags):
        problems.append("meta.json needs 'tags': a list of lowercase kebab-case words")
    unknown = set(meta) - META_FIELDS
    if unknown:
        problems.append("meta.json has unknown fields {}; allowed are {}".format(sorted(unknown), sorted(META_FIELDS)))
    return problems


def date_added(asset_id):
    """Date of the first commit that added the asset's GLB, else today."""
    path = "library/{0}/{0}.glb".format(asset_id)
    try:
        dates = subprocess.run(["git", "-C", REPO, "log", "--diff-filter=A", "--format=%as", "--", path],
                               capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        dates = []
    return dates[-1] if dates else datetime.date.today().isoformat()


def asset_entry(asset_id, license_id):
    asset_dir = os.path.join(LIBRARY, asset_id)
    with open(os.path.join(asset_dir, "meta.json")) as f:
        meta = json.load(f)
    problems = meta_problems(asset_id, meta)
    glb = os.path.join(asset_dir, asset_id + ".glb")
    for path in (glb, os.path.join(asset_dir, "preview.webp")):
        if not os.path.isfile(path):
            problems.append("{} is missing".format(os.path.relpath(path, REPO)))
    if problems:
        raise ValueError("; ".join(problems))
    stats = glb_stats(glb)
    source = "sources/{0}/{0}.blend".format(asset_id)
    return {
        "id": asset_id,
        "name": meta["name"].strip(),
        "description": meta["description"].strip(),
        "tags": sorted(set(meta["tags"])),
        "author": meta["author"].strip(),
        "license": license_id,
        "added": date_added(asset_id),
        "file": "{0}/{0}.glb".format(asset_id),
        "preview": "{}/preview.webp".format(asset_id),
        "source": source if os.path.isfile(os.path.join(REPO, source)) else None,
        "bytes": os.path.getsize(glb),
        "triangles": stats["triangles"],
        "vertices": stats["vertices"],
        "materials": stats["materials"],
        "dimensions": stats["dimensions"],
        "extensions": stats["extensions"],
    }


def build():
    with open(os.path.join(LIBRARY, "library.json")) as f:
        index = json.load(f)
    assets, errors = [], []
    for asset_id in sorted(os.listdir(LIBRARY)):
        if not os.path.isdir(os.path.join(LIBRARY, asset_id)):
            continue
        try:
            assets.append(asset_entry(asset_id, index.get("license")))
        except (OSError, ValueError, KeyError) as ex:
            errors.append("library/{}: {}".format(asset_id, ex))
    if errors:
        sys.exit("\n".join(errors))
    index["assets"] = assets
    return index


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(LIBRARY, "index.json")
    index = build()
    with open(out, "w") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    print("Wrote {} ({} assets)".format(out, len(index["assets"])))


if __name__ == "__main__":
    main()
