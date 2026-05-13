"""Shared utilities for v3 ingest scripts.

Centralizes:
- Path defaults pointing at the v3 dump + DBs
- Donor canonicalization (re-exports from v2 to keep one source of truth)
- Stance recovery (re-exports from v2)
- Date parsing
- Week-start computation
- finance_flow_v3 column list (for bulk inserts)
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Defaults
DUMP_DIR = REPO_ROOT / "data" / "CalAccess" / "DUMP_2026-05-13" / "CalAccess" / "DATA"
V2_DB = REPO_ROOT / "scraper" / "data" / "finance" / "finance_statewide_v2.db"
V3_DB = REPO_ROOT / "scraper" / "data" / "finance" / "finance_statewide_v3.db"

# Re-export v2 canonicalization + stance recovery so v3 stays in sync
sys.path.insert(0, str(REPO_ROOT / "scraper"))
from scripts.rebuild_finance_db import (  # noqa: E402
    canonicalize_donor,
    recover_stance_from_committee,
    DONOR_ALIAS_PATTERNS,
    COMMITTEE_STANCE_OVERRIDES,
)

# CalAccess null sentinel (two chars: backslash + 'N')
CA_NULL = chr(92) + "N"


def is_null(value: str | None) -> bool:
    """True for CalAccess-null values (empty string or \\N sentinel)."""
    return value is None or value == "" or value == CA_NULL


def parse_calaccess_date(s: str | None) -> Optional[date]:
    """Parse a CalAccess date column. Returns None on parsing failure.

    Accepts:
    - M/D/YYYY or MM/DD/YYYY (the common case in TSV exports)
    - YYYY-MM-DD (ISO; future-safe per Codex round-5)
    - Either with a trailing time suffix (regex is prefix-based)

    Blank/\\N returns None silently.
    """
    if is_null(s):
        return None
    s = (s or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        try:
            mo, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(yr, mo, day)
        except (ValueError, TypeError):
            return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            yr, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(yr, mo, day)
        except (ValueError, TypeError):
            return None
    return None


def week_start_iso(d: date) -> str:
    """Monday-of-week ISO string for a given date."""
    monday = d - timedelta(days=d.weekday())
    return monday.isoformat()


def extract_prop_num(bal_name: str | None, bal_num: str | None) -> Optional[str]:
    """Extract a clean prop number from CalAccess BAL_NUM / BAL_NAME fields.

    Returns e.g. "36", "1A", "22"; None if neither column yields one.
    Lifted from extract_calaccess_finance.py (v2) for parity.
    """
    if not is_null(bal_num):
        m = re.search(r"(\d+[A-Za-z]?)", (bal_num or "").strip())
        if m:
            return m.group(1).lstrip("0") or "0"
    if not is_null(bal_name):
        m = re.search(
            r"PROP(?:OSITION)?\s*[#]?\s*0*(\d+[A-Za-z]?)",
            bal_name or "",
            re.IGNORECASE,
        )
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Attribution dataclass for cover-sheet -> v3 lookup
# ---------------------------------------------------------------------------


@dataclass
class CoverAttribution:
    """Per-FILING_ID resolved attribution from CVR_CAMPAIGN_DISCLOSURE_CD."""

    filing_id: str
    cover_form_type: str
    cover_filer_id: str
    cover_filer_name: str
    cover_committee_id: str
    cover_bal_num: str
    cover_bal_name: str
    cover_bal_juris: str
    cover_sup_opp_cd: str
    cover_elect_date: str
    cover_from_date: str
    cover_thru_date: str
    election_year: Optional[int]
    prop_num: Optional[str]
    finance_campaign_id: Optional[str]  # None if not in v2 crosswalk
    measure_db_id: Optional[int]
    stance: Optional[str]
    attribution_method: str  # 'cover_sheet' | 'crosswalk' | 'inferred' | 'failed'


# ---------------------------------------------------------------------------
# finance_flow_v3 column list (matches schema.sql ordering exactly)
# ---------------------------------------------------------------------------

FLOW_COLUMNS = [
    "finance_campaign_id",
    "source_crosswalk_campaign_id",
    "measure_db_id",
    "stance",
    "receipt_type",
    "amount",
    "txn_date",
    "week_start",
    "source_table",
    "source_form_type",
    "filing_id",
    "amend_id",
    "source_line_item",
    "source_tran_id",
    "source_bakref_tid",
    "source_memo_refno",
    "source_xref_schnm",
    "amount_field_used",
    "row_bal_num",
    "row_bal_name",
    "row_bal_juris",
    "row_sup_opp_cd",
    "cover_form_type",
    "cover_filer_id",
    "cover_filer_name",
    "cover_committee_id",
    "cover_bal_num",
    "cover_bal_name",
    "cover_bal_juris",
    "cover_sup_opp_cd",
    "cover_elect_date",
    "cover_from_date",
    "cover_thru_date",
    "attribution_method",
    "committee_id",
    "committee_name",
    "donor_name_raw",
    "donor_name_canon",
    "reported_filer",
    "payee_name",
    "attribution_source",
    "donor_type",
    "donor_sector",
    "memo_code",
    "source_fingerprint",
    "economic_fingerprint",
    "dedupe_key",
    "quarantine_reason",
]
