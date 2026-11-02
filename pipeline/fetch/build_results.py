"""Build town-level statewide results and district-level legislative results from the
OpenElections NH files (SoS tabulations transcribed by OpenElections).

Run:  .venv/bin/python -I pipeline/fetch/build_results.py
Writes data/processed/town_results.csv          (year, race, county, town, dem, rep, other, total)
       data/processed/legislative_candidates.csv (year, chamber, key, party, candidate, votes, won)
       data/processed/legislative_results.csv    (one row per year x district: seats, candidates, votes, seats won)
       data/processed/incumbents_pre.csv         (House incumbents before each election, from Wikipedia's per-district tables)
Raw files are untrusted: parsed as CSV/HTML text only.
"""
import csv, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nh_names import norm_town, city_of
from bs4 import BeautifulSoup

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OE = os.path.join(ROOT, "data", "raw", "openelections")
OUT = os.path.join(ROOT, "data", "processed")
WIKI = os.path.join(ROOT, "data", "raw", "polls_historical")
os.makedirs(OUT, exist_ok=True)

SKIP_CANDS = {"scatter", "scattrer", "undervotes", "overvotes", "write-ins", "total", "totals", "blank", "blanks"}
COUNTIES = {"Belknap", "Carroll", "Cheshire", "Coos", "Grafton", "Hillsborough", "Merrimack", "Rockingham", "Strafford", "Sullivan"}


def votes(s):
    try:
        return int(str(s).replace(",", "").strip() or 0)
    except ValueError:
        return 0


def party_of(p):
    p = str(p).strip().upper()
    if not p:
        return ""
    tok = p.split(",")[-1].strip()           # "JR., R" -> "R"
    if tok in ("D", "DEM", "DEMOCRAT", "DEMOCRATIC", "I&D"): return "D"
    if tok in ("R", "REP", "REPUBLICAN", "I&R"): return "R"
    if tok in ("I", "IND", "INDEPENDENT", "UND"): return "I"
    if tok in ("L", "LIB", "LIBERTARIAN", "GRN", "SGI", "WRI", "CON"): return "O"
    return "O"


def is_junk(cand):
    c = cand.lower().strip()
    return c in SKIP_CANDS or "w-in" in c or c.startswith("write-in") or c.startswith("write in")


def read(fn):
    with open(os.path.join(OE, fn), newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- town results
town_rows = []


def add_race(year, race, rows, office_filter=None, year_2020=False):
    acc = collections.defaultdict(lambda: {"dem": 0, "rep": 0, "other": 0})
    for r in rows:
        if office_filter and r.get("office") != office_filter:
            continue
        pre = r["precinct"].strip()
        if year_2020 and pre.isupper():
            continue   # the 2020 file carries county subtotal ("BELKNAP", "CARROLL NH") and "TOTALS" rows, all upper-case
        if is_junk(r["candidate"]):
            continue
        town = norm_town(pre)
        p = party_of(r["party"])
        v = votes(r["votes"])
        key = (r["county"].strip().title().replace("Coos Nh", "Coos"), town)
        if p == "D": acc[key]["dem"] += v
        elif p == "R": acc[key]["rep"] += v
        else: acc[key]["other"] += v
    for (county, town), d in acc.items():
        # a missing major-party line (e.g. Amherst's Biden row is absent from the 2020 file) would
        # read as a 100-0 town; blank the row instead and say so
        if (d["dem"] == 0) != (d["rep"] == 0) and max(d["dem"], d["rep"]) > 300:
            print(f"   !! {race} {town}: one major party has zero votes (D {d['dem']}, R {d['rep']}); row blanked as missing")
            d = {"dem": "", "rep": "", "other": ""}
            town_rows.append(dict(year=year, race=race, county=county, town=town, dem="", rep="", other="", total="")); continue
        town_rows.append(dict(year=year, race=race, county=county, town=town, dem=d["dem"], rep=d["rep"], other=d["other"], total=d["dem"] + d["rep"] + d["other"]))


r20 = read("20201103__nh__general__precinct.csv")
add_race(2020, "pres2020", r20, office_filter="President", year_2020=True)
# (the 2020 file's Governor and U.S. Senate sections double-count several towns; only the
#  presidential race, which checks out against the certified total, is used from 2020)
add_race(2022, "gov2022", read("20221108__nh__general__governor__precinct.csv"))
add_race(2022, "ussen2022", read("20221108__nh__general__us__senate__precinct.csv"))
add_race(2022, "cong2022", read("20221108__nh__general__congressional__precinct.csv"))
add_race(2024, "pres2024", read("20241105__nh__general__president__precinct.csv"))
add_race(2024, "gov2024", read("20241105__nh__general__governor__precinct.csv"))
add_race(2024, "cong2024", read("20241105__nh__general__congressional__precinct.csv"))

with open(os.path.join(OUT, "town_results.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["year", "race", "county", "town", "dem", "rep", "other", "total"]); w.writeheader(); w.writerows(town_rows)
for race in sorted({r["race"] for r in town_rows}):
    sub = [r for r in town_rows if r["race"] == race]
    print(f"[towns] {race}: {len(sub)} places, D {sum(r['dem'] or 0 for r in sub):,} R {sum(r['rep'] or 0 for r in sub):,}")

# ---------------------------------------------------------------- districts
districts = {}
with open(os.path.join(OUT, "districts.csv"), newline="") as f:
    for r in csv.DictReader(f):
        districts[(r["chamber"], r["county"], int(r["number"]))] = r
senate_keys = {int(r["number"]): r for r in districts.values() if r["chamber"] == "senate"}


def house_key(county, label):
    num = int(label.rstrip("F"))
    return districts[("house", county, num)]["key"] if ("house", county, num) in districts else None


# ---------------------------------------------------------------- Wikipedia incumbents (House)
def wiki_incumbents(year):
    """Return {(county, number): [(name, party), ...]} of incumbents BEFORE the election, from the
    'By district' results table (columns: District | Incumbent | Party | District | Elected | Party)."""
    fn = {2022: "wiki_nh_house_2022.html", 2024: "wiki_nh_house_2024.html", 2026: None}[year]
    path = os.path.join(WIKI, fn) if fn else os.path.join(ROOT, "data", "raw", "polls", "wiki_nh_house_2026.html")
    s = BeautifulSoup(open(path, encoding="utf8"), "lxml")
    tabs = s.select("table.wikitable")
    tab = max(tabs, key=lambda t: len(t.find_all("tr")))
    out = collections.defaultdict(list)
    elected = collections.defaultdict(list)
    county = None; num = None; county_r = None; num_r = None
    county_left = 0; num_left = 0; county_rleft = 0; num_rleft = 0
    for tr in tab.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        texts = [c.get_text(" ", strip=True).replace("Co\u00f6s", "Coos").replace("Coös", "Coos") for c in cells]
        if not texts:
            continue
        i = 0
        # left block: [county?] [number?] name colour party
        if county_left == 0:
            if i < len(texts) and texts[i] in COUNTIES:
                county = texts[i]; county_left = int(cells[i].get("rowspan", 1)); i += 1
        county_left = max(county_left - 1, 0)
        if num_left == 0:
            if i < len(texts) and re.fullmatch(r"\d+", texts[i]):
                num = int(texts[i]); num_left = int(cells[i].get("rowspan", 1)); i += 1
        num_left = max(num_left - 1, 0)
        if i + 2 < len(texts):
            name, party = texts[i], texts[i + 2]
            party = {"Rep": "R", "Dem": "D"}.get(party.split(" ")[0], "I" if party.startswith("Ind") else party[:1])
            name = name.replace("†", "").strip()
            if name and name.lower() not in ("vacant", "tbd", ""):
                out[(county, num)].append((name, party))
            i += 3
        # right block: [county?] [number?] name colour party
        if county_rleft == 0:
            if i < len(texts) and texts[i] in COUNTIES:
                county_r = texts[i]; county_rleft = int(cells[i].get("rowspan", 1)); i += 1
        county_rleft = max(county_rleft - 1, 0)
        if num_rleft == 0:
            if i < len(texts) and re.fullmatch(r"\d+", texts[i]):
                num_r = int(texts[i]); num_rleft = int(cells[i].get("rowspan", 1)); i += 1
        num_rleft = max(num_rleft - 1, 0)
        if i + 2 < len(texts):
            name, party = texts[i], texts[i + 2]
            party = {"Rep": "R", "Dem": "D"}.get(party.split(" ")[0], "I" if party.startswith("Ind") else party[:1])
            if name and name.lower() not in ("tbd", "vacant"):
                elected[(county_r, num_r)].append((name.replace("†", "").strip(), party))
    return out, elected


inc_rows = []
wiki_elected = {}
for yr in (2022, 2024, 2026):
    inc, el = wiki_incumbents(yr)
    wiki_elected[yr] = el
    n = sum(len(v) for v in inc.values())
    print(f"[wiki] {yr}: incumbents listed {n} across {len(inc)} districts; elected listed {sum(len(v) for v in el.values())}")
    for (county, num), lst in inc.items():
        k = districts.get(("house", county, num))
        if not k:
            if yr != 2022:
                print("   unmatched district", county, num)
            k = {"key": ""}
        for name, party in lst:
            inc_rows.append(dict(year=yr, chamber="house", key=k["key"], county=county, name=name, party=party))
with open(os.path.join(OUT, "incumbents_pre.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["year", "chamber", "key", "county", "name", "party"]); w.writeheader(); w.writerows(inc_rows)

# ---------------------------------------------------------------- legislative results
cand_rows, dist_rows = [], []


def surname(n):
    n = re.sub(r"\b(Jr|Sr|II|III|IV)\.?$", "", n.strip()).strip()
    return n.split()[-1].lower() if n else ""


def legislative(year, chamber, rows):
    acc = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        if is_junk(r["candidate"]):
            continue
        pre = r["precinct"].strip(); label = r["district"].strip(); county = r["county"].strip()
        if chamber == "house":
            # SoS/OpenElections label Dover Ward 3 as Strafford 15; by statute it is Strafford 16
            if norm_town(pre) == "Dover Ward 3" and label == "15":
                label = "16"
            key = house_key(county, label)
        else:
            key = senate_keys[int(label)]["key"]
        if key is None:
            print("   unknown district", year, chamber, county, label); continue
        acc[key][(party_of(r["party"]), r["candidate"].strip())] += votes(r["votes"])
    dmeta = {d["key"]: d for d in districts.values()}
    inc_lookup = collections.defaultdict(list)
    for ir in inc_rows:
        if ir["year"] == year and ir["chamber"] == chamber:
            inc_lookup[ir["key"]].append(ir)
    if chamber == "senate":
        statewide = [ir for ir in inc_rows if ir["year"] == year and ir["chamber"] == "senate"]
        inc_lookup = collections.defaultdict(list, {d["key"]: statewide for d in districts.values() if d["chamber"] == "senate"})
    if year == 2022 and chamber == "house":
        # the 2022 page's incumbent column uses the 2012-map district numbers (new map that
        # year), so incumbents are matched by county instead of by district
        by_county = collections.defaultdict(list)
        for ir in inc_rows:
            if ir["year"] == year and ir["chamber"] == chamber:
                by_county[ir["county"]].append(ir)
        inc_lookup = collections.defaultdict(list, {d["key"]: by_county[d["county"]] for d in districts.values() if d["chamber"] == "house"})
    for key, c in acc.items():
        seats = int(dmeta[key]["seats"])
        ranked = sorted(c.items(), key=lambda kv: -kv[1])
        winners = ranked[:seats]
        # fill from Wikipedia when the SoS data names fewer candidates than seats
        names = {n for (_, n) in c}
        filled = []
        if chamber == "house" and len(ranked) < seats:
            county, num = dmeta[key]["county"], int(dmeta[key]["number"])
            for n, p in wiki_elected.get(year, {}).get((county, num), []):
                if surname(n) not in {surname(x) for x in names}:
                    filled.append(((p, n + " [winner per Wikipedia; votes not in SoS file]"), None))
        tally = collections.Counter(p for (p, n), v in winners) + collections.Counter(p for (p, n), v in filled)
        for (p, n), v in ranked:
            inc = any(surname(n) == surname(ir["name"]) and ir["party"] == p for ir in inc_lookup.get(key, []))
            cand_rows.append(dict(year=year, chamber=chamber, key=key, party=p, candidate=n, votes=v, won=((p, n), v) in winners, incumbent_pre=inc))
        for (p, n), v in filled:
            cand_rows.append(dict(year=year, chamber=chamber, key=key, party=p, candidate=n, votes="", won=True, incumbent_pre=False))
        n_d = sum(1 for (p, n) in c if p == "D"); n_r = sum(1 for (p, n) in c if p == "R"); n_o = len(c) - n_d - n_r
        dv = sum(v for (p, n), v in c.items() if p == "D"); rv = sum(v for (p, n), v in c.items() if p == "R"); ov = sum(v for (p, n), v in c.items() if p not in ("D", "R"))
        mean_d = dv / n_d if n_d else 0.0; mean_r = rv / n_r if n_r else 0.0
        contested = n_d > 0 and n_r > 0 and len(c) > seats
        inc_d = sum(1 for ir in inc_lookup.get(key, []) if ir["party"] == "D" and any(surname(ir["name"]) == surname(n) for (p, n) in c if p == "D"))
        inc_r = sum(1 for ir in inc_lookup.get(key, []) if ir["party"] == "R" and any(surname(ir["name"]) == surname(n) for (p, n) in c if p == "R"))
        dist_rows.append(dict(year=year, chamber=chamber, key=key, seats=seats, n_d=n_d, n_r=n_r, n_other=n_o,
                              d_votes=dv, r_votes=rv, other_votes=ov, mean_d_votes=round(mean_d, 1), mean_r_votes=round(mean_r, 1),
                              party_margin=(round(100 * (mean_d - mean_r) / (mean_d + mean_r), 2) if (mean_d + mean_r) > 0 else ""),
                              d_seats=tally.get("D", 0), r_seats=tally.get("R", 0), other_seats=sum(v for k2, v in tally.items() if k2 not in ("D", "R")),
                              contested=contested, inc_d_running=inc_d, inc_r_running=inc_r,
                              filled_from_wikipedia=len(filled)))


# Senate incumbents: the senator elected at the previous election (2020 winners from the 2020
# file for 2022; 2022 winners for 2024), matched statewide by surname.
def senate_winners_2020():
    acc = collections.defaultdict(lambda: collections.Counter())
    for r in r20:
        if r["office"] == "State Senate" and not is_junk(r["candidate"]) and not r["precinct"].isupper():
            acc[r["district"]][(party_of(r["party"]), r["candidate"].strip())] += votes(r["votes"])
    return [max(c.items(), key=lambda kv: kv[1])[0] for c in acc.values()]

def add_senate_incumbents(year, winners):
    for p, n in winners:
        inc_rows.append(dict(year=year, chamber="senate", key="", county="", name=n, party=p))

add_senate_incumbents(2022, senate_winners_2020())
legislative(2022, "house", read("20221108__nh__general__state__representative__precinct.csv"))
legislative(2024, "house", read("20241105__nh__general__state__representative__precinct.csv"))
legislative(2022, "senate", read("20221108__nh__general__state__senate__precinct.csv"))
add_senate_incumbents(2024, [(c["party"], c["candidate"]) for c in cand_rows if c["year"] == 2022 and c["chamber"] == "senate" and c["won"]])
legislative(2024, "senate", read("20241105__nh__general__state__senate__precinct.csv"))

with open(os.path.join(OUT, "legislative_candidates.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(cand_rows[0].keys())); w.writeheader(); w.writerows(cand_rows)
with open(os.path.join(OUT, "legislative_results.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(dist_rows[0].keys())); w.writeheader(); w.writerows(dist_rows)

for yr in (2022, 2024):
    for ch in ("house", "senate"):
        sub = [r for r in dist_rows if r["year"] == yr and r["chamber"] == ch]
        print(f"[leg] {yr} {ch}: {len(sub)} districts, seats {sum(r['seats'] for r in sub)}, D {sum(r['d_seats'] for r in sub)} R {sum(r['r_seats'] for r in sub)} other {sum(r['other_seats'] for r in sub)}; "
              f"contested {sum(1 for r in sub if r['contested'])}; filled from Wikipedia {sum(r['filled_from_wikipedia'] for r in sub)}; incumbents matched D {sum(r['inc_d_running'] for r in sub)} R {sum(r['inc_r_running'] for r in sub)}")
