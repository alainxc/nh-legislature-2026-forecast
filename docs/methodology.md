## The short version

This forecast estimates how the November 3, 2026 elections for the New Hampshire General Court are likely to turn out: who wins each of the 24 State Senate seats, how many of the 400 State House seats each party wins in each of the 203 House districts, and therefore how likely each party is to hold a majority (13 senators, 201 representatives). It is built only from public data, every input to every district is shown on that district's page, and the election is simulated 40,000 times.

Four things make New Hampshire different from most states, and the model handles each one explicitly:

- **Everything is on the ballot.** All 24 Senate seats and all 400 House seats are elected every two years. There are no holdovers to count.
- **Towns are the atoms.** Districts are built from whole towns and city wards, and results are reported by town and ward. So a district's past vote in any statewide race can be computed exactly, including for floterial districts, instead of being estimated from precinct splits.
- **The House uses multi-member districts.** About half of the House districts elect two or more members, up to eleven, and voters cast as many votes as there are seats. Parties often field fewer candidates than there are seats. On top of the base districts sit 39 floterial districts that overlap several base districts and elect 58 additional members from the combined area. The model simulates individual candidates, not just parties.
- **There is no legislative polling to speak of.** One poll (UNH Survey Center) asked which party people want to control the legislature. The statewide environment therefore has to be built from the governor's race, the two congressional races and the national generic ballot, with corrections for how much those differ from a generic legislative race.

## 1. District baselines

For each district and each reference race we add up the votes of its towns and wards and compute the two-party Democratic margin, then subtract the statewide margin in the same race. That difference is the district's lean. Leans from the 2024 presidential (weight 40%), 2024 governor (15%), 2022 U.S. Senate (20%), 2022 governor (10%) and 2020 presidential (15%) races are averaged. A whole-city entry in a Senate district expands to all of that city's wards.

The district's own most recent legislative result is also turned into a lean, by subtracting that year's statewide legislative environment and removing the incumbency bonus the then-incumbents enjoyed, and blended at 30% when the race was contested. In multi-member districts the "district margin" is the party margin: the mean votes of a Democratic candidate against the mean votes of a Republican candidate, which is unaffected by how many candidates each side fielded.

## 2. The statewide environment

The anchor is the 2024 presidential result in New Hampshire (Harris by 2.8 points, two-party). The model forecasts a statewide "generic legislative" margin for 2026 and applies the difference as a uniform swing to every district. The generic margin is a blend of polls and a structural prior:

- **Structural prior.** The president's party loses ground in midterms; the prior is the 2024 result plus 4 points toward the out-party, worth the equivalent of 1,500 poll respondents. Once a few thousand people have been polled, the polls dominate.
- **New Hampshire legislative generic ballot.** UNH's question on which party should control the NH House and Senate is used directly. It carries the largest weight because it asks exactly the right question, but there is only one such poll.
- **Governor.** Kelly Ayotte ran 12 points ahead of the 2024 presidential result in 2024. Incumbent governors in New Hampshire keep most of such a personal vote, so 10 points are subtracted from her polled margin and only half of the remaining signal is passed through.
- **Congressional races.** Polls of NH-01 and NH-02 are averaged after removing an incumbency bonus (NH-02's Democrat is an incumbent; NH-01 is open), and statewide "which party for Congress" polls are used with an 80% pass-through.
- **National generic ballot.** Shifted by New Hampshire's lean relative to the country in 2024 (4.3 points more Democratic) and passed through at 80%.

Within each type, polls are weighted by recency (half-life 14 days), sample size (square root), pollster quality (FiveThirtyEight's final numeric grades), and sponsorship (partisan-sponsored polls get half weight and are shifted 2 points against the sponsor); a pollster's second and later polls count progressively less.

**The legislative offset.** New Hampshire legislative candidates systematically run behind their party's statewide ticket: in 2022 the vote-weighted party margin across contested legislative districts was about 8 points more Republican than the U.S. Senate and U.S. House vote, and in 2024 about 5 points more Republican than the presidential vote. Part of that is the Republican incumbency advantage built up over two cycles, part is ticket-splitting in a state with a long tradition of it. The model subtracts 5 points from the generic margin to get the generic legislative margin. The backtests (which use only pre-election data) missed the actual legislative environment by about 3 points toward Democrats in 2022 and 4 points toward Republicans in 2024 with this offset, which is why it is set where it is and why the statewide error term is 4 points.

The environment page shows every poll, its weight, and each step of this calculation.

## 3. Candidates

- **Senate.** Incumbents get 3 points. An incumbent who ran ahead of their district's lean last time keeps 35% of that over-performance, capped at 6 points. A seat with only one major-party candidate is fixed at a 99.5% win probability. Where a major party has no nominee but an independent is on the ballot, the independent is modelled as the challenger from what a generic candidate of the missing party would get, minus a 6-point penalty.
- **House.** Each candidate's share is the party's share (from the district party margin) plus 2.5 points if an incumbent, plus a candidate-specific deviation drawn from a normal distribution whose spread (about 3.3 points) is estimated from how far same-party candidates finished apart in the same districts in 2022 and 2024. Within those districts incumbents ran about 3 points ahead of same-party non-incumbents, which is where the incumbency figure comes from. The top k candidates by share win the district's k seats. If a party fields fewer candidates than seats, it cannot win more seats than it has candidates; the other party's extra lines fill the remainder, which is exactly what happens in New Hampshire. Independents are placed with the weaker major party minus a 6-point penalty. A district where the number of candidates equals the number of seats is fixed: everyone wins.

Candidate lists come from Ballotpedia's transcription of the Secretary of State filings, because the Secretary of State's site cannot be reached from the machine that builds this site. Every district page says so.

## 4. Simulation

The simulation draws three layers of error, shared across both chambers: a statewide miss common to every district (SD 4 points, Student-t with 5 degrees of freedom so a large systematic polling miss is a live possibility), a regional miss shared by districts in the same region (SD 2 points; the regions are the North Country, Upper Valley, Lakes Region, Greater Manchester, Nashua and the Massachusetts border, Seacoast and Strafford, Concord and the Merrimack Valley, and the Monadnock region), and district-specific noise (SD 6 points for Senate seats, 5 points for House district party margins, plus the candidate-level deviations above). Open seats and districts without a recent contested result get a little extra uncertainty.

Chamber control is read off each simulation. The House total is the sum over 203 districts of the Democratic seats won in that simulation, so the correlation between neighbouring districts and between a town's base and floterial seats is carried through naturally.

## 5. The "what if the polls are off" slider

The slider fixes the statewide generic legislative vote at a chosen value and re-simulates both chambers with the regional, district and candidate error still in play; the curve is precomputed on a half-point grid and interpolated in the browser. The preset buttons apply the statewide misses measured in the 2022 and 2024 backtests, so "2022-style miss" means polls that understated Democrats by the amount they did that year, and "2024-style miss" the reverse.

## 6. Backtests

The model is run on the 2022 and 2024 elections using only what existed three days before each: district leans from earlier statewide races (only the 2020 presidential race for 2022, the first election on the current map), the ballot and incumbency from the results and the pre-election incumbent lists, and New Hampshire polls of the governor's race, the U.S. Senate or presidential race and the two congressional districts. No national generic-ballot poll list with sources survives for those cycles, so it is left out of the backtests and the backtest says so. The Backtests page reports seats called, Brier scores, margin error and interval coverage for the Senate; and for the House, the accuracy of "Democrats win at least j seats" in each contested district, how often the exact seat split was right, the chamber total, and the statewide miss.

## Known limitations and weakest assumptions

- **One legislative generic-ballot poll.** The environment leans on races with their own candidate effects. The governor correction (10 points) is the single most consequential assumption; the environment page shows what each source implies so readers can judge it.
- **The legislative offset** of 5 points is estimated from two elections. It is centred between them but either cycle alone would move it by 3 to 4 points, which is why the statewide error term is wide.
- **Candidate quality is unobserved.** Beyond incumbency, the model knows nothing about individual House candidates: no fundraising, no district polls, no outside ratings exist for New Hampshire legislative seats in 2026.
- **Candidate lists are second-hand.** Ballotpedia is reliable but is not the official filing list; late withdrawals may be missed.
- **Vacancies.** Eighteen House seats are vacant; "held by" counts use the House Clerk's list of August 27, 2026.
- **Map wards.** Ward boundaries on the map are the 2020 Census vintage; a few cities adjusted wards in 2021-22. Vote aggregation never uses the map.
