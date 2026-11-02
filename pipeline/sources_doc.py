"""Build docs/sources.md from every data/raw/*/MANIFEST.json (source URL + retrieval date per file)."""
from __future__ import annotations

import json

from .common import RAW, ROOT

TITLES = {"openelections": "Election returns by town and ward (OpenElections transcription of NH Secretary of State tabulations)",
          "statutes": "District compositions (RSA 662, General Court)", "gencourt": "Current membership and vacancies (General Court, House Clerk)",
          "candidates": "2026 candidates (Ballotpedia, compiled from Secretary of State filings)", "polls": "2026 polls (Wikipedia tables with links to each pollster's release)",
          "polls_historical": "2022 and 2024 polls and results tables (backtests)", "ratings": "Pollster ratings", "shapes": "Boundaries (Census Bureau)"}


def main():
    out = ["Every file the model reads, with where it came from and when it was retrieved. Raw captures are kept under `data/raw/` in the repository; gaps and caveats are in each folder's `NOTES.md` and in the data audit below.", ""]
    for d in sorted(RAW.iterdir()):
        m = d / "MANIFEST.json"
        if not m.exists(): continue
        out.append(f"### {TITLES.get(d.name, d.name)}")
        for e in json.loads(m.read_text()):
            url = e.get("source_url") or ""
            link = f"[{url}]({url})" if url.startswith("http") else "(no URL)"
            out.append(f"- `{e['file']}` — {e['description']} Source: {link} (retrieved {str(e.get('retrieved_at'))[:10]})")
        out.append("")
    (ROOT / "docs" / "sources.md").write_text("\n".join(out))
    print("[sources] wrote docs/sources.md")


if __name__ == "__main__":
    main()
