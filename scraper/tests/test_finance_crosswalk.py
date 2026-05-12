"""
Tests for the year-lookback matcher in scripts/build_finance_crosswalk.py.

Codex-flagged scenarios (round 4): conservative-only neighbor matching,
ambiguity-handling, audit-note preservation, MAX_YEAR_LOOKBACK boundary.
"""
import sys
from pathlib import Path

# scripts/ isn't a package by default; add the repo root so we can import it.
SCRAPER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRAPER_ROOT))

from scripts.build_finance_crosswalk import (  # noqa: E402
    MAX_YEAR_LOOKBACK,
    resolve_pair,
)


def _candidate(measure_db_id: int, mid: str, election_date: str, match_via: str = "title_short"):
    """Build a single measures-index candidate dict (matches the shape that
    `load_measures_index` produces internally)."""
    return {
        "measure_db_id": measure_db_id,
        "measure_id": mid,
        "election_date": election_date,
        "title": f"Proposition {mid}",
        "match_via": match_via,
    }


def test_exact_year_match_returns_matched():
    """Happy path: (prop_num, year) is in the index → matched, no offset."""
    index = {
        ("22", 2020): [_candidate(123, "PROP_22", "2020-11-03", match_via="short_form")],
    }
    out = resolve_pair("22", 2020, index)
    assert out["status"] == "matched"
    assert out["measure_db_id"] == 123
    assert out["match_via"] == "short_form"  # no year_offset_ prefix
    assert "year-offset" not in (out["notes"] or "").lower()


def test_year_offset_1_recovers_single_neighbor():
    """Schwarzenegger pattern: CalAccess year=2006 but ICPSR has it as 2005."""
    index = {
        ("73", 2005): [_candidate(1165, "CA1143", "2005-11-08")],
    }
    out = resolve_pair("73", 2006, index)
    assert out["status"] == "matched"
    assert out["measure_db_id"] == 1165
    assert out["match_via"].startswith("year_offset_1_")
    assert "1-year lookback" in (out["notes"] or "")


def test_year_offset_2_recovers_single_neighbor():
    """PROP_4_2010 pattern: late filings actually attach to 2008's Prop 4."""
    index = {
        ("4", 2008): [_candidate(1189, "CA1167", "2008-11-04")],
    }
    out = resolve_pair("4", 2010, index)
    assert out["status"] == "matched"
    assert out["measure_db_id"] == 1189
    assert out["match_via"].startswith("year_offset_2_")
    assert "2-year lookback" in (out["notes"] or "")


def test_year_offset_stops_at_first_non_empty_neighbor():
    """If both year-1 and year-2 have candidates, only the closer year wins —
    no skipping over a populated neighbor to find a cleaner match further out.
    """
    index = {
        # year-1: ambiguous (would bail)
        ("4", 2009): [
            _candidate(2001, "CA2001", "2009-11-03"),
            _candidate(2002, "CA2002", "2009-06-08"),
        ],
        # year-2: clean single match (but we shouldn't reach it)
        ("4", 2008): [_candidate(1189, "CA1167", "2008-11-04")],
    }
    out = resolve_pair("4", 2010, index)
    assert out["status"] == "missing", "Ambiguity at first non-empty offset must bail, not skip"


def test_year_offset_ambiguity_bails_to_missing_with_note():
    """Multiple candidates in the neighbor year → missing (refuse to guess)
    with the ambiguity reason preserved in notes for the audit trail.
    """
    index = {
        ("4", 2008): [
            _candidate(2001, "CA2001", "2008-11-04"),
            _candidate(2002, "CA2002", "2008-06-03"),
        ],
    }
    out = resolve_pair("4", 2010, index)
    assert out["status"] == "missing"
    note = (out["notes"] or "").lower()
    assert "ambiguous" in note or "2-year-prior" in note, (
        f"Expected ambiguity note to survive, got: {out['notes']!r}"
    )


def test_no_neighbor_at_any_offset_returns_clean_missing():
    """When nothing matches at year/year-1/year-2, status=missing with the
    generic notes (no spurious ambiguity reference).
    """
    index = {
        # Some other prop in the same era; this prop_num is entirely absent.
        ("99", 2008): [_candidate(9999, "CA9999", "2008-11-04")],
    }
    out = resolve_pair("4", 2010, index)
    assert out["status"] == "missing"
    assert out["measure_db_id"] is None
    assert out["notes"] == "no measures-DB record"


def test_lookback_does_not_exceed_max_year_lookback():
    """A match older than MAX_YEAR_LOOKBACK years should not be recovered."""
    # Place a single matching candidate just beyond the lookback horizon.
    too_far_year = 2010 - (MAX_YEAR_LOOKBACK + 1)
    index = {
        ("4", too_far_year): [_candidate(7777, "CA7777", f"{too_far_year}-11-04")],
    }
    out = resolve_pair("4", 2010, index)
    assert out["status"] == "missing", (
        f"Match at year-{MAX_YEAR_LOOKBACK + 1} must not be accepted "
        f"(MAX_YEAR_LOOKBACK={MAX_YEAR_LOOKBACK})"
    )


def test_id_based_preference_within_recovery():
    """If a neighbor year has both an id-based match and a title-only match,
    the id-based one wins (same preference rule as the exact-year path).
    """
    index = {
        ("22", 2005): [
            _candidate(5555, "CA5555", "2005-11-08", match_via="title_short"),
            _candidate(6666, "PROP_22", "2005-11-08", match_via="short_form"),
        ],
    }
    out = resolve_pair("22", 2006, index)
    assert out["status"] == "matched"
    assert out["measure_db_id"] == 6666  # the short_form match
