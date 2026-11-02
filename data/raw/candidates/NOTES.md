# 2026 candidates: provenance and caveats

The Secretary of State's general-election candidate list could not be fetched (sos.nh.gov blocks automated
access and the in-app browser is blocked from the domain by policy; no Wayback snapshot of a 2026 general-election
candidate page exists). Ballotpedia's chamber election pages, which transcribe the SoS filings, are used instead
(captured 2026-11-02). Parsed by `pipeline/fetch/build_candidates.py`.

- House: 716 candidates on the ballot across 203 districts (373 D, 330 R, 13 other), 279 marked incumbents.
  Senate: 46 (23 D, 23 R), 22 incumbents. Candidates listed under "Did not make the ballot" or marked
  "(unofficially withdrew)" are kept in `candidates_2026.csv` with a `note` and excluded from the model. Senate
  District 6's Democrat (Cecil Abels) is marked as unofficially withdrawn by Ballotpedia; the seat is treated as
  uncontested for the Republican incumbent, which may overstate his certainty if the name remains on the ballot.
- Candidates in Ballotpedia's "Other" column whose label includes a major party (e.g. "Independent, Democratic
  Party", "Republican Party, Democratic Party") hold that party's line too and are credited to it; pure independents
  and minor-party candidates are modelled as independents.
- Incumbency marks `(i)` are Ballotpedia's; House incumbents elected in a different district are not flagged.
- Ballotpedia spells Cheshire as "Chesire" in its anchors; fixed in parsing.
