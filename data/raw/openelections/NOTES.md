# OpenElections NH returns: what was collected and caveats

Collected 2026-11-02 from github.com/openelections/openelections-data-nh (town/ward-level transcriptions of the
NH Secretary of State's official tabulations). The SoS site itself (sos.nh.gov) returns HTTP 403 to automated
requests and is blocked by policy in the in-app browser, so these transcriptions are the source of record here.
Scripts: `pipeline/fetch/build_results.py` (town results, legislative results, incumbents), `build_baseline.py`.

- Statewide sums match certified totals to within a few votes: 2024 president D 418,488 / R 395,523 (certified
  418,496 / 395,523); 2024 governor 360,149 / 436,122; 2022 governor 256,766 / 352,813; 2022 US Senate 332,490 /
  275,631; 2020 president 420,125 / 365,654 after dropping the file's county-subtotal and TOTALS rows (certified
  424,937 / 365,660; the Amherst Biden line is missing from the 2020 file, so Amherst's 2020 row is blanked and
  excluded from every district's 2020 component).
- The 2020 file's Governor and US Senate sections double-count several towns and are not used.
- State Representative files: floterials carry an `F` suffix. Dover Ward 3 is labelled Strafford 15 in both years;
  by RSA 662:5 Dover Ward 2 is Strafford 15 and Dover Ward 3 is Strafford 16, so the Dover Ward 3 rows are
  relabelled. In 2022 the Dover Ward 3 Democratic line sits under `Scatter` (1,766 votes), so Strafford 16's 2022
  Democratic candidate is missing; the seat count is still right (one named Republican lost). 2022 rows carry
  surnames only; 2024 rows carry full names. Party codes carry suffix noise ("JR., R"); the last token is the party.
  `I&R` / `I&D` (a candidate with an independent and a major-party nomination) are credited to the major party.
- Seat tallies from these files: 2024 House 222 R / 178 D (matches the official result exactly); 2022 House 203 R /
  197 D versus the official 201 / 199 (two seats differ; recounts changed close multi-member results after the
  tabulation these files reflect). Senate 2022 14 R / 10 D and 2024 16 R / 8 D match.
- Incumbents before each election come from Wikipedia's per-district tables (saved under polls_historical/). The
  2022 table uses the pre-2022 district numbers, so 2022 incumbents are matched by county and surname.
- Unincorporated places are spelled differently across files (`Atk. & Gilm. Ac. Gt.`, `At. & Gil. Academy Grant`,
  `Thompson & Mes's Pur.`); `pipeline/fetch/nh_names.py` maps every spelling to the statute spelling.
- Congressional and Executive Council files are collected but only the congressional races are aggregated (not
  used in the baseline).
