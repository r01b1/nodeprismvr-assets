#!/bin/bash
# Assemble the GitHub Pages site in _site/: the gallery from site/ plus the
# library, so assets are served under <site>/library/, and site-files.json,
# the list of the website's files for mirrors. Used by the Pages
# workflow; run it locally to preview (python3 -m http.server -d _site).
set -euo pipefail
cd "$(dirname "$0")/../.."

rm -rf _site
mkdir _site
cp -r site/. _site/
cp -r library _site/library
python3 tools/library/build_library_index.py --out _site/library/index.json
# The website's own files, for mirrors (tools/mirror/syncNodeprismLibrary.php).
(cd site && find . -type f | sed 's|^\./||' | sort) | python3 -c 'import json, sys; print(json.dumps(sys.stdin.read().split()))' > _site/site-files.json
echo "Built _site/ with $(find _site/library -name '*.glb' | wc -l) assets"
