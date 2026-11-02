#!/usr/bin/env bash
# One-command pipeline: fetch/refresh -> process -> forecast -> backtest -> build site -> zip -> (optionally) publish.
#
#   ./run.sh              # refresh raw sources that can be refreshed, rebuild everything
#   ./run.sh --no-fetch   # use the raw captures already on disk
#   ./run.sh --publish    # ...and push the site to GitHub Pages (needs `gh auth login` once)
#   AS_OF=2026-10-20 ./run.sh   # pretend today is another date (polls after it are ignored)
#   SIMS=5000 ./run.sh --no-fetch
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
FETCH=1; PUBLISH=0; SIMS="${SIMS:-}"
for a in "$@"; do
  case "$a" in
    --no-fetch) FETCH=0;;
    --publish) PUBLISH=1;;
    *) echo "unknown flag $a"; exit 1;;
  esac
done
[ -x "$PY" ] || { echo "Python venv missing. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }

if [ "$FETCH" = 1 ]; then
  echo "== 1/6 Refreshing raw sources (Wikipedia poll pages, Ballotpedia candidate lists, General Court roster) =="
  $PY -I pipeline/fetch/fetch_sources.py || echo "!! refresh failed; continuing with the captures already on disk"
fi

echo "== 2/6 Processing raw data (districts, results, baselines, candidates, polls, geometry) =="
$PY -I pipeline/fetch/build_districts.py
$PY -I pipeline/fetch/build_results.py
$PY -I pipeline/fetch/build_baseline.py
$PY -I pipeline/fetch/build_candidates.py
$PY -I pipeline/fetch/build_polls.py > /dev/null
[ -f site/assets/geo/towns.geojson ] || $PY -I pipeline/fetch/build_geo.py
$PY -I pipeline/fetch/write_manifest.py > /dev/null

echo "== 3/6 Running forecast =="
$PY -m pipeline.run_forecast ${AS_OF:+--as-of "$AS_OF"} ${SIMS:+--sims "$SIMS"}

echo "== 4/6 Backtests (2022, 2024) =="
$PY -m pipeline.backtest

echo "== 5/6 Building site =="
$PY -m pipeline.sources_doc
$PY -m pipeline.build_site
$PY -m pipeline.changelog_entry

echo "== 6/6 Zipping site =="
./make_zip.sh

if [ "$PUBLISH" = 1 ]; then
  echo "== Publishing to GitHub Pages =="
  ./publish.sh
fi
echo "Done. Open site/index.html (or run: $PY -m http.server -d site 8000)"
