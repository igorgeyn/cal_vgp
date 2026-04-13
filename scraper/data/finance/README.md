# Campaign Finance Data

## Pipeline

1. Download raw CAL-ACCESS data from https://www.sos.ca.gov/campaign-lobbying/helpful-resources/raw-data-campaign-finance-and-lobbying-activity
2. Extract: `python scripts/extract_calaccess_finance.py --calaccess-dir /path/to/CalAccess/DATA`
3. Build DB: `python scripts/build_statewide_prop_finance_db.py`
4. Regen site: `python scripts/generate_site.py --force`

## Current State (April 2026)

- 2,083,808 ballot measure receipts extracted from CAL-ACCESS
- 622,916 mapped to CalBallot statewide measure IDs
- **1,460,892 skipped (no matching measure_id)** — these need attention

## TODO: Recover Skipped Receipts

The 1.46M skipped rows are receipts for ballot measure committees that couldn't be matched
to CalBallot measure IDs. Likely causes:

1. **Local/county measures** — CAL-ACCESS covers both statewide and local ballot measures,
   but the current crosswalk only maps statewide propositions (PROP_1 through PROP_99 etc.)
2. **Pre-1998 measures** — the CalBallot DB starts at 1998, but CAL-ACCESS has data back to 2000
3. **Non-proposition measures** — measures filed under names rather than prop numbers
   (e.g., "FAIR INSURANCE RESPONSIBILITY ACT" instead of "PROPOSITION 103")
4. **Referendums and initiatives** — filed under BAL_NAME rather than BAL_NUM

To recover these:
- Expand the prop_num → measure_id crosswalk to include local measures
- Add fuzzy name matching for measures filed by name only
- Add pre-1998 statewide measures to the crosswalk if they exist in ICPSR data

The skipped rows are still in `calaccess_raw/ballot_measure_receipts_clean.csv` and can be
re-processed after improving the crosswalk.
