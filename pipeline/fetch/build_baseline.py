"""Aggregate town-level statewide results to every district (House base and floterial,
Senate) and assign regions.

Run:  .venv/bin/python -I pipeline/fetch/build_baseline.py
Writes data/processed/district_baseline.csv  (one row per district x race: dem, rep, other, total, towns_missing)
       data/processed/district_regions.csv   (chamber, key, region)
A whole-city entry in a Senate district expands to all of that city's wards. A town whose row
for a race is blank (missing in the source) is reported in towns_missing and excluded from
that race's sum for every district containing it.
"""
import csv, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml
from nh_names import city_of

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "processed")

towns_by_key = collections.defaultdict(list)
with open(os.path.join(OUT, "district_towns.csv"), newline="") as f:
    for r in csv.DictReader(f):
        towns_by_key[(r["chamber"], r["key"])].append(r["town"])
results = collections.defaultdict(dict)   # race -> town -> row
all_towns = set()
with open(os.path.join(OUT, "town_results.csv"), newline="") as f:
    for r in csv.DictReader(f):
        results[r["race"]][r["town"]] = r
        all_towns.add(r["town"])
wards_of = collections.defaultdict(list)
for t in all_towns:
    wards_of[city_of(t)].append(t)


def expand(town):
    """A Senate 'Concord' -> all Concord wards present in the results; a town/ward -> itself."""
    if town in all_towns:
        return [town]
    return wards_of.get(town, [town])


rows = []
for (chamber, key), towns in towns_by_key.items():
    places = sorted({p for t in towns for p in expand(t)})
    for race, res in results.items():
        dem = rep = oth = tot = 0; missing = []
        for p in places:
            r = res.get(p)
            if r is None:
                if race.endswith("2020") and p not in res:
                    missing.append(p)   # 2020 file lacks the unincorporated places (tiny)
                else:
                    missing.append(p)
                continue
            if r["dem"] == "" or r["rep"] == "":
                missing.append(p); continue
            dem += int(r["dem"]); rep += int(r["rep"]); oth += int(r["other"]); tot += int(r["total"])
        rows.append(dict(chamber=chamber, key=key, race=race, dem=dem, rep=rep, other=oth, total=tot, n_places=len(places), towns_missing="|".join(missing)))
with open(os.path.join(OUT, "district_baseline.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# sanity: statewide sums from base House districts equal the town totals
for race in sorted(results):
    base = [r for r in rows if r["chamber"] == "house" and r["race"] == race]
    # floterials double count, so use Senate districts (a partition of the state) for the check
    sen = [r for r in rows if r["chamber"] == "senate" and r["race"] == race]
    tv = results[race].values()
    print(f"[baseline] {race}: senate-sum D {sum(r['dem'] for r in sen):,} R {sum(r['rep'] for r in sen):,} | towns D {sum(int(r['dem'] or 0) for r in tv):,} R {sum(int(r['rep'] or 0) for r in tv):,} | districts with missing places: {sum(1 for r in base if r['towns_missing'])}")

# regions
cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "regions.yaml")))
town_region = {}
for reg, lst in cfg["towns"].items():
    for t in lst:
        town_region[t] = reg
county_of = {}
with open(os.path.join(OUT, "town_results.csv"), newline="") as f:
    for r in csv.DictReader(f):
        county_of[r["town"]] = r["county"]


def region_of_place(p):
    c = city_of(p)
    if c in town_region: return town_region[c]
    return cfg["county_default"].get(county_of.get(p, ""), "concord_merrimack")


reg_rows = []
for (chamber, key), towns in towns_by_key.items():
    places = sorted({p for t in towns for p in expand(t)})
    acc = collections.Counter()
    for p in places:
        r = results["pres2024"].get(p)
        acc[region_of_place(p)] += int(r["total"]) if r and r["total"] else 1
    reg_rows.append(dict(chamber=chamber, key=key, region=acc.most_common(1)[0][0]))
with open(os.path.join(OUT, "district_regions.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["chamber", "key", "region"]); w.writeheader(); w.writerows(reg_rows)
print("[regions]", {ch: dict(collections.Counter(r["region"] for r in reg_rows if r["chamber"] == ch)) for ch in ("senate", "house")})
unassigned = sorted({city_of(p) for p in all_towns if city_of(p) not in town_region})
print(f"[regions] {len(unassigned)} towns fall back to county default, e.g. {unassigned[:12]}")
