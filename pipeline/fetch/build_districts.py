"""Parse RSA 662:5 (House) and RSA 662:3 (Senate) into district composition tables.

Run:  .venv/bin/python -I pipeline/fetch/build_districts.py
Writes data/processed/districts.csv (one row per district) and
       data/processed/district_towns.csv (one row per district x town/ward).
Floterial districts are detected as districts whose every town already belongs to a
lower-numbered district in the same county (RSA 662:5 lists them after the base districts).
"""
import csv, html, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nh_names import norm_town

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw", "statutes")
OUT = os.path.join(ROOT, "data", "processed")
os.makedirs(OUT, exist_ok=True)

# Every town, city ward and unincorporated place named in either statute. Built from the
# Senate statute (comma separated, unambiguous) and used to tokenise the House statute,
# whose town lists have no separators ("Center Harbor New Hampton 1").
def text_of(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    t = re.sub(r"<br\s*/?>", "\n", t); t = re.sub(r"<[^>]+>", "", t); t = html.unescape(t)
    return re.sub(r"\s+", " ", t)

sen_txt = text_of(os.path.join(RAW, "rsa_662-3_senate_districts.html"))
house_txt = text_of(os.path.join(RAW, "rsa_662-5_house_districts.html"))

# ---------------- Senate ----------------
senate = []
for m in re.finditer(r"Senatorial district number (\d+) is constituted of (.*?)\.(?= [IVX]+\. | Source)", sen_txt):
    d = int(m.group(1)); body = m.group(2)
    towns = []
    # "wards 1, 2, and 5 in Nashua, and Brookline, ..." / "ward 1 in Manchester, and Candia"
    for wm in re.finditer(r"wards? ([\d, and]+) in (\w+)", body):
        nums = [int(x) for x in re.findall(r"\d+", wm.group(1))]
        towns += [f"{wm.group(2)} Ward {n}" for n in nums]
    body2 = re.sub(r"wards? [\d, and]+ in \w+,?", "", body)
    for part in body2.split(","):
        part = re.sub(r"^\s*and\s+", "", part.strip()).strip()
        if part and part.lower() != "and":
            towns.append(norm_town(part))
    senate.append((d, towns))
assert len(senate) == 24, len(senate)

# ---------------- House ----------------
# vocabulary of place names: everything in the Senate statute + multi-word names + "X Ward n"
vocab = set()
for _, ts in senate:
    for t in ts:
        vocab.add(t.split(" Ward ")[0] if " Ward " in t else t)
vocab |= {"Hale's Location", "Hart's Location", "Waterville Valley", "Center Harbor", "New Hampton", "New Castle", "New Durham",
          "New Boston", "New Ipswich", "New London", "North Hampton", "South Hampton", "Hampton Falls", "East Kingston",
          "Mont Vernon", "Sugar Hill", "Second College Grant", "Low and Burbank's Grant", "Thompson and Meserve's Purchase",
          "Atkinson & Gilmanton Academy Grant", "Wentworth's Location", "Erving's Location", "Martin's Location",
          "Bean's Grant", "Bean's Purchase", "Chandler's Purchase", "Crawford's Purchase", "Cutt's Grant", "Dix's Grant",
          "Green's Grant", "Hadley's Purchase", "Pinkham's Grant", "Sargent's Purchase", "Hampton", "Kingston", "Durham", "Boston", "London", "Ipswich", "Castle"}
# Longest-first tokeniser
HOUSE_ABBREV = {"E. Kingston": "East Kingston", "S. Hampton": "South Hampton", "N. Hampton": "North Hampton", "Hale's Loc.": "Hale's Location", "Hart's Loc.": "Hart's Location"}
vocab_sorted = sorted(vocab, key=len, reverse=True)

def tokenise(s):
    """Split 'Chesterfield Hinsdale Keene Ward 1 Keene Ward 3 Surry' into canonical names."""
    for a, b in HOUSE_ABBREV.items():
        s = s.replace(a, b)
    out = []
    while s:
        s = s.strip()
        if not s: break
        m = re.match(r"^([A-Z][A-Za-z'.]+(?: [A-Z][A-Za-z'.]+)*?) Ward (\d+)", s)
        if m and norm_town(m.group(1)) in vocab:
            out.append(f"{norm_town(m.group(1))} Ward {int(m.group(2))}"); s = s[m.end():]; continue
        hit = None
        for v in vocab_sorted:
            vv = v.replace("&", "&")
            if s.startswith(vv) and (len(s) == len(vv) or s[len(vv)] == " "):
                hit = v; break
        if hit is None:
            # try alias spellings (e.g. "Atkinson & Gilmanton Academy Grant")
            for v in vocab_sorted:
                if norm_town(s[:len(v)]) == v and (len(s) == len(v) or s[len(v)] == " "):
                    hit = v; break
        if hit is None:
            raise SystemExit(f"cannot tokenise: {s[:80]!r}")
        out.append(hit); s = s[len(hit):]
    return out

house = []
county = None
for m in re.finditer(r"(?:^| )(I|II|III|IV|V|VI|VII|VIII|IX|X)\. (\w+) County|District No\. (\d+) (.*?) (\d+)(?= District No\.| [IVX]+\. |\s*Source)", house_txt):
    if m.group(2):
        county = m.group(2); continue
    num, body, seats = int(m.group(3)), m.group(4), int(m.group(5))
    house.append((county, num, tokenise(body), seats))
assert len(house) == 203 and sum(h[3] for h in house) == 400, (len(house), sum(h[3] for h in house))

# floterial detection: the SoS tabulations (via OpenElections) label floterials with an F
# suffix ("Belknap 8F"). Read those labels, then verify that the non-floterial districts
# partition each county's towns exactly once (the legal definition of base districts).
oe = os.path.join(ROOT, "data", "raw", "openelections", "20241105__nh__general__state__representative__precinct.csv")
flot_labels = set()
with open(oe, newline="") as f:
    for r in csv.DictReader(f):
        if r["district"].endswith("F"):
            flot_labels.add((r["county"], int(r["district"][:-1])))
rows, town_rows = [], []
seen_by_county = {}
for county, num, towns, seats in house:
    flot = False   # decided below by the partition rule; SoS labels are only a cross-check
    key = f"{county}-{num}"
    rows.append(dict(chamber="house", key=key, district_id=f"{county} {num}", county=county, number=num,
                     floterial=flot, seats=seats, n_towns=len(towns), towns="|".join(towns)))
    for t in towns:
        town_rows.append(dict(chamber="house", key=key, town=t))
for d, towns in senate:
    rows.append(dict(chamber="senate", key=f"S{d}", district_id=f"District {d}", county="", number=d,
                     floterial=False, seats=1, n_towns=len(towns), towns="|".join(towns)))
    for t in towns:
        town_rows.append(dict(chamber="senate", key=f"S{d}", town=t))

with open(os.path.join(OUT, "districts.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
with open(os.path.join(OUT, "district_towns.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["chamber", "key", "town"]); w.writeheader(); w.writerows(town_rows)

# Floterial rule: base districts partition a county's towns; floterials overlay them. Start
# from the SoS "F" labels (which mislabel a few districts) and repair until the non-floterial
# districts cover every town in the county exactly once:
#   - a town covered by no base district -> the F-labelled district holding it is really base
#     (Cheshire 14 Rindge, Grafton 16 Enfield);
#   - a town covered twice -> the base district all of whose towns are over-covered is really a
#     floterial (Hillsborough 44, Strafford 18).
from collections import Counter
for r in rows:
    if r["chamber"] == "house":
        r["floterial"] = (r["county"], r["number"]) in flot_labels
for _ in range(50):
    hb = [r for r in rows if r["chamber"] == "house" and not r["floterial"]]
    cnt = Counter(t for r in hb for t in r["towns"].split("|"))
    changed = False
    for r in rows:
        if r["chamber"] != "house" or not r["floterial"]:
            continue
        if any(cnt[t] == 0 for t in r["towns"].split("|")):
            r["floterial"] = False; changed = True; break
    if changed:
        continue
    for r in sorted(hb, key=lambda r: -r["number"]):
        if all(cnt[t] > 1 for t in r["towns"].split("|")):
            r["floterial"] = True; changed = True; break
    if not changed:
        break
with open(os.path.join(OUT, "districts.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
nflot = sum(1 for r in rows if r["floterial"])
print(f"House: {len(house)} districts ({nflot} floterial, {sum(r['seats'] for r in rows if r['floterial'])} floterial seats)")
mine = {(r["county"], r["number"]) for r in rows if r["chamber"] == "house" and r["floterial"]}
print("  SoS-labelled F but base by statute:", sorted(flot_labels - mine)); print("  floterial by statute but no F label:", sorted(mine - flot_labels))
base = Counter(t for r in rows if r["chamber"] == "house" and not r["floterial"] for t in r["towns"].split("|"))
assert all(c == 1 for c in base.values()), [t for t, c in base.items() if c != 1]
flot_towns = {t for r in rows if r["chamber"] == "house" and r["floterial"] for t in r["towns"].split("|")}
assert flot_towns <= set(base), sorted(flot_towns - set(base))
sen = Counter(t for r in rows if r["chamber"] == "senate" for t in r["towns"].split("|"))
print("towns in base House districts:", len(base), "dups:", [t for t, c in base.items() if c > 1][:5])
print("towns in Senate districts:", len(sen), "dups:", [t for t, c in sen.items() if c > 1][:5])
print("in Senate not House:", sorted(set(sen) - set(base))[:10]); print("in House not Senate:", sorted(set(base) - set(sen))[:10])
