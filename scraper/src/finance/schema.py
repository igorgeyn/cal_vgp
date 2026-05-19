"""
Finance database schema for statewide proposition campaign finance data.

Separate SQLite database — does not modify the main ballot_measures.db.

V2 schema (rebuilt 2026-05-04). Keyed on year-scoped `finance_campaign_id`
(e.g. "PROP_16_2020") to fix the cross-cycle contamination in the v1 DB.
See `scraper/scripts/rebuild_finance_db.py` for the build process and
`plans/finance-panel-redesign.md` for the rebuild story.
"""
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
FINANCE_DB_PATH = DATA_DIR / "finance" / "finance_statewide_v2.db"
# v3 expanded-scope DB (loans + in-kind + IE on top of monetary). Read-only
# from the application layer until the atomic UI flip in Phase 5. Built by
# scripts/v3/ingest_* + dedup_ies.py + rebuild_derived.py.
FINANCE_DB_V3_PATH = DATA_DIR / "finance" / "finance_statewide_v3.db"
# Old contaminated DB kept as audit artifact; not consumed by any live code.
FINANCE_DB_LEGACY_PATH = DATA_DIR / "finance" / "finance_statewide.db"

# Schema is built by scripts/rebuild_finance_db.py from
# data/finance/calaccess_raw/ballot_measure_receipts_clean.csv plus the
# (prop_num, election_year) -> measure_db_id crosswalk at
# data/finance/finance_crosswalk.csv. The v2 tables:
#
#   finance_campaign          — the crosswalk indexed in SQLite (PK)
#   finance_summary           — per (campaign, stance): receipts, committees, HHI
#   finance_top_donors        — per (campaign, stance, donor): canonicalized
#   finance_timeline_weekly   — per (campaign, stance, week_start)
#   finance_row_quarantine    — rejected source rows with reason code (audit)
