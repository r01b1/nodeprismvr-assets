#!/usr/bin/env python3
"""
Check an asset submission (a pull request) before an admin reviews it.

Runs in CI with the tools from the base branch (trusted) against a checkout of
the pull request (untrusted data). Writes a Markdown report to stdout and to
$GITHUB_STEP_SUMMARY, and exits 1 when a submission has errors.

Usage: check_submission.py --repo PR_CHECKOUT --base BASE_SHA --head HEAD_SHA
                           [--pr N --head-repo OWNER/REPO --review-url URL]
"""

import argparse
import json
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_library_index import ID_PATTERN, METADATA_DIR, OBJECTS_DIR, meta_problems, scan_library  # noqa: E402
from glb_stats import glb_stats  # noqa: E402

# Budgets for a VR app; warnings ask the reviewer to look closer.
MAX_TRIANGLES, WARN_TRIANGLES = 100_000, 20_000
MAX_BYTES, WARN_BYTES = 10 * 1024 * 1024, 2 * 1024 * 1024
# Extensions an app can only load with an extra decoder, and that decoder in three.js.
DECODER_EXTENSIONS = {
    "EXT_meshopt_compression": "MeshoptDecoder (GLTFLoader.setMeshoptDecoder)",
    "KHR_draco_mesh_compression": "DRACOLoader (GLTFLoader.setDRACOLoader)",
    "KHR_texture_basisu": "KTX2Loader (GLTFLoader.setKTX2Loader)",
}
METADATA_FILES = {"meta.json", "preview.webp"}
# Paths a submission may change: the GLB in a category folder, its metadata, its source.
GLB_PATH = re.compile(r"^library/" + OBJECTS_DIR + r"/([^/]+)/([^/]+)\.glb$")
METADATA_PATH = re.compile(r"^library/" + METADATA_DIR + r"/([^/]+)/[^/]+$")
SOURCE_PATH = re.compile(r"^sources/([^/]+)/[^/]+$")


def asset_of(path):
    """The asset id a changed path belongs to, or None if a submission may not change it."""
    for pattern in (METADATA_PATH, SOURCE_PATH):
        m = pattern.match(path)
        if m:
            return m.group(1)
    m = GLB_PATH.match(path)
    return m.group(2) if m else None


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def webp_size(path):
    with open(path, "rb") as f:
        data = f.read(64)
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP image")
    chunk = data[12:16]
    if chunk == b"VP8X":
        w = int.from_bytes(data[24:27], "little") + 1
        h = int.from_bytes(data[27:30], "little") + 1
    elif chunk == b"VP8 ":
        w, h = (v & 0x3FFF for v in struct.unpack_from("<HH", data, 26))
    elif chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        w, h = (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    else:
        raise ValueError("unknown WebP format")
    return w, h


def validate_glb(path):
    node = subprocess.run(["node", os.path.join(HERE, "validate_glb.mjs"), path],
                          capture_output=True, text=True, timeout=120)
    if node.returncode != 0:
        raise ValueError("glTF-Validator failed: " + node.stderr.strip()[-300:])
    return json.loads(node.stdout)


def check_asset(repo, asset_id, category):
    """Return (errors, warnings, stats) for the asset in library/objects/<category>/ and library/metadata/."""
    errors, warnings, stats = [], [], {}
    if not ID_PATTERN.match(asset_id):
        errors.append("`{}` is not a valid asset id (lowercase kebab-case).".format(asset_id))
        return errors, warnings, stats
    meta_dir = os.path.join(repo, "library", METADATA_DIR, asset_id)
    present = set(os.listdir(meta_dir)) if os.path.isdir(meta_dir) else set()
    for name in sorted(METADATA_FILES - present):
        errors.append("`library/{}/{}/{}` is missing.".format(METADATA_DIR, asset_id, name))
    for name in sorted(present - METADATA_FILES):
        errors.append("`library/{}/{}/{}` is not expected; the metadata folder holds only {}.".format(
            METADATA_DIR, asset_id, name, ", ".join(sorted(METADATA_FILES))))
    if not os.path.isfile(os.path.join(repo, "sources", asset_id, asset_id + ".blend")):
        warnings.append("No Blender source `sources/{0}/{0}.blend`.".format(asset_id))

    if "meta.json" in present:
        try:
            with open(os.path.join(meta_dir, "meta.json")) as f:
                meta = json.load(f)
            stats["name"] = meta.get("name", "")
            errors.extend(meta_problems(asset_id, meta))
        except (ValueError, OSError) as ex:
            errors.append("meta.json is not valid JSON: {}".format(ex))

    if "preview.webp" in present:
        try:
            size = webp_size(os.path.join(meta_dir, "preview.webp"))
            if size != (512, 512):
                warnings.append("preview.webp is {}x{}; previews are 512x512.".format(*size))
        except (ValueError, OSError) as ex:
            errors.append("preview.webp: {}".format(ex))

    glb = os.path.join(repo, "library", OBJECTS_DIR, category, asset_id + ".glb")
    if os.path.isfile(glb):
        stats["bytes"] = os.path.getsize(glb)
        try:
            stats.update(glb_stats(glb))
        except (ValueError, KeyError, IndexError) as ex:
            errors.append("The GLB could not be read: {}".format(ex))
            return errors, warnings, stats
        report = validate_glb(glb)
        for issue in report["messages"]:
            line = "glTF-Validator {}: {} ({})".format(issue["code"], issue["message"], issue.get("pointer") or "")
            (errors if issue["severity"] == 0 else warnings if issue["severity"] == 1 else []).append(line)
        if stats["external_uris"]:
            errors.append("The GLB references external files ({}); it must be self-contained.".format(
                ", ".join(stats["external_uris"])))
        if stats["triangles"] > MAX_TRIANGLES:
            errors.append("{:,} triangles; the limit is {:,}.".format(stats["triangles"], MAX_TRIANGLES))
        elif stats["triangles"] > WARN_TRIANGLES:
            warnings.append("{:,} triangles is a lot for VR (over {:,}).".format(stats["triangles"], WARN_TRIANGLES))
        if stats["bytes"] > MAX_BYTES:
            errors.append("The GLB is {:.1f} MB; the limit is {:.0f} MB.".format(
                stats["bytes"] / 2**20, MAX_BYTES / 2**20))
        elif stats["bytes"] > WARN_BYTES:
            warnings.append("The GLB is {:.1f} MB, large for VR.".format(stats["bytes"] / 2**20))
        for ext in sorted(DECODER_EXTENSIONS.keys() & set(stats["extensions"])):
            warnings.append("Uses {}: apps need three.js's {} to load it.".format(ext, DECODER_EXTENSIONS[ext]))
        low_y = stats["bounds"]["min"][1]
        if abs(low_y) > 0.01:
            warnings.append("The lowest point is at y = {:.3f} m; assets should stand on y = 0.".format(low_y))
        biggest = max(stats["dimensions"].values())
        if biggest > 50 or biggest < 0.02:
            warnings.append("The asset is {:.3f} m at its largest; check the scale (1 unit = 1 m).".format(biggest))
    return errors, warnings, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--pr")
    parser.add_argument("--head-repo")
    parser.add_argument("--review-url")
    args = parser.parse_args()

    if git(args.repo, "rev-parse", "HEAD").strip() != git(args.repo, "rev-parse", args.head).strip():
        sys.exit("The checkout in {} is not at --head {}".format(args.repo, args.head))
    changes = [line.split("\t") for line in git(args.repo, "diff", "--name-status", "--no-renames",
                                                    "{}...{}".format(args.base, args.head)).splitlines()]
    paths = [c[-1] for c in changes]
    deleted = {c[-1] for c in changes if c[0] == "D"}
    outside = [p for p in paths if asset_of(p) is None]
    asset_ids = sorted({asset_of(p) for p in paths} - {None})
    categories, layout_problems = scan_library(os.path.join(args.repo, "library"))
    base_categories = {os.path.basename(p) for p in git(args.repo, "ls-tree", "-d", "--name-only",
                                                         args.base, "library/{}/".format(OBJECTS_DIR)).split()}

    lines = ["## Asset submission check", ""]
    failed = False
    if outside:
        failed = True
        lines += ["❌ An asset submission may only change `library/objects/<category>/<id>.glb`, "
                  "`library/metadata/<id>/` and `sources/<id>/`. Category folders hold only .glb "
                  "files; meta.json and preview.webp go to `library/metadata/<id>/`. Send changes "
                  "to other files in a separate pull request:", ""]
        lines += ["- `{}`".format(p) for p in outside] + [""]
    if layout_problems:
        failed = True
        lines += ["❌ Library layout:", ""] + ["- " + p for p in layout_problems] + [""]

    for asset_id in asset_ids:
        if asset_id not in categories:
            if all(p in deleted for p in paths if asset_of(p) == asset_id):
                lines += ["### `{}`".format(asset_id), "",
                          "⚠️ This pull request removes the asset. Apps may still reference it.", ""]
            elif not os.path.isdir(os.path.join(args.repo, "library", METADATA_DIR, asset_id)):
                failed = True
                lines += ["### ❌ `{}`".format(asset_id), "",
                          "- ❌ No `library/objects/<category>/{0}.glb` and no `library/metadata/{0}/`.".format(asset_id), ""]
            continue  # Metadata without a GLB is reported as a layout problem.
        category = categories[asset_id]
        errors, warnings, stats = check_asset(args.repo, asset_id, category)
        if category not in base_categories:
            warnings.append("Adds the new category `{}`; apps show category folders by name.".format(category))
        failed = failed or bool(errors)
        lines += ["### {} `{}` in `{}`".format("❌" if errors else "✅", asset_id, category), ""]
        if args.head_repo:
            raw = "https://raw.githubusercontent.com/{}/{}/library/{}/{}/".format(
                args.head_repo, args.head, METADATA_DIR, asset_id)
            lines += ['<img src="{}preview.webp" width="256" alt="preview">'.format(raw), ""]
        if args.review_url and args.pr:
            lines += ["**[Look at it in 3D]({}#pr={}&id={})**".format(args.review_url, args.pr, asset_id), ""]
        if "triangles" in stats:
            d = stats["dimensions"]
            lines += ["| Name | Triangles | Vertices | Size (x × y × z) | File | Materials |",
                      "| --- | --- | --- | --- | --- | --- |",
                      "| {} | {:,} | {:,} | {:.2f} × {:.2f} × {:.2f} m | {:.1f} KB | {} |".format(
                          stats.get("name", ""), stats["triangles"], stats["vertices"], d["x"], d["y"], d["z"],
                          stats["bytes"] / 1024, ", ".join(stats["materials"])), ""]
        lines += ["- ❌ " + e for e in errors] + ["- ⚠️ " + w for w in warnings]
        if not errors and not warnings:
            lines += ["No problems found."]
        lines += [""]

    if not asset_ids and not outside:
        lines += ["No asset changes in this pull request."]
    report = "\n".join(lines) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(report)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
