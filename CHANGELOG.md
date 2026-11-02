# Changelog

## Model runs

- **2026-11-02 model run** — Senate: D control 15%, mean 10.5 D seats of 24. House: D control 50%, mean 202.2 D seats of 400. Statewide generic legislative margin D+2.9 from 186 polls. 40,000 simulations.

- **2026-11-02 model run** — Senate: D control 15%, mean 10.5 D seats of 24. Statewide generic legislative margin D+2.9 from 186 polls. 40,000 simulations.

## Changes to model, config, or data

- **2026-11-02 v1.1 (House)** — Added the State House: all 203 districts (164 base, 39 floterial) simulated at the candidate level. Each candidate's share is the district party share plus 2.5 points for incumbents plus a candidate deviation (SD 3.5 points, estimated from the 2022/2024 within-district spread of same-party candidates); the top k by share win. Short slates lose seats mechanically; districts with no more candidates than seats are fixed. Town-level map with Senate, House and town views; swing slider now re-simulates both chambers on a half-point grid. House backtests added (2022: 89% of seat events called, 197 actual vs 169 forecast; 2024: 93%, 178 actual vs 198 forecast).
- **2026-11-02 v1.0 (Senate)** — Initial release for the State Senate: exact town-level baselines (2024 president, 2024 governor, 2022 US Senate, 2022 governor, 2020 president) aggregated to districts from RSA 662:3; candidates from Ballotpedia's transcription of the Secretary of State filings; statewide environment from the UNH legislative generic ballot, the governor's race (Ayotte personal-vote corrected), NH-01/NH-02, the statewide congressional preference and the national generic ballot; a legislative-vs-top-of-ticket offset of 5 points; 40,000-run Monte Carlo with statewide, regional and district error; backtests on 2022 and 2024. All weights in `config/model_config.yaml`.
