"""Build data/processed/polls_statewide.csv (2026), polls_historical.csv (2022/2024 backtests)
and pollster_ratings.csv from raw Wikipedia captures. Run: .venv/bin/python -I pipeline/fetch/build_polls.py
Every poll row comes from a wikitable row; source_url = external citation in the row (else the Wikipedia page).
Also writes data/raw/polls/NOTES.md.
"""
import csv, re, sys, os, datetime as dt
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_tables import load, ref_map, table_rows

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "processed")
os.makedirs(OUT, exist_ok=True)
WP = "https://en.wikipedia.org/wiki/"

MONTHS = {}
for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                       "September", "October", "November", "December"], 1):
    MONTHS[m] = i; MONTHS[m[:3]] = i
MONTHS["Sept"] = 9

def D(y, mo, d): return dt.date(int(y), MONTHS[mo], int(d)).isoformat()

def parse_dates(s):
    s = s.replace("–", "-").replace("—", "-").replace("\xa0", " ").replace(" ", " ").strip()
    s = re.sub(r"\s+", " ", s)
    W = r"([A-Za-z]+)\.?"
    m = re.match(rf"{W} (\d+), (\d{{4}})\s*-\s*{W} (\d+), (\d{{4}})$", s)
    if m: return D(m[3], m[1], m[2]), D(m[6], m[4], m[5])
    m = re.match(rf"{W} (\d+)\s*-\s*{W} (\d+), (\d{{4}})$", s)
    if m: return D(m[5], m[1], m[2]), D(m[5], m[3], m[4])
    m = re.match(rf"{W} (\d+)\s*-\s*(\d+), (\d{{4}})$", s)
    if m: return D(m[4], m[1], m[2]), D(m[4], m[1], m[3])
    m = re.match(rf"{W} (\d+), (\d{{4}})$", s)
    if m: d = D(m[3], m[1], m[2]); return d, d
    m = re.match(rf"{W} (\d{{4}})$", s)
    if m: return D(m[2], m[1], 1), ""
    return "", ""

def parse_sample(s):
    s = s.replace("\xa0", " ")
    m = re.match(r"([\d,]+)\s*\((LV|RV|A|V)\)", s)
    if m: return m.group(1).replace(",", ""), m.group(2)
    m = re.match(r"([\d,]+)", s)
    n = m.group(1).replace(",", "") if m else ""
    m = re.search(r"\((LV|RV|A|V)\)", s)
    return n, (m.group(1) if m else "")

def pct(s):
    s = (s or "").replace("\xa0", " ").strip()
    m = re.match(r"(\d+(?:\.\d+)?)\s*%?['\u2019]?$", s)
    return m.group(1) if m else ""

def margin(a, b):
    try: return str(round(float(a) - float(b), 1)).rstrip("0").rstrip(".")
    except ValueError: return ""

def party_tag(name, notes):
    d, r = re.search(r"\(D\)", name), re.search(r"\(R\)", name)
    if d and r: return "none"
    if d: return "D"
    if r: return "R"
    return "none"

def sponsor_from_notes(notes):
    for n in notes:
        m = re.search(r"(?:sponsored|commissioned|paid for) by (?:the )?(.+?)(?:,| which|\.|$)", n)
        if m: return m.group(1).strip()
        m = re.search(r"conducted for (?:the )?(.+?)(?:,|\.|$)", n)
        if m: return m.group(1).strip()
    return ""

COLS = ["poll_type", "pollster", "sponsor", "sponsor_party", "start_date", "end_date", "sample_size",
        "population", "dem_value", "rep_value", "margin_dem", "mode", "source_url", "notes"]

NOTES = []   # (file, table desc, rows, skipped list)
_cache = {}
def get(path):
    if path not in _cache:
        s = load(os.path.join(RAW, path)); _cache[path] = (s, ref_map(s))
    return _cache[path]

def hdr(t):
    return [re.sub(r"\s*\[.*?\]\s*", "", th.get_text(" ", strip=True)).strip()
            for th in t.find("tr").find_all(["th", "td"])]

def find_tables(soup, col_a, col_b, ncols=None):
    """Poll tables whose first two data columns are col_a, col_b (in that header order)."""
    out = []
    for t in soup.select("table.wikitable"):
        h = hdr(t)
        if h[:2] == ["Poll source", "Date(s) administered"] and len(h) >= 6 and h[4:6] == [col_a, col_b] \
           and (ncols is None or len(h) == ncols):
            out.append(t)
    return out

def section(t):
    h = t.find_previous(["h2", "h3", "h4"])
    return h.get_text(" ", strip=True) if h else ""

def parse_table(path, wiki_page, t, refs, poll_type, dem_col, rep_col, note_prefix="", min_end=None, max_end=None,
                desc=""):
    rows, skipped, seen = [], [], set()
    page_url = WP + wiki_page
    for r in table_rows(t, refs):
        src = r.get("Poll source")
        if not src or not r.get(dem_col) or not r.get(rep_col):
            skipped.append(f"{(src[0] if src else '?')[:70]!r}: event/marker row (no values)"); continue
        name = src[0]
        dates = (r.get("Date(s) administered") or ("",))[0]
        sd, ed = parse_dates(dates)
        dem, rep = pct(r[dem_col][0]), pct(r[rep_col][0])
        if not (ed and dem and rep):
            skipped.append(f"{name[:50]!r} dates={dates!r} dem={r[dem_col][0]!r} rep={r[rep_col][0]!r}: unparsable/marker")
            continue
        if min_end and ed < min_end: skipped.append(f"{name[:40]!r} {ed}: before {min_end}"); continue
        if max_end and ed > max_end: skipped.append(f"{name[:40]!r} {ed}: after election day {max_end}"); continue
        n, pop = parse_sample(r["Sample size"][0])
        other = [f"{k}={r[k][0]}" for k in r if k not in ("Poll source", "Date(s) administered", "Sample size",
                 "Margin of error", dem_col, rep_col, "Lead") and r[k] and r[k][0]]
        extra = []
        for k in ("Poll source", dem_col, rep_col):
            extra += r[k][2]
        if (name, dates) in seen:
            note_prefix_r = note_prefix + "additional row for same poll (alternate sample/variant on Wikipedia); "
        else:
            note_prefix_r = note_prefix
        seen.add((name, dates))
        note = f"{note_prefix_r}MoE {r['Margin of error'][0]}; " + "; ".join(other)
        if extra: note += ". " + " ".join(extra)
        url = src[1][0] if src[1] else page_url
        pollster = re.sub(r"\s*\((D|R)\)", "", name).strip()
        rows.append(dict(poll_type=poll_type, pollster=pollster, sponsor=sponsor_from_notes(src[2]),
            sponsor_party=party_tag(name, src[2]), start_date=sd, end_date=ed, sample_size=n, population=pop,
            dem_value=dem, rep_value=rep, margin_dem=margin(dem, rep), mode="", source_url=url,
            notes=note.strip()))
    NOTES.append((path, desc or f"{poll_type} [{dem_col} vs {rep_col}]", len(rows), skipped))
    return rows

def one(path, wiki_page, dem_col, rep_col, poll_type, idx=0, ncols=None, **kw):
    """Find the table with these two candidate columns (either order) and parse it."""
    soup, refs = get(path)
    ts = find_tables(soup, dem_col, rep_col, ncols) + find_tables(soup, rep_col, dem_col, ncols)
    if len(ts) <= idx: raise SystemExit(f"table not found: {path} {dem_col}/{rep_col} idx {idx}")
    t = ts[idx]
    return parse_table(path, wiki_page, t, refs, poll_type, dem_col, rep_col,
                       desc=f"{poll_type}: '{dem_col}' (D) vs '{rep_col}' (R) (section '{section(t)}', match #{idx})", **kw)

P, H = "polls/", "polls_historical/"
stat, hist = [], []
def add(cycle, rows): hist.extend([dict(cycle=cycle, **r) for r in rows])

# ---------------- 2026 ----------------
stat += one(P+"wiki_nh_gov_2026.html", "2026_New_Hampshire_gubernatorial_election",
            "Cinde Warmington (D)", "Kelly Ayotte (R)", "nh_governor")
HP = "2026_United_States_House_of_Representatives_elections_in_New_Hampshire"
stat += one(P+"wiki_us_house_nh_2026.html", HP, "Democratic", "Republican", "nh_congressional_generic")
stat += one(P+"wiki_us_house_nh_2026.html", HP, "Stefany Shaheen (D)", "Anthony DiLorenzo (R)", "nh_cd1")
stat += one(P+"wiki_us_house_nh_2026.html", HP, "Maggie Goodlander (D)", "Lily Tang Williams (R)", "nh_cd2")
stat += one(P+"wiki_nh_house_2026.html", "2026_New_Hampshire_House_of_Representatives_election",
            "Democratic", "Republican", "nh_legislative_generic", note_prefix="chamber=house; ")
stat += one(P+"wiki_nh_senate_2026.html", "2026_New_Hampshire_Senate_election",
            "Democratic", "Republican", "nh_legislative_generic", note_prefix="chamber=senate; ")
soup, refs = get(P+"wiki_us_elections_2026.html")
for t in find_tables(soup, "Democratic", "Republican"):
    stat += parse_table(P+"wiki_us_elections_2026.html", "2026_United_States_elections", t, refs,
                        "national_generic_ballot", "Democratic", "Republican", min_end="2026-01-01",
                        desc=f"national_generic_ballot: section '{section(t)}' (only end_date >= 2026-01-01 kept)")

# ---------------- historical ----------------
E22, E24 = "2022-11-08", "2024-11-05"
add(2022, one(H+"wiki_nh_gov_2022.html", "2022_New_Hampshire_gubernatorial_election",
              "Tom Sherman (D)", "Chris Sununu (R)", "nh_governor", max_end=E22))
add(2022, one(H+"wiki_nh_ussen_2022.html", "2022_United_States_Senate_election_in_New_Hampshire",
              "Maggie Hassan (D)", "Don Bolduc (R)", "nh_us_senate", max_end=E22))
HP22 = "2022_United_States_House_of_Representatives_elections_in_New_Hampshire"
add(2022, one(H+"wiki_us_house_nh_2022.html", HP22, "Chris Pappas (D)", "Karoline Leavitt (R)", "nh_cd1", max_end=E22))
add(2022, one(H+"wiki_us_house_nh_2022.html", HP22, "Annie Kuster (D)", "Robert Burns (R)", "nh_cd2", max_end=E22))
for idx, dist in ((0, "1"), (1, "2")):
    add(2022, one(H+"wiki_us_house_nh_2022.html", HP22, "Generic Democrat", "Generic Republican",
                  "nh_congressional_generic", idx=idx, note_prefix=f"district={dist}; ", max_end=E22))
add(2024, one(H+"wiki_nh_pres_2024.html", "2024_United_States_presidential_election_in_New_Hampshire",
              "Kamala Harris Democratic", "Donald Trump Republican", "nh_president", ncols=7, max_end=E24))
add(2024, one(H+"wiki_nh_gov_2024.html", "2024_New_Hampshire_gubernatorial_election",
              "Joyce Craig (D)", "Kelly Ayotte (R)", "nh_governor", max_end=E24))
HP24 = "2024_United_States_House_of_Representatives_elections_in_New_Hampshire"
add(2024, one(H+"wiki_us_house_nh_2024.html", HP24, "Chris Pappas (D)", "Russell Prescott (R)", "nh_cd1", max_end=E24))
add(2024, one(H+"wiki_us_house_nh_2024.html", HP24, "Maggie Goodlander (D)", "Lily Tang Williams (R)", "nh_cd2", max_end=E24))

def key(r): return (r.get("cycle", 0), r["poll_type"], r["end_date"], r["pollster"])
stat.sort(key=key); hist.sort(key=key)
with open(os.path.join(OUT, "polls_statewide.csv"), "w", newline="", encoding="utf8") as f:
    w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(stat)
with open(os.path.join(OUT, "polls_historical.csv"), "w", newline="", encoding="utf8") as f:
    w = csv.DictWriter(f, fieldnames=["cycle"] + COLS); w.writeheader(); w.writerows(hist)

# ---------------- ratings ----------------
nrat = 0
with open(os.path.join(RAW, "ratings", "538_pollster_ratings_combined.csv"), encoding="utf8") as f, \
     open(os.path.join(OUT, "pollster_ratings.csv"), "w", newline="", encoding="utf8") as g:
    w = csv.writer(g); w.writerow(["pollster", "grade_or_score", "source"])
    for r in csv.DictReader(f):
        if r["numeric_grade"].strip() == "": continue
        w.writerow([r["pollster"], r["numeric_grade"], "fivethirtyeight_combined"]); nrat += 1

# ---------------- NOTES.md ----------------
with open(os.path.join(RAW, "polls", "NOTES.md"), "w", encoding="utf8") as f:
    f.write("# Poll table parsing notes\n\nGenerated by pipeline/fetch/build_polls.py (do not hand-edit).\n"
            "Each row = one Wikipedia table row; source_url = external citation in the Poll source cell, "
            "else the Wikipedia page URL. margin_dem = dem - rep. Pollster (D)/(R) tags are stripped from "
            "pollster and recorded in sponsor_party. Historical rows kept only if end_date <= election day.\n\n")
    for path, desc, n, sk in NOTES:
        f.write(f"## {path}\n- {desc}: **{n} rows**\n")
        for x in sk[:40]: f.write(f"  - skipped: {x}\n")
        if len(sk) > 40: f.write(f"  - ... and {len(sk)-40} more skipped\n")
        f.write("\n")
    f.write("## Quirks\n"
            "- Event-marker rows (colspan notes such as primaries, conventions, candidate withdrawals) are skipped; "
            "counts are therefore lower than raw table row counts (e.g. CD2 2026 table: 9 polls + 1 event row; "
            "Harris-Trump 2024 table: 13 poll rows + 7 event rows, 2 Emerson/CES polls have two rows each).\n"
            "- Multi-row polls (rowspan: alternate samples/leaner variants) produce one CSV row each; later ones are "
            "flagged 'additional row for same poll' in notes. Some rows have no sample size (source shows only '(LV)').\n"
            "- Wikipedia's 2024 Harris-Trump table contains a Trafalgar Group row dated 2021-12-10..12 (identical to "
            "the 2022 Senate Trafalgar poll; likely a Wikipedia mislabel). Kept as in source; downweight/drop by date.\n"
            "- The 2026 NH CD1/CD2 tables include 2025 polls (cycle 2026); only the national generic ballot is cut at 2026-01-01.\n"
            "- Header 'Lead' column of the national table is ignored; margin_dem is recomputed.\n\n")
    f.write(f"## Ratings\n538_pollster_ratings_combined.csv -> pollster_ratings.csv: {nrat} rows with numeric_grade; "
            "pollsters without an exact name match are treated as unrated by the model.\n")

# ---------------- summary ----------------
c = Counter((r.get("cycle", 2026), r["poll_type"]) for r in stat + hist)
for k in sorted(c): print(k, c[k])
print("ratings:", nrat)
by = defaultdict(list)
for r in stat: by[r["poll_type"]].append(r)
for t, rs in by.items():
    print("\n--", t)
    for r in sorted(rs, key=lambda r: r["end_date"], reverse=True)[:5]:
        print(" ", r["end_date"], r["pollster"][:45], r["sample_size"], r["population"], r["dem_value"], r["rep_value"], r["sponsor_party"], r["source_url"][:60])
