#!/usr/bin/env python3
"""
Build the library catalogue (index.json) from library/library.json, the
metadata in library/metadata/<id>/ and the asset files themselves.

Layout: library/objects/<category>/<id>.glb, where each category folder (e.g.
planets) holds only .glb files, so apps can treat folder names as categories;
each asset's meta.json and preview.webp are in library/metadata/<id>/.

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
OBJECTS_DIR = "objects"    # library/objects/<category>/<id>.glb
METADATA_DIR = "metadata"  # library/metadata/<id>/: meta.json, preview.webp


def scan_library(library):
    """
    Map each asset id to its category (the folder in library/objects/ holding
    <id>.glb) and list the layout problems: files outside category folders,
    other files than .glb in them, ids in two categories, GLBs without
    metadata and metadata without a GLB.
    """
    categories, problems = {}, []
    for name in sorted(set(os.listdir(library)) - {OBJECTS_DIR, METADATA_DIR, "library.json", "index.json"}):
        problems.append("library/{}: the library holds only {}/, {}/ and library.json".format(
            name, OBJECTS_DIR, METADATA_DIR))
    objects = os.path.join(library, OBJECTS_DIR)
    for name in sorted(os.listdir(objects)) if os.path.isdir(objects) else []:
        path = os.path.join(objects, name)
        if not os.path.isdir(path):
            problems.append("library/{}/{}: files go into a category folder, library/{}/<category>/".format(
                OBJECTS_DIR, name, OBJECTS_DIR))
            continue
        if not ID_PATTERN.match(name):
            problems.append("category folder library/{}/{} must be lowercase kebab-case".format(OBJECTS_DIR, name))
        for entry in sorted(os.listdir(path)):
            asset_id, ext = os.path.splitext(entry)
            if ext != ".glb" or not os.path.isfile(os.path.join(path, entry)):
                problems.append("library/{}/{}/{}: category folders hold only .glb files "
                                "(metadata goes to library/{}/<id>/)".format(OBJECTS_DIR, name, entry, METADATA_DIR))
            elif asset_id in categories:
                problems.append("asset {!r} is in two categories, {} and {}".format(
                    asset_id, categories[asset_id], name))
            else:
                categories[asset_id] = name
    metadata = os.path.join(library, METADATA_DIR)
    described = set(os.listdir(metadata)) if os.path.isdir(metadata) else set()
    for asset_id in sorted(described - set(categories)):
        problems.append("library/{}/{} has no GLB in a category folder".format(METADATA_DIR, asset_id))
    for asset_id in sorted(set(categories) - described):
        problems.append("library/{}/{}/{}.glb has no library/{}/{}/".format(
            OBJECTS_DIR, categories[asset_id], asset_id, METADATA_DIR, asset_id))
    return categories, problems


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


def date_added(path):
    """Date of the first commit that added the file at *path* (following moves), else today."""
    try:
        dates = subprocess.run(["git", "-C", REPO, "log", "--follow", "--diff-filter=A", "--format=%as", "--", path],
                               capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        dates = []
    return dates[-1] if dates else datetime.date.today().isoformat()


def asset_entry(asset_id, category, license_id):
    meta_dir = os.path.join(LIBRARY, METADATA_DIR, asset_id)
    with open(os.path.join(meta_dir, "meta.json")) as f:
        meta = json.load(f)
    problems = meta_problems(asset_id, meta)
    file = "{}/{}/{}.glb".format(OBJECTS_DIR, category, asset_id)
    preview = "{}/{}/preview.webp".format(METADATA_DIR, asset_id)
    if not os.path.isfile(os.path.join(LIBRARY, preview)):
        problems.append("library/{} is missing".format(preview))
    if problems:
        raise ValueError("; ".join(problems))
    glb = os.path.join(LIBRARY, file)
    stats = glb_stats(glb)
    source = "sources/{0}/{0}.blend".format(asset_id)
    return {
        "id": asset_id,
        "category": category,
        "name": meta["name"].strip(),
        "description": meta["description"].strip(),
        "tags": sorted(set(meta["tags"])),
        "author": meta["author"].strip(),
        "license": license_id,
        "added": date_added("library/" + file),
        "file": file,
        "preview": preview,
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
    categories, errors = scan_library(LIBRARY)
    assets = []
    for asset_id, category in sorted(categories.items()):
        try:
            assets.append(asset_entry(asset_id, category, index.get("license")))
        except (OSError, ValueError, KeyError) as ex:
            errors.append("{}: {}".format(asset_id, ex))
    if errors:
        sys.exit("\n".join(errors))
    index["categories"] = sorted(set(categories.values()))
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
