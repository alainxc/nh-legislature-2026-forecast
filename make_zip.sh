#!/usr/bin/env bash
# Rebuild nh-legislature-2026-site.zip from site/ for upload to the GitHub repository.
set -euo pipefail
cd "$(dirname "$0")"
rm -f nh-legislature-2026-site.zip
(cd site && zip -qr ../nh-legislature-2026-site.zip . -x ".DS_Store")
echo "Wrote nh-legislature-2026-site.zip ($(du -h nh-legislature-2026-site.zip | cut -f1))"
