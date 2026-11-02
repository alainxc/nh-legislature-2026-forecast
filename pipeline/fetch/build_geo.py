"""Build NH GeoJSON (towns/wards, House, Senate, counties) from Census TIGER shapefiles.
Run: .venv/bin/python -I pipeline/fetch/build_geo.py   (inputs are untrusted; only parsed with pyshp)
"""
import csv, json, os, re, sys
from collections import defaultdict
import shapefile
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import transform, unary_union
from shapely.validation import make_valid
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nh_names import norm_town, city_of

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(ROOT, "data/raw/shapes"); GEO = os.path.join(ROOT, "site/assets/geo"); PROC = os.path.join(ROOT, "data/processed")
os.makedirs(GEO, exist_ok=True)
TOL_T = float(os.environ.get("TOL_T", "0.0002")); TOL_D = float(os.environ.get("TOL_D", "0.0003"))

to_aea = Transformer.from_crs("EPSG:4269", "+proj=aea +lat_1=43 +lat_2=45 +lat_0=43.5 +lon_0=-71.5 +datum=NAD83 +units=m", always_xy=True).transform
to_wgs = Transformer.from_crs("EPSG:4269", "EPSG:4326", always_xy=True).transform

def read(name, filt=None):
    r = shapefile.Reader(os.path.join(RAW, name, name))
    names = [f[0] for f in r.fields[1:]]
    out = []
    for sr in r.iterShapeRecords():
        rec = dict(zip(names, sr.record))
        if filt and not filt(rec): continue
        out.append((rec, make_valid(shape(sr.shape.__geo_interface__))))
    return out

def polys(g):
    if isinstance(g, (Polygon, MultiPolygon)): return g
    flat = []
    for p in getattr(g, "geoms", []):
        if isinstance(p, Polygon): flat.append(p)
        elif isinstance(p, MultiPolygon): flat.extend(p.geoms)
    return unary_union(flat) if flat else GeometryCollection()

def rnd(g, nd=5):
    return json.loads(json.dumps(mapping(g)), parse_float=lambda s: round(float(s), nd))

def write_fc(path, feats, tol):
    fc = {"type": "FeatureCollection", "features": []}
    for props, g in feats:
        gs = polys(g.simplify(tol, preserve_topology=True))
        if gs.is_empty: gs = g
        fc["features"].append({"type": "Feature", "properties": props, "geometry": rnd(transform(to_wgs, gs))})
    with open(path, "w") as f: json.dump(fc, f, separators=(",", ":"))
    return os.path.getsize(path)

def area(g): return transform(to_aea, g).area

# ---- counties
cty = read("cb_2024_us_county_500k", lambda r: r["STATEFP"] == "33")
assert len(cty) == 10, len(cty)
cname = {r["COUNTYFP"]: r["NAME"] for r, _ in cty}

# ---- VTDs -> towns
PFX = re.compile(r"^(Town|Township|City) of ", re.I)
vtd = read("tl_2020_33_vtd20")
print("VTD records:", len(vtd))
groups = defaultdict(list); county_of = {}
dropped = []
for r, g in vtd:
    if r["NAME20"].lower().startswith("voting districts not defined"):
        dropped.append((r["NAME20"], round(area(g) / 1e6, 2))); continue
    t = norm_town(PFX.sub("", r["NAME20"]))
    groups[t].append(g); county_of[t] = cname[r["COUNTYFP20"]]
print("dropped VTDs (name, km2):", dropped)

house_places = {x["town"] for x in csv.DictReader(open(os.path.join(PROC, "district_towns.csv"))) if x["chamber"] == "house"}
# Statute names some wards-cities as one whole town (e.g. Berlin, Derry): merge their ward VTDs into the whole town.
merged = []
for t in list(groups):
    c = city_of(t)
    if c != t and c in house_places and not any(h.startswith(c + " Ward ") for h in house_places):
        groups.setdefault(c, []).extend(groups.pop(t)); county_of[c] = county_of.pop(t); merged.append((t, c))
print("ward VTDs merged into whole-town statute names:", merged)
dupes = {t: len(v) for t, v in groups.items() if len(v) > 1}
print("place names with multiple VTD polygons (merged):", dupes)
town_geom = {t: unary_union(v) for t, v in groups.items()}
miss = sorted(house_places - set(town_geom)); extra = sorted(set(town_geom) - house_places)
print("House places with NO VTD:", miss); print("VTD places not in statute:", extra)

town_feats = sorted((({"town": t, "city": city_of(t), "county": county_of[t]}, g) for t, g in town_geom.items()), key=lambda x: x[0]["town"])
sizes = {"towns": write_fc(os.path.join(GEO, "towns.geojson"), town_feats, TOL_T)}
with open(os.path.join(PROC, "town_centroids.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["town", "lon", "lat"])
    for p, g in town_feats:
        pt = g.representative_point(); w.writerow([p["town"], round(pt.x, 5), round(pt.y, 5)])

# ---- districts
def members(name):
    if name in town_geom: return [name]
    ws = [t for t in town_geom if city_of(t) == name]
    return ws
rows = list(csv.DictReader(open(os.path.join(PROC, "district_towns.csv"))))
dt = defaultdict(list)
for r in rows: dt[(r["chamber"], r["key"])].append(r["town"])
meta = {(r["chamber"], r["key"]): r for r in csv.DictReader(open(os.path.join(PROC, "districts.csv")))}

def dissolve(ch, key):
    gs = []
    for name in dt[(ch, key)]:
        m = members(name)
        if not m: print("  UNMATCHED", ch, key, name)
        gs += [town_geom[x] for x in m]
    return unary_union(gs).buffer(0)

house_g, senate_g = {}, {}
house_feats, senate_feats = [], []
for (ch, key), m in sorted(meta.items()):
    g = dissolve(ch, key)
    if ch == "house":
        house_g[key] = g
        house_feats.append(({"key": key, "district_id": m["district_id"], "county": m["county"], "floterial": m["floterial"] == "True", "seats": int(m["seats"])}, g))
    else:
        senate_g[key] = g
        senate_feats.append(({"key": key, "district_id": m["district_id"]}, g))
house_feats.sort(key=lambda x: (x[0]["county"], int(x[0]["key"].rsplit("-", 1)[1])))
senate_feats.sort(key=lambda x: int(x[0]["key"][1:]))
assert len(house_feats) == 203 and len(senate_feats) == 24, (len(house_feats), len(senate_feats))
county_feats = sorted((({"name": r["NAME"], "fips": r["GEOID"]}, g) for r, g in cty), key=lambda x: x[0]["fips"])
sizes["house"] = write_fc(os.path.join(GEO, "house.geojson"), house_feats, TOL_D)
sizes["senate"] = write_fc(os.path.join(GEO, "senate.geojson"), senate_feats, TOL_D)
sizes["counties"] = write_fc(os.path.join(GEO, "counties.geojson"), county_feats, 0.0008)
print("sizes (bytes):", sizes)

# ---- validation vs TIGER
def sym(a, b):
    a, b = transform(to_aea, a), transform(to_aea, b)
    return a.symmetric_difference(b).area / b.area
res = []
for r, g in read("tl_2024_33_sldl"):
    nm = r["NAMELSAD"].replace("State House District ", "")
    if "not defined" in nm.lower(): print("  dropping undefined SLDL polygon:", nm); continue
    cn, num = nm.rsplit(" ", 1); key = f"{cn}-{int(num)}"
    if key not in house_g or meta[("house", key)]["floterial"] == "True":
        print("  SLDL has no matching base district:", key); continue
    res.append((sym(house_g[key], g), key))
res.sort(reverse=True)
print(f"House base districts compared: {len(res)} (of {sum(1 for k in meta if k[0]=='house' and meta[k]['floterial']!='True')} base); >2%: {sum(1 for x,_ in res if x>0.02)}; median {res[len(res)//2][0]:.4f}")
print("worst 5 House:", [(k, round(x, 4)) for x, k in res[:5]])
print("base districts with no TIGER SLDL polygon:", sorted(k for (c, k), m in meta.items() if c == "house" and m["floterial"] != "True" and k not in {y for _, y in res}))
res = []
for r, g in read("tl_2024_33_sldu"):
    if not r["SLDUST"].strip("0123456789") == "" : print("  dropping non-numeric SLDU", r["SLDUST"]); continue
    key = "S" + str(int(r["SLDUST"]))
    res.append((sym(senate_g[key], g), key))
res.sort(reverse=True)
print(f"Senate compared: {len(res)}; worst 5:", [(k, round(x, 4)) for x, k in res[:5]])
ub = unary_union([g for (c, k), m in meta.items() if c == "house" and m["floterial"] != "True" for g in [house_g[k]]])
uv = unary_union(list(town_geom.values()))
print("union(base House) vs union(VTD) symdiff/area: %.5f" % (transform(to_aea, ub).symmetric_difference(transform(to_aea, uv)).area / transform(to_aea, uv).area))
if os.environ.get("DEBUG"):
    for r, g in read("tl_2024_33_sldl"):
        nm = r["NAMELSAD"].replace("State House District ", "")
        if "not defined" in nm.lower(): continue
        cn, num = nm.rsplit(" ", 1); key = f"{cn}-{int(num)}"
        if key not in house_g: print("TIGER-only", key, meta.get(("house", key))); continue
        d = sym(house_g[key], g)
        if d > 0.02:
            a, b = house_g[key], g
            ours_only = sorted({t for n in dt[("house", key)] for t in members(n) if transform(to_aea, town_geom[t].difference(b)).area / transform(to_aea, town_geom[t]).area > 0.5})
            ti = [t for t, tg in town_geom.items() if transform(to_aea, tg.intersection(b)).area / transform(to_aea, tg).area > 0.5 and t not in {x for n in dt[("house", key)] for x in members(n)}]
            print(key, round(d, 3), meta[("house", key)]["floterial"], "ours-only:", ours_only, "tiger-extra:", ti)
if os.environ.get("DEBUG"):
    wardd = {k for (c, k), v in dt.items() if c == "house" and any(" Ward " in t for t in v)}
    bad = []
    for r, g in read("tl_2024_33_sldl"):
        nm = r["NAMELSAD"].replace("State House District ", "")
        if "not defined" in nm.lower(): continue
        cn, num = nm.rsplit(" ", 1); key = f"{cn}-{int(num)}"
        if key in house_g and sym(house_g[key], g) > 0.02: bad.append(key)
    print("BAD no-ward:", [k for k in bad if k not in wardd]); print("BAD ward:", len([k for k in bad if k in wardd]))
    for k in ("Hillsborough-34","Hillsborough-43","Hillsborough-37"):
        for r, g in read("tl_2024_33_sldl"):
            if r["NAMELSAD"].endswith(k.replace("-"," ")): print(k, "TIGER area km2", round(area(g)/1e6,1), "ours", round(area(house_g[k])/1e6,1))
