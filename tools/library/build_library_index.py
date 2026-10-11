#!/usr/bin/env python3
"""
Build library/index.json, the catalogue of all assets, from library/library.json
(library-wide fields) and each library/<id>/meta.json.

Paths in the index are relative to the index file, so it works from GitHub Pages
and from raw.githubusercontent.com alike.

Usage: tools/library/build_library_index.py [--check]
  --check  exit 1 if library/index.json is not up to date (used by CI)
"""

import json
import os
import sys

LIBRARY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "library")
INDEX = os.path.join(LIBRARY, "index.json")


def build():
    with open(os.path.join(LIBRARY, "library.json")) as f:
        index = json.load(f)
    assets = []
    for asset_id in sorted(os.listdir(LIBRARY)):
        meta_path = os.path.join(LIBRARY, asset_id, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        if meta["id"] != asset_id:
            sys.exit("{}: id {!r} does not match its directory".format(meta_path, meta["id"]))
        for key in ("file", "preview"):
            path = os.path.join(LIBRARY, asset_id, meta[key])
            if not os.path.isfile(path):
                sys.exit("{}: {} {!r} is missing".format(meta_path, key, meta[key]))
        meta["file"] = "{}/{}".format(asset_id, meta["file"])
        meta["preview"] = "{}/{}".format(asset_id, meta["preview"])
        meta["bytes"] = os.path.getsize(os.path.join(LIBRARY, meta["file"]))
        meta.setdefault("license", index.get("license"))
        assets.append(meta)
    index["assets"] = assets
    return json.dumps(index, indent=2) + "\n"


def main():
    text = build()
    if "--check" in sys.argv[1:]:
        with open(INDEX) as f:
            if f.read() != text:
                sys.exit("library/index.json is out of date: run tools/library/build_library_index.py")
        print("library/index.json is up to date")
        return
    with open(INDEX, "w") as f:
        f.write(text)
    print("Wrote {} ({} assets)".format(INDEX, text.count('"id":')))


if __name__ == "__main__":
    main()
