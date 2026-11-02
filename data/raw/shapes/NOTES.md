# Shapefile provenance (all retrieved 2026-11-02)

- `tl_2020_33_vtd20`: Census TIGER/Line 2020 PL voting districts, https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/33_NEW_HAMPSHIRE/33/tl_2020_33_vtd20.zip
- `tl_2024_33_sldl`: TIGER 2024 state house districts (base only, no floterials), https://www2.census.gov/geo/tiger/TIGER2024/SLDL/tl_2024_33_sldl.zip
- `tl_2024_33_sldu`: TIGER 2024 state senate districts, https://www2.census.gov/geo/tiger/TIGER2024/SLDU/tl_2024_33_sldu.zip
- `cb_2024_33_cousub_500k`, `cb_2024_us_county_500k`: cartographic boundary files, https://www2.census.gov/geo/tiger/GENZ2024/shp/

## Caveats
- Ward lines are 2020 vintage. Several cities adjusted wards in 2021-22, so ward shapes are display-only; ward-split House districts will not match TIGER SLDL exactly.
- The VTD file splits Berlin (3) and Derry (4) into wards; the statute names them as whole towns, so `build_geo.py` merges them.
- VTD "Voting Districts Not Defined" (112.9 km2, water) is dropped. TIGER SLDU "ZZZ" and SLDL "not defined" polygons are dropped.
- "Wentworth Location" (VTD) is aliased to the statute "Wentworth's Location" in `pipeline/fetch/nh_names.py`.

## Validation (build_geo.py, symmetric difference / TIGER area, equal-area projection)
- All 320 statute House place names match exactly one town feature; no unmatched names.
- 164 base House districts vs TIGER SLDL: median ~0.00; 121 under 2%; 43 over 2%, 42 of them contain city wards (ward-vintage differences); the other is Rockingham-24 (Greenland|Rye, 17%). Worst: Merrimack-17 (4.0, Concord ward split), Merrimack-16 0.66, Cheshire-1 0.57, Strafford-17 0.44, Hillsborough-6 0.41.
- Senate vs TIGER SLDU: all 24 compared; worst S13 9.1%, S24 6.0%, S20 1.3%, S12 0.8%, S18 0.5% (ward-related); the rest under 0.5%.
- Union of base House districts equals union of VTDs (symdiff 0.00000).
