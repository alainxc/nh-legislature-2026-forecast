"""Build the 2026 ballot and current seat holders.

Run:  .venv/bin/python -I pipeline/fetch/build_candidates.py
Sources (raw captures, parsed only):
  data/raw/candidates/ballotpedia_nh_{house,senate}_2026.html  general-election candidate tables
      (Ballotpedia's transcription of the SoS filings; the SoS site is unreachable from here)
  data/raw/polls/wiki_nh_house_2026.html   per-seat incumbents (party) for the House
  data/raw/gencourt/Members.txt            General Court roster (Senate holders)
  data/raw/gencourt/RDSE.pdf               House Clerk's resignations/deaths/vacancies list
Writes data/processed/candidates_2026.csv (one row per candidate) and
       data/processed/current_holders.csv (one row per district: D/R/I seats held, vacancies)
"""
import csv, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "processed")

districts = {}
with open(os.path.join(OUT, "districts.csv"), newline="") as f:
    for r in csv.DictReader(f):
        districts[r["key"]] = r
by_name = {(r["chamber"], r["county"], int(r["number"])): r["key"] for r in districts.values() if r["chamber"] == "house"}
by_name.update({("senate", "", int(r["number"])): r["key"] for r in districts.values() if r["chamber"] == "senate"})

BP_COUNTY_FIX = {"Chesire": "Cheshire"}


def parse_ballotpedia(path, chamber):
    s = BeautifulSoup(open(path, encoding="utf8"), "lxml")
    tab = s.select_one("table.candidateListTablePartisan")
    rows = []
    for tr in tab.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) != 4:
            continue
        office = tds[0].get_text(" ", strip=True)
        if chamber == "house":
            m = re.match(r"([A-Za-z]+) (\d+)", office)
            if not m: continue
            county = BP_COUNTY_FIX.get(m.group(1), m.group(1)); num = int(m.group(2))
            key = by_name.get(("house", county, num))
        else:
            m = re.match(r"District (\d+)", office)
            if not m: continue
            key = by_name.get(("senate", "", int(m.group(1))))
        if key is None:
            print("   unmatched office", office); continue
        m = re.search(r"\((\d+) seats?\)", office)
        seats_bp = int(m.group(1)) if m else 1
        if seats_bp != int(districts[key]["seats"]):
            print(f"   seat count mismatch {key}: Ballotpedia {seats_bp} vs statute {districts[key]['seats']}")
        for party, td in (("D", tds[1]), ("R", tds[2]), ("O", tds[3])):
            # candidates on the ballot are <span class="candidate">; withdrawn / did-not-qualify names sit in a trailing div
            for sp in td.select("span.candidate"):
                txt = sp.get_text(" ", strip=True)
                a = sp.find("a")
                name = a.get_text(" ", strip=True) if a else re.sub(r"\(.*?\)", "", txt).strip()
                inc = "(i)" in txt
                note = ""
                m2 = re.search(r"\((unofficially withdrew|withdrew|disqualified)[^)]*\)", txt, re.I)
                if m2: note = m2.group(1).lower()
                label = ""
                if party == "O":
                    m3 = re.search(re.escape(name) + r"\s*\(([^)]*)\)", txt)
                    label = m3.group(1) if m3 else ""
                rows.append(dict(chamber=chamber, key=key, district_id=districts[key]["district_id"], seats=districts[key]["seats"],
                                 party=party, name=name, incumbent=inc, other_label=label, note=note,
                                 source="ballotpedia", source_url="https://ballotpedia.org/" + ("New_Hampshire_House_of_Representatives_elections,_2026" if chamber == "house" else "New_Hampshire_State_Senate_elections,_2026")))
            extra = td.get_text(" ", strip=True)
            for blk in td.find_all("div"):
                t = blk.get_text(" ", strip=True)
                if "Did not make the ballot" in t or "Withdrew" in t or "withdrew" in t:
                    for a in blk.find_all("a"):
                        rows.append(dict(chamber=chamber, key=key, district_id=districts[key]["district_id"], seats=districts[key]["seats"],
                                         party=party, name=a.get_text(" ", strip=True), incumbent=False, other_label="",
                                         note="did not make the ballot" if "Did not make" in t else "withdrew", source="ballotpedia",
                                         source_url=rows[-1]["source_url"] if rows else ""))
    return rows


cands = parse_ballotpedia(os.path.join(RAW, "candidates", "ballotpedia_nh_house_2026.html"), "house")
cands += parse_ballotpedia(os.path.join(RAW, "candidates", "ballotpedia_nh_senate_2026.html"), "senate")
# Other-column candidates whose label includes a major party nomination (e.g. "Independent, Democratic Party",
# "Republican Party, Democratic Party") hold that party's ballot line too; flag it for the model.
for c in cands:
    if c["party"] == "O":
        lab = c["other_label"].lower()
        c["also_dem"] = "democratic" in lab
        c["also_rep"] = "republican" in lab
    else:
        c["also_dem"] = c["also_rep"] = False
with open(os.path.join(OUT, "candidates_2026.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(cands[0].keys())); w.writeheader(); w.writerows(cands)
on_ballot = [c for c in cands if not c["note"]]
for ch in ("house", "senate"):
    sub = [c for c in on_ballot if c["chamber"] == ch]
    print(f"[cands] {ch}: {len(sub)} on ballot (D {sum(1 for c in sub if c['party']=='D')}, R {sum(1 for c in sub if c['party']=='R')}, other {sum(1 for c in sub if c['party']=='O')}), "
          f"incumbents {sum(1 for c in sub if c['incumbent'])}, flagged {sum(1 for c in cands if c['chamber']==ch and c['note'])}")

# ------------------------------------------------------------ holders
# House: Wikipedia 2026 per-seat incumbent table (parsed in build_results -> incumbents_pre.csv, year 2026)
inc = collections.defaultdict(list)
with open(os.path.join(OUT, "incumbents_pre.csv"), newline="") as f:
    for r in csv.DictReader(f):
        if r["year"] == "2026" and r["key"]:
            inc[r["key"]].append(r)
# House vacancies: RDSE.pdf "DECLARED VACANCIES" lines like "3/10/2025   Rock/25"
import pypdf
txt = "\n".join(p.extract_text() for p in pypdf.PdfReader(os.path.join(RAW, "gencourt", "RDSE.pdf")).pages)
ABBR = {"Belk": "Belknap", "Carr": "Carroll", "Ches": "Cheshire", "Coos": "Coos", "Graf": "Grafton", "Hills": "Hillsborough", "Merr": "Merrimack", "Rock": "Rockingham", "Straf": "Strafford", "Sull": "Sullivan"}
vac_section = txt.split("DECLARED VACANCIES:")[1].split("SPECIAL ELECTIONS:")[0]
vacancies = collections.Counter()
for m in re.finditer(r"([A-Za-z]+)/(\d+)", vac_section):
    vacancies[by_name[("house", ABBR[m.group(1)], int(m.group(2)))]] += 1
# who vacated (party) from the RESIGNED / DECEASED lists
vac_party = collections.defaultdict(list)
for sect in ("RESIGNED:", "DECEASED:"):
    body = txt.split(sect)[1].split("\n \n")[0] if sect in txt else ""
    for m in re.finditer(r"([A-Za-z'. -]+), ([A-Za-z'. ]+), ([DRI])\s+(\w+)/(\d+)", body):
        vac_party[by_name[("house", ABBR[m.group(4)], int(m.group(5)))]].append((m.group(1).strip() + ", " + m.group(2).strip(), m.group(3)))
m = re.search(r"TOTAL R: (\d+) TOTAL D: (\d+)\s+TOTAL I: (\d+)", txt); tot = m.groups() if m else None
print(f"[holders] RDSE: {sum(vacancies.values())} vacancies in {len(vacancies)} districts; chamber R {tot[0]} D {tot[1]} I {tot[2]}" if tot else "[holders] RDSE totals not found")

# Senate: Members.txt
sen = {}
with open(os.path.join(RAW, "gencourt", "Members.txt"), encoding="utf-8", errors="replace") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["LegislativeBody"] == "S":
            sen[by_name[("senate", "", int(r["District"]))]] = (f"{r['FirstName']} {r['LastName']}".strip(), r["party"].upper())

hold_rows = []
for key, d in districts.items():
    if d["chamber"] == "senate":
        name, party = sen[key]
        hold_rows.append(dict(chamber="senate", key=key, seats=1, d_held=int(party == "D"), r_held=int(party == "R"), i_held=int(party not in "DR"), vacant=0,
                              holders=f"{name} ({party})", vacated_by="", source="gencourt Members.txt"))
    else:
        members = inc.get(key, [])
        seats = int(d["seats"])
        # the Wikipedia table lists the 2024 winners (and later special-election winners); subtract the Clerk's vacancies
        v = vacancies.get(key, 0)
        vp = vac_party.get(key, [])
        # members who resigned or died (Clerk's list) are dropped from the seat-holder list if the
        # Wikipedia table still names them; otherwise the vacancy is simply added
        def sn(n):
            last = n.split(",")[0].strip() if "," in n else re.sub(r"\s+(Jr|Sr|II|III)\.?$", "", n.strip())
            return re.sub(r"[^a-z]", "", last.split()[-1].lower())
        gone = {sn(n) for n, _ in vp}
        members = [m for m in members if sn(m["name"]) not in gone]
        parties = collections.Counter(m["party"] for m in members)
        listed = sum(parties.values())
        if listed + v > seats:
            # the table names more people than seats (a replaced member still listed): keep the first `seats - v`
            members = members[:max(seats - v, 0)]
            parties = collections.Counter(m["party"] for m in members); listed = sum(parties.values())
        if listed + v != seats:
            # table and vacancy list disagree (special elections, late changes): note it
            note = f"listed {listed}+{v} vacant != {seats} seats"
        else:
            note = ""
        hold_rows.append(dict(chamber="house", key=key, seats=seats, d_held=parties.get("D", 0), r_held=parties.get("R", 0), i_held=parties.get("I", 0), vacant=v,
                              holders="; ".join(f"{m['name']} ({m['party']})" for m in members), vacated_by="; ".join(f"{n} ({p})" for n, p in vp),
                              source="wikipedia 2026 page per-seat table + House Clerk RDSE.pdf" + (" | " + note if note else "")))
with open(os.path.join(OUT, "current_holders.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(hold_rows[0].keys())); w.writeheader(); w.writerows(hold_rows)
h = [r for r in hold_rows if r["chamber"] == "house"]
print(f"[holders] House: D {sum(r['d_held'] for r in h)} R {sum(r['r_held'] for r in h)} I {sum(r['i_held'] for r in h)} vacant {sum(r['vacant'] for r in h)} (sum {sum(r['d_held']+r['r_held']+r['i_held']+r['vacant'] for r in h)}); mismatched districts: {[r['key'] for r in h if 'listed' in r['source']]}")
s_ = [r for r in hold_rows if r["chamber"] == "senate"]
print(f"[holders] Senate: D {sum(r['d_held'] for r in s_)} R {sum(r['r_held'] for r in s_)}")
