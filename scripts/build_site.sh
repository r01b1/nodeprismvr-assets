#!/bin/bash
# Assemble the GitHub Pages site in _site/: the gallery from site/ plus the
# library, so assets are served under <site>/library/. Used by the Pages
# workflow; run it locally to preview (python3 -m http.server -d _site).
set -euo pipefail
cd "$(dirname "$0")/.."

python3 scripts/build_library_index.py --check
rm -rf _site
mkdir _site
cp -r site/. _site/
cp -r library _site/library
echo "Built _site/ with $(find _site/library -name '*.glb' | wc -l) assets"
