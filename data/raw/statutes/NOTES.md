# District compositions

RSA 662:5 (House) and RSA 662:3 (Senate), as enacted in 2022, fetched from gencourt.state.nh.us on 2026-11-02 and
parsed by `pipeline/fetch/build_districts.py`. The House statute lists towns without separators, so it is tokenised
against the place-name vocabulary from the Senate statute; abbreviations ("E. Kingston", "S. Hampton", "N. Hampton")
are expanded. Floterials are identified by the rule that base districts partition each county's towns exactly once;
the SoS tabulations' `F` labels mislabel Cheshire 14 and Grafton 16 as floterial and omit Hillsborough 44 and
Strafford 18. Result: 203 districts, 39 floterial (58 seats), 400 seats; 24 Senate districts.
