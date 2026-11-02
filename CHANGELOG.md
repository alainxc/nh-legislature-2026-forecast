# Changelog

## Model runs

- **2026-11-02 model run** — Senate: D control 15%, mean 10.5 D seats of 24. Statewide generic legislative margin D+2.9 from 186 polls. 40,000 simulations.

## Changes to model, config, or data

- **2026-11-02 v1.0 (Senate)** — Initial release for the State Senate: exact town-level baselines (2024 president, 2024 governor, 2022 US Senate, 2022 governor, 2020 president) aggregated to districts from RSA 662:3; candidates from Ballotpedia's transcription of the Secretary of State filings; statewide environment from the UNH legislative generic ballot, the governor's race (Ayotte personal-vote corrected), NH-01/NH-02, the statewide congressional preference and the national generic ballot; a legislative-vs-top-of-ticket offset of 5 points; 40,000-run Monte Carlo with statewide, regional and district error; backtests on 2022 and 2024. All weights in `config/model_config.yaml`.
