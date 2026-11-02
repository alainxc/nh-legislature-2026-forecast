"""Write data/raw/<topic>/MANIFEST.json for every raw capture: file, source_url, retrieved_at, description."""
import os, json, glob, datetime as dt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
OE = "https://raw.githubusercontent.com/openelections/openelections-data-nh/master/"
W = "https://en.wikipedia.org/wiki/"
URLS = {
 "openelections/20201103__nh__general__precinct.csv": (OE + "2020/20201103__nh__general__precinct.csv", "2020 general election by town (president, governor, US Senate, US House, State Senate, State House), transcribed from NH SoS tabulations by OpenElections. Only the presidential race is used (other sections double-count towns)."),
 "openelections/20221108__nh__general__governor__precinct.csv": (OE + "2022/20221108__nh__general__governor__precinct.csv", "2022 governor by town/ward (Sununu v Sherman)."),
 "openelections/20221108__nh__general__us__senate__precinct.csv": (OE + "2022/20221108__nh__general__us__senate__precinct.csv", "2022 US Senate by town/ward (Hassan v Bolduc)."),
 "openelections/20221108__nh__general__congressional__precinct.csv": (OE + "2022/20221108__nh__general__congressional__precinct.csv", "2022 US House by town/ward."),
 "openelections/20221108__nh__general__executive__council__precinct.csv": (OE + "2022/20221108__nh__general__executive__council__precinct.csv", "2022 Executive Council by town/ward (not used)."),
 "openelections/20221108__nh__general__state__senate__precinct.csv": (OE + "2022/20221108__nh__general__state__senate__precinct.csv", "2022 State Senate by town/ward and district."),
 "openelections/20221108__nh__general__state__representative__precinct.csv": (OE + "2022/20221108__nh__general__state__representative__precinct.csv", "2022 State Representative by town/ward and district (floterials suffixed F; Dover Ward 3 mislabelled as Strafford 15, fixed in processing; candidate surnames only)."),
 "openelections/20241105__nh__general__president__precinct.csv": (OE + "2024/20241105__nh__general__president__precinct.csv", "2024 president by town/ward."),
 "openelections/20241105__nh__general__governor__precinct.csv": (OE + "2024/20241105__nh__general__governor__precinct.csv", "2024 governor by town/ward (Ayotte v Craig)."),
 "openelections/20241105__nh__general__congressional__precinct.csv": (OE + "2024/20241105__nh__general__congressional__precinct.csv", "2024 US House by town/ward."),
 "openelections/20241105__nh__general__executive__council__precinct.csv": (OE + "2024/20241105__nh__general__executive__council__precinct.csv", "2024 Executive Council by town/ward (not used)."),
 "openelections/20241105__nh__general__state__senate__precinct.csv": (OE + "2024/20241105__nh__general__state__senate__precinct.csv", "2024 State Senate by town/ward and district."),
 "openelections/20241105__nh__general__state__representative__precinct.csv": (OE + "2024/20241105__nh__general__state__representative__precinct.csv", "2024 State Representative by town/ward and district (same Dover Ward 3 label fix)."),
 "openelections/README_openelections.md": ("https://github.com/openelections/openelections-data-nh", "OpenElections NH repository README (file conventions)."),
 "statutes/rsa_662-5_house_districts.html": ("https://gencourt.state.nh.us/rsa/html/LXIII/662/662-5.htm", "RSA 662:5 State Representative districts: towns/wards and seats per district (2022 redistricting)."),
 "statutes/rsa_662-3_senate_districts.html": ("https://gencourt.state.nh.us/rsa/html/LXIII/662/662-3.htm", "RSA 662:3 State Senate districts: towns and wards per district."),
 "statutes/rsa_662-2_councilor_districts.html": ("https://gencourt.state.nh.us/rsa/html/LXIII/662/662-2.htm", "RSA 662:2 Executive Council districts (not used)."),
 "gencourt/Members.txt": ("https://gencourt.state.nh.us/downloads/Members.txt", "General Court member roster download: name, body, county, district, party, status."),
 "gencourt/RDSE.pdf": ("https://www.gencourt.state.nh.us/house/aboutthehouse/RDSE.pdf", "House Clerk: resignations, deaths, special elections and declared vacancies, 2025-26 session (Aug 27, 2026 update)."),
 "gencourt/senate_roster.html": ("https://gencourt.state.nh.us/senate/members/senate_roster.aspx", "Senate roster page (cross-check)."),
 "gencourt/house_members.html": ("https://gencourt.state.nh.us/house/members/default.aspx", "House roster page (cross-check; no party shown)."),
 "gencourt/wiki_nh_house_chamber.html": (W + "New_Hampshire_House_of_Representatives", "Wikipedia chamber article: composition (cross-check)."),
 "gencourt/wiki_nh_senate_chamber.html": (W + "New_Hampshire_Senate", "Wikipedia chamber article: composition (cross-check)."),
 "gencourt/ballotpedia_nh_house_chamber.html": ("https://ballotpedia.org/New_Hampshire_House_of_Representatives", "Ballotpedia chamber page (cross-check)."),
 "gencourt/ballotpedia_nh_senate_chamber.html": ("https://ballotpedia.org/New_Hampshire_State_Senate", "Ballotpedia chamber page (cross-check)."),
 "candidates/ballotpedia_nh_house_2026.html": ("https://ballotpedia.org/New_Hampshire_House_of_Representatives_elections,_2026", "Ballotpedia: 2026 general-election candidates by House district with incumbent marks, seat counts, withdrawals (compiled from SoS filings; the SoS site blocks automated access)."),
 "candidates/ballotpedia_nh_senate_2026.html": ("https://ballotpedia.org/New_Hampshire_State_Senate_elections,_2026", "Ballotpedia: 2026 general-election candidates by Senate district."),
 "polls/wiki_nh_gov_2026.html": (W + "2026_New_Hampshire_gubernatorial_election", "Wikipedia: 2026 governor polling tables (Ayotte v Warmington) with source links."),
 "polls/wiki_us_house_nh_2026.html": (W + "2026_United_States_House_of_Representatives_elections_in_New_Hampshire", "Wikipedia: statewide congressional preference polls and NH-01/NH-02 polls."),
 "polls/wiki_nh_house_2026.html": (W + "2026_New_Hampshire_House_of_Representatives_election", "Wikipedia: NH House generic ballot poll (UNH) and the per-seat incumbent table."),
 "polls/wiki_nh_senate_2026.html": (W + "2026_New_Hampshire_Senate_election", "Wikipedia: NH Senate generic ballot poll (UNH) and per-district nominees."),
 "polls/wiki_us_elections_2026.html": (W + "2026_United_States_elections", "Wikipedia: national generic congressional ballot poll tables."),
 "polls/wiki_us_senate_nh_2026.html": (W + "2026_United_States_Senate_election_in_New_Hampshire", "Wikipedia: 2026 US Senate polls (not used as an input)."),
 "polls/wiki_generic_polling_2026.html": (W + "Nationwide_opinion_polling_for_the_2026_United_States_House_of_Representatives_elections", "Checked; page does not exist."),
 "polls_historical/wiki_nh_gov_2022.html": (W + "2022_New_Hampshire_gubernatorial_election", "2022 governor polls (backtest)."),
 "polls_historical/wiki_nh_ussen_2022.html": (W + "2022_United_States_Senate_election_in_New_Hampshire", "2022 US Senate polls (backtest)."),
 "polls_historical/wiki_us_house_nh_2022.html": (W + "2022_United_States_House_of_Representatives_elections_in_New_Hampshire", "2022 NH-01/NH-02 and NH generic ballot polls (backtest)."),
 "polls_historical/wiki_nh_pres_2024.html": (W + "2024_United_States_presidential_election_in_New_Hampshire", "2024 presidential polls in NH (backtest)."),
 "polls_historical/wiki_nh_gov_2024.html": (W + "2024_New_Hampshire_gubernatorial_election", "2024 governor polls (backtest)."),
 "polls_historical/wiki_us_house_nh_2024.html": (W + "2024_United_States_House_of_Representatives_elections_in_New_Hampshire", "2024 NH-01/NH-02 polls (backtest)."),
 "polls_historical/wiki_nh_house_2022.html": (W + "2022_New_Hampshire_House_of_Representatives_election", "Wikipedia: 2022 NH House results by district with pre-election incumbents (incumbency for the 2022 backtest)."),
 "polls_historical/wiki_nh_house_2024.html": (W + "2024_New_Hampshire_House_of_Representatives_election", "Wikipedia: 2024 NH House results by district with pre-election incumbents."),
 "polls_historical/wiki_nh_senate_2022.html": (W + "2022_New_Hampshire_Senate_election", "Wikipedia: 2022 NH Senate results (cross-check)."),
 "polls_historical/wiki_nh_senate_2024.html": (W + "2024_New_Hampshire_Senate_election", "Wikipedia: 2024 NH Senate results (cross-check)."),
 "polls_historical/wiki_us_elections_2022.html": (W + "2022_United_States_elections", "Checked for national generic ballot polls; only aggregates."),
 "polls_historical/wiki_generic_2022.html": (W + "2022_United_States_House_of_Representatives_elections", "Checked for national generic ballot polls; only aggregates."),
 "polls_historical/wiki_generic_2024.html": (W + "2024_United_States_House_of_Representatives_elections", "Checked for national generic ballot polls; only aggregates."),
 "polls_historical/wiki_generic_polling_2022.html": (W + "Nationwide_opinion_polling_for_the_2022_United_States_House_of_Representatives_elections", "Checked; page does not exist."),
 "polls_historical/wiki_generic_polling_2024.html": (W + "Nationwide_opinion_polling_for_the_2024_United_States_House_of_Representatives_elections", "Checked; page does not exist."),
 "ratings/538_pollster_ratings_combined.csv": ("https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/pollster-ratings-combined.csv", "FiveThirtyEight final pollster ratings (2024 methodology): numeric_grade 0-3 used as the pollster quality weight."),
 "ratings/538_pollster_ratings_2023.csv": ("https://raw.githubusercontent.com/fivethirtyeight/data/master/pollster-ratings/2023/pollster-ratings.csv", "FiveThirtyEight 2023 letter-grade ratings (reference)."),
 "shapes/tl_2024_33_sldl.zip": ("https://www2.census.gov/geo/tiger/TIGER2024/SLDL/tl_2024_33_sldl.zip", "Census TIGER 2024 state House (lower) districts: 165 base districts, no floterials (validation)."),
 "shapes/tl_2024_33_sldu.zip": ("https://www2.census.gov/geo/tiger/TIGER2024/SLDU/tl_2024_33_sldu.zip", "Census TIGER 2024 state Senate districts (validation)."),
 "shapes/cb_2024_33_cousub_500k.zip": ("https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_33_cousub_500k.zip", "Census cartographic county subdivisions (towns) 2024."),
 "shapes/cb_2024_us_county_500k.zip": ("https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip", "Census cartographic counties 2024."),
 "shapes/tl_2020_33_vtd20.zip": ("https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/33_NEW_HAMPSHIRE/33/tl_2020_33_vtd20.zip", "Census 2020 voting districts: towns and city wards (map geometry; 2020 ward lines)."),
}
for topic in sorted(os.listdir(RAW)):
    d = os.path.join(RAW, topic)
    if not os.path.isdir(d): continue
    manifest = []
    for path in sorted(glob.glob(os.path.join(d, "**", "*"), recursive=True)):
        if os.path.isdir(path) or path.endswith(("MANIFEST.json", "NOTES.md", ".DS_Store")): continue
        rel = os.path.relpath(path, RAW)
        if rel.startswith("shapes/") and not rel.endswith(".zip"):
            continue   # unzipped members are described by their zip
        url, desc = URLS.get(rel, ("", "UNDESCRIBED"))
        manifest.append({"file": os.path.relpath(path, d), "source_url": url, "retrieved_at": dt.datetime.fromtimestamp(os.path.getmtime(path)).astimezone().isoformat(timespec="seconds"),
                         "description": desc, "bytes": os.path.getsize(path)})
    json.dump(manifest, open(os.path.join(d, "MANIFEST.json"), "w"), indent=1)
    und = [m["file"] for m in manifest if m["description"] == "UNDESCRIBED"]
    print(f"{topic}: {len(manifest)} files" + (f"; UNDESCRIBED: {und}" if und else ""))
