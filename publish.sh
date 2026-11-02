#!/usr/bin/env bash
# Publish the built site by uploading nh-legislature-2026-site.zip to the GitHub
# repository root. The repository's Actions workflow (docs/github/deploy-zip.yml)
# unzips it and deploys to GitHub Pages, so the public URL never changes.
# Needs the GitHub CLI logged in once (gh auth login) with repo + workflow scope.
#   ./publish.sh                 # uploads the zip built by make_zip.sh
#   REPO=owner/name ./publish.sh # a different repository
set -euo pipefail
cd "$(dirname "$0")"
REPO="${REPO:-alainxc/nh-legislature-2026-forecast}"
ZIP="nh-legislature-2026-site.zip"
if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not logged in. Run:  gh auth login   and re-run ./publish.sh"; exit 1
fi
[ -f "$ZIP" ] || ./make_zip.sh
SHA=$(gh api "repos/$REPO/contents/$ZIP" --jq .sha 2>/dev/null || true)
TMP=$(mktemp)
python3 - "$ZIP" "$SHA" "$TMP" <<'PY'
import base64, json, sys, datetime
zip_path, sha, out = sys.argv[1:4]
body = {"message": f"Update site ({datetime.date.today().isoformat()} build)", "branch": "main",
        "content": base64.b64encode(open(zip_path, "rb").read()).decode()}
if sha: body["sha"] = sha
json.dump(body, open(out, "w"))
PY
gh api -X PUT "repos/$REPO/contents/$ZIP" --input "$TMP" --jq '"Uploaded as commit " + .commit.sha[0:7]'
rm -f "$TMP"
echo "Waiting for the deploy workflow..."
for i in $(seq 1 36); do
  st=$(gh api "repos/$REPO/actions/runs?per_page=1&event=push" --jq '.workflow_runs[0] | "\(.status) \(.conclusion)"')
  case "$st" in completed*) echo "Workflow: $st"; break;; esac
  sleep 5
done
echo "Published. Site: https://$(echo "$REPO" | cut -d/ -f1).github.io/$(echo "$REPO" | cut -d/ -f2)/"
