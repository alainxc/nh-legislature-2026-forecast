# Data audit: what exists for a New Hampshire Legislature 2026 forecast (as of 2026-11-02)

Checked every item in the brief against the live source. Verdicts: **OK** (official or official-derived, usable as is),
**PARTIAL** (usable with a documented workaround), **GAP** (not available from here; the site says so).

## 1. Election returns by town and ward, 2020-2024

| Item | Verdict | Finding |
|---|---|---|
| NH Secretary of State results pages | **GAP (direct)** | `sos.nh.gov` returns HTTP 403 to every non-browser request and the in-app browser is blocked from the domain by organisation policy. No Wayback snapshot exists for the 2024 results page or any 2026 general-election candidate page (only the 2026 primary pages and the `2026-election-details` stub were archived). |
| OpenElections `openelections-data-nh` | **OK** | Town/ward-level CSVs transcribed from the SoS tabulations for every 2022 and 2024 general-election race (president, governor, US Senate, US House, Executive Council, State Senate, State Representative) plus one combined 2020 general file (president, governor, US Senate, US House, State Senate, State House). Statewide sums match the certified totals to within a few votes (2024 president D 418,488 / R 395,523 vs certified 418,496 / 395,523; 2024 governor 360,149 / 436,122; 2022 governor 256,766 / 352,813; 2022 US Senate 332,490 / 275,631). Cities are reported by ward (Manchester 12, Nashua 9, Concord 10, Dover 6, Rochester 6, Keene 5, Laconia 6, Lebanon 3, Portsmouth 5, Somersworth 5, Franklin 3, Claremont 3, Berlin 4). |
| OpenElections quirks found | **PARTIAL** | (a) The 2020 file carries county-subtotal and `TOTALS` rows that must be dropped (they double the statewide sum). (b) Unincorporated places are spelled differently across years (`Atk. & Gilm. Ac. Gt.` vs `At. & Gil. Academy Grant` vs `Atkinson & Gilmanton Academy Grant`); a name-normalisation table is needed. (c) State Representative files label Dover Ward 3 as Strafford 15 in both years; by statute Dover Ward 2 is Strafford 15 and Dover Ward 3 is Strafford 16, so the row is relabelled. In 2022 the Dover Ward 3 Democratic candidate's votes appear under `Scatter` (1,766 votes). (d) 2022 state-rep rows carry surnames only; 2024 rows carry full names. (e) Party codes include suffix noise (`JR., R`); last token is the party. (f) Floterial districts are suffixed `F` (e.g. `Belknap 8F`). With the Dover fix, the aggregated 2024 seat split reproduces the official 222 R / 178 D and 2022 reproduces 201 R / 199 D to within one or two seats before recount adjustments. |
| MIT Election Data + Science Lab | not needed | Precinct returns exist for 2020 and 2022 but add nothing beyond OpenElections for NH (towns are the precincts); kept as a cross-check reference only. |

## 2. District compositions (towns and wards -> districts)

| Item | Verdict | Finding |
|---|---|---|
| RSA 662:5 (House) | **OK** | The statute text at gencourt.state.nh.us lists all 203 districts by county with their towns/wards and seat counts; parsed total is exactly 400 seats (Hillsborough 45 districts, Rockingham 40, Merrimack 30, Strafford 21, Cheshire 18, Grafton 18, Belknap 8, Carroll 8, Sullivan 8, Coos 7). Floterials are the higher-numbered districts whose towns repeat earlier districts. |
| RSA 662:3 (Senate) | **OK** | All 24 districts by town; three cities are split by ward (Nashua wards 1,2,5 in SD-12 and 3,4,6,7,8,9 in SD-13; Manchester ward 1 in SD-16, 5-9 in SD-18, 2,3,4,10,11,12 in SD-20). |
| Redistricting Data Hub / Dave's Redistricting | not needed | Block-equivalency files require an account; the statutes are the legal definition and match OpenElections' district labels. |

## 3. Boundaries for the map

| Item | Verdict | Finding |
|---|---|---|
| Census TIGER 2024 SLDL/SLDU | **PARTIAL** | SLDL has 165 polygons = the 165 base (non-floterial) House districts; floterials are absent and must be built as unions of their towns. SLDU has the 24 Senate districts (plus one water/undefined polygon). |
| Census cartographic county subdivisions 2024 | **OK** | 259 towns, cities and unincorporated places for a town-level map; cities are single polygons (no wards). |
| Census 2020 VTDs | **OK (caveat)** | 326 voting districts including every city ward, so the map can show wards; ward lines are the 2020 vintage and a few cities adjusted wards in 2021-22. Used for display only, never for vote aggregation. |

## 4. Current membership and vacancies

| Item | Verdict | Finding |
|---|---|---|
| General Court `downloads/Members.txt` | **OK** | Tab-delimited roster with party, county, district, status (Incumbent / new / Former). Senate: 16 R, 8 D in 24 seats. House rows are incomplete (366 sitting members listed vs 382 qualified). |
| House Clerk `RDSE.pdf` (Aug 27, 2026) | **OK** | Official vacancy list: 211 R, 170 D, 1 independent, 18 vacancies (19 resignations, 2 deaths, 3 special elections since Dec 2024). This is the authoritative "current numbers" figure; the brief's "roughly 222 to 178" is the post-2024 count. |
| Wikipedia 2026 NH House page | **OK** | Per-district table of every seat's incumbent with party (220 R / 178 D listed at the seat level), used to assign each seat's holder; cross-checked against RDSE. |

## 5. 2026 candidates

| Item | Verdict | Finding |
|---|---|---|
| SoS general-election candidate list | **GAP (direct)** | Blocked as above and not archived. |
| Ballotpedia chamber pages | **OK (secondary)** | Both chamber pages carry a complete general-election candidate table by district with party columns, seat counts, incumbent `(i)` marks, an `Other` column and notes such as `(unofficially withdrew)` and `Did not make the ballot`. Ballotpedia compiles these from the SoS filings. |
| Wikipedia 2026 Senate page | **OK** | Per-district nominees and incumbent status; used to cross-check Ballotpedia. |

## 6. Polling

| Item | Verdict | Finding |
|---|---|---|
| NH legislative generic ballot | **OK (one poll)** | UNH Survey Center, Sept 17-21 2026, 1,418 LV: NH House control D 49 / R 39, NH Senate D 51 / R 41. The only direct legislative generic ballot found. |
| 2026 governor (Ayotte v Warmington) | **OK** | 17 head-to-head polls on Wikipedia with source links, including UNH Oct 27-31 (48-48), National Public Affairs (R) Oct 25-29, Rasmussen Oct 20-23, Saint Anselm Oct 19-20. |
| NH-01 and NH-02 general-election polls | **OK (thin)** | NH-01 Shaheen v DiLorenzo: 2 polls (Saint Anselm Oct, UNH Sept). NH-02 Goodlander v Tang Williams: 11 polls. Plus two statewide "which party for Congress" polls (Saint Anselm Oct 19-20 D 52-43; NYT/Siena Sept 15-22 D 52-43). |
| National generic ballot 2026 | **OK** | Individual polls (about 700 rows) on Wikipedia's 2026 United States elections page with links. |
| Pollster ratings | **PARTIAL** | FiveThirtyEight's final (2024-methodology) ratings archive on GitHub; Silver Bulletin's current ratings are behind Datawrapper embeds. UNH, Saint Anselm and Emerson are all rated. |
| 2022 backtest polls | **OK** | Wikipedia tables: governor Sununu v Sherman (28), US Senate Hassan v Bolduc (35), NH-01 and NH-02 (7 each) and NH congressional generic (6-7). |
| 2024 backtest polls | **OK** | President Harris v Trump in NH (21), governor Ayotte v Craig (16), NH-01 (8), NH-02 (7). |
| National generic ballot 2022/2024 for backtests | **GAP** | No Wikipedia poll list with URLs survives for those cycles and the FiveThirtyEight CSVs are offline; backtests use NH-specific polls only and say so. |

## 7. Not found / not used

- Seat-level outside ratings for NH legislative districts in 2026 (none published; Sabato and State Navigate rate chamber control only).
- District-level legislative polls (none public).
- Campaign finance by candidate (NH's CFS portal is a JavaScript application without a bulk export reachable from here). Not used.
- Prediction markets (not an input in any case).

## Consequences for the model

1. Town-level baselines are exact for every district (towns and wards are the atoms of NH districts), including floterials, for 2024 president, 2024 governor, 2022 governor, 2022 US Senate and 2020 president.
2. Candidate data rests on Ballotpedia's transcription of SoS filings rather than the filings themselves; the site discloses this on every page that uses it.
3. There is one direct legislative generic-ballot poll, so the statewide environment leans on the governor race (with a large personal-vote correction for Ayotte, who ran 12 points ahead of the 2024 presidential result), the two congressional districts, the statewide congressional preference and the national generic ballot.
4. House 2022 incumbency for the backtest comes from Wikipedia's per-district incumbent column, since 2020 results are on the old map.
