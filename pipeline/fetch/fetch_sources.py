"""Refresh the raw sources that change between runs: Wikipedia poll/candidate pages, Ballotpedia
candidate tables, the General Court roster and the House Clerk's vacancy list. Every download
overwrites the previous capture only if the new copy is non-trivial (> 20 KB for HTML pages).
Run with: .venv/bin/python -I pipeline/fetch/fetch_sources.py
"""
import os, sys, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
W = "https://en.wikipedia.org/wiki/"
TARGETS = {
    "polls/wiki_nh_gov_2026.html": W + "2026_New_Hampshire_gubernatorial_election",
    "polls/wiki_us_house_nh_2026.html": W + "2026_United_States_House_of_Representatives_elections_in_New_Hampshire",
    "polls/wiki_nh_house_2026.html": W + "2026_New_Hampshire_House_of_Representatives_election",
    "polls/wiki_nh_senate_2026.html": W + "2026_New_Hampshire_Senate_election",
    "polls/wiki_us_elections_2026.html": W + "2026_United_States_elections",
    "candidates/ballotpedia_nh_house_2026.html": "https://ballotpedia.org/New_Hampshire_House_of_Representatives_elections,_2026",
    "candidates/ballotpedia_nh_senate_2026.html": "https://ballotpedia.org/New_Hampshire_State_Senate_elections,_2026",
    "gencourt/Members.txt": "https://gencourt.state.nh.us/downloads/Members.txt",
    "gencourt/RDSE.pdf": "https://www.gencourt.state.nh.us/house/aboutthehouse/RDSE.pdf",
}
ok = 0
for rel, url in TARGETS.items():
    path = os.path.join(RAW, rel)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        data = urllib.request.urlopen(req, timeout=60).read()
        if len(data) < (20000 if rel.endswith(".html") else 2000):
            print(f"  skipped {rel}: response too small ({len(data)} bytes)"); continue
        with open(path, "wb") as f:
            f.write(data)
        ok += 1; print(f"  refreshed {rel} ({len(data):,} bytes)")
    except Exception as e:  # noqa
        print(f"  failed {rel}: {e}")
print(f"[fetch] refreshed {ok}/{len(TARGETS)} sources")
sys.exit(0)
