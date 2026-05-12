"""
Tests for FinanceDatabase: resolve_campaign determinism under measure_db_id
collisions, aggregate_for_measure rollup semantics, and the
_actual_election_year helper in rebuild_finance_db.

These tests build a minimal v2-shaped SQLite DB in memory so they're hermetic
(no dependency on whether the real finance_statewide_v2.db is built).
"""
import sqlite3
import sys
from pathlib import Path

import pytest

SCRAPER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRAPER_ROOT))

from src.finance.operations import FinanceDatabase  # noqa: E402
from scripts.rebuild_finance_db import (  # noqa: E402
    _actual_election_year,
    canonicalize_donor,
    recover_stance_from_committee,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

V2_SCHEMA = """
CREATE TABLE finance_campaign (
    finance_campaign_id TEXT PRIMARY KEY,
    prop_num TEXT NOT NULL,
    election_year INTEGER NOT NULL,
    election_month INTEGER,
    measure_db_id INTEGER,
    measure_id TEXT,
    status TEXT NOT NULL,
    match_via TEXT,
    csv_row_count INTEGER,
    csv_total_amount REAL,
    notes TEXT
);
CREATE TABLE finance_summary (
    finance_campaign_id TEXT NOT NULL,
    stance TEXT NOT NULL,
    total_receipts REAL NOT NULL,
    n_committees INTEGER NOT NULL,
    top5_share REAL,
    hhi REAL,
    PRIMARY KEY (finance_campaign_id, stance)
);
CREATE TABLE finance_top_donors (
    finance_campaign_id TEXT NOT NULL,
    stance TEXT NOT NULL,
    donor_name_canon TEXT NOT NULL,
    donor_type TEXT,
    total_amount REAL NOT NULL,
    PRIMARY KEY (finance_campaign_id, stance, donor_name_canon)
);
CREATE TABLE finance_timeline_weekly (
    finance_campaign_id TEXT NOT NULL,
    stance TEXT NOT NULL,
    week_start TEXT NOT NULL,
    weekly_receipts REAL NOT NULL,
    cumulative_receipts REAL NOT NULL,
    PRIMARY KEY (finance_campaign_id, stance, week_start)
);
"""


@pytest.fixture
def fdb(tmp_path):
    """A FinanceDatabase backed by a fresh on-disk SQLite file (in-memory
    connections can't easily be shared with the FinanceDatabase wrapper)."""
    db_path = tmp_path / "test_finance.db"
    raw = sqlite3.connect(str(db_path))
    raw.executescript(V2_SCHEMA)
    raw.commit()
    raw.close()
    db = FinanceDatabase(db_path)
    yield db
    db.close()


def insert_campaign(db, cid, prop_num, year, measure_db_id, match_via="short_form"):
    db.conn.execute(
        "INSERT INTO finance_campaign "
        "(finance_campaign_id, prop_num, election_year, measure_db_id, measure_id, status, match_via) "
        "VALUES (?, ?, ?, ?, ?, 'matched', ?)",
        (cid, prop_num, year, measure_db_id, f"PROP_{prop_num}", match_via),
    )


def insert_summary(db, cid, stance, total_receipts, n_committees=1, top5_share=None, hhi=None):
    db.conn.execute(
        "INSERT INTO finance_summary "
        "(finance_campaign_id, stance, total_receipts, n_committees, top5_share, hhi) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (cid, stance, total_receipts, n_committees, top5_share, hhi),
    )


def insert_donor(db, cid, stance, donor, amount, donor_type="committee"):
    db.conn.execute(
        "INSERT INTO finance_top_donors "
        "(finance_campaign_id, stance, donor_name_canon, donor_type, total_amount) "
        "VALUES (?, ?, ?, ?, ?)",
        (cid, stance, donor, donor_type, amount),
    )


def insert_week(db, cid, stance, week_start, weekly, cumulative):
    db.conn.execute(
        "INSERT INTO finance_timeline_weekly "
        "(finance_campaign_id, stance, week_start, weekly_receipts, cumulative_receipts) "
        "VALUES (?, ?, ?, ?, ?)",
        (cid, stance, week_start, weekly, cumulative),
    )


# ---------------------------------------------------------------------------
# _actual_election_year helper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# canonicalize_donor — alias pattern expansion (Codex round-6 audit)
# ---------------------------------------------------------------------------

class TestDonorCanonicalizationDelaney:
    """M. Quinn Delaney: 5 variants -> 1. Covers both LAST,FIRST-MIDDLE
    and FIRST-MIDDLE-LAST orderings (Codex caution: no broad surname matching)."""

    @pytest.mark.parametrize("variant", [
        "DELANEY, M. QUINN",
        "M. QUINN DELANEY",
        "DELANEY, QUINN",
        "DELANEY, MARY QUINN",
        "DELANEY, M QUINN",
    ])
    def test_variant_canonicalizes(self, variant):
        assert canonicalize_donor(variant) == "M. Quinn Delaney"

    @pytest.mark.parametrize("other_delaney", [
        "DELANEY, JOHN",
        "DELANEY, MARGARET",
        "DELANEY, ROBERT J",
        "OTHER DELANEY FAMILY MEMBER",
    ])
    def test_other_delaneys_left_alone(self, other_delaney):
        """Negative test (Codex caution): broad surname matches must not fire
        on unrelated Delaneys."""
        assert canonicalize_donor(other_delaney) != "M. Quinn Delaney"


class TestDonorCanonicalizationDavita:
    @pytest.mark.parametrize("variant", ["DAVITA", "DAVITA, INC", "DAVITA, INC."])
    def test_davita_variants(self, variant):
        assert canonicalize_donor(variant) == "DaVita"


class TestDonorCanonicalizationPechanga:
    @pytest.mark.parametrize("variant", [
        "PECHANGA BAND OF LUISENO MISSION INDIANS",
        "PECHANGA BAND OF LUISENO INDIANS",
        "PECHANGA BAND OF MISSION INDIANS",
    ])
    def test_pechanga_variants(self, variant):
        assert canonicalize_donor(variant) == "Pechanga Band of Luiseno Mission Indians"


class TestDonorCanonicalizationMungerJr:
    """Charles T. Munger Jr.: 4 unambiguous variants merge. Negative cases
    cover (a) ambiguous form that could be Sr., (b) other Mungers (Molly,
    Nancy, Wendy)."""

    @pytest.mark.parametrize("variant", [
        "MUNGER, JR., CHARLES THOMAS",
        "MUNGER, JR., CHARLES T",
        "CHARLES T. MUNGER, JR",
        "MUNGER, JR., CHARLES",
    ])
    def test_jr_variants_merge(self, variant):
        assert canonicalize_donor(variant) == "Charles T. Munger, Jr."

    def test_ambiguous_no_jr_stays_distinct(self):
        """MUNGER, CHARLES T has no JR anchor; could be Sr.
        Conservative rule: leave distinct."""
        assert canonicalize_donor("MUNGER, CHARLES T") != "Charles T. Munger, Jr."

    @pytest.mark.parametrize("other_munger", [
        "MUNGER, MOLLY",
        "MUNGER, NANCY B",
        "MUNGER, WENDY",
    ])
    def test_other_mungers_stay_distinct(self, other_munger):
        """Different people — never collapse different individuals into one."""
        assert canonicalize_donor(other_munger) != "Charles T. Munger, Jr."


class TestDonorCanonicalizationCAR:
    """California Association of Realtors Issues Mobilization PAC: 9 spelling
    variants merge to one canonical. Parent CAR + National Realtors stay
    distinct (legally separate entities)."""

    @pytest.mark.parametrize("variant", [
        "CALIFORNIA ASSOCIATION OF REALTORS ISSUES MOBILIZATION POLITICAL ACTION COMMITTEE (IMPAC)",
        "CALIFORNIA ASSOCIATION OF REALTORS - ISSUES MOBILIZATION PAC",
        "CALIFORNIA ASSOCIATION OF REALTORS ISSUES MOBILIZATION PAC",
        "CALIFORNIA ASSOCIATION OF REALTORS, ISSUES MOBILIZATION POLITICAL ACTION COMMITTEE (IMPAC)",
        "CALIFORNIA ASSOCIATION OF REALTORS ISSUES MOBILIZATION POLITICAL ACTION COMMITTEE",
        "CALIFORNIA ASSOCIATION OF REALTORS- ISSUES MOBILIZATION PAC",
        "CALIFORNIA ASSOCIATION OF REALTORS ISSUES MOBILIZATION PAC (IMPAC)",
        "CA ASSN OF REALTORS ISSUES MOBILIZATION PAC",
        "CA ASSOCIATION OF REALTORS ISSUES",
    ])
    def test_car_impac_variants_merge(self, variant):
        assert canonicalize_donor(variant) == "California Association of Realtors Issues Mobilization PAC"

    def test_parent_car_stays_distinct(self):
        """Parent association is a separate legal entity from its PAC."""
        result = canonicalize_donor("CALIFORNIA ASSOCIATION OF REALTORS")
        assert result != "California Association of Realtors Issues Mobilization PAC"

    def test_national_realtors_stays_distinct(self):
        """National Association of Realtors is a different national entity."""
        result = canonicalize_donor("NATIONAL ASSOCIATION OF REALTORS")
        assert result != "California Association of Realtors Issues Mobilization PAC"


class TestDonorCanonicalizationInstacart:
    def test_maplebear_dba_canonicalizes(self):
        assert canonicalize_donor("MAPLEBEAR INC., DBA INSTACART") == "Instacart"


class TestDonorCanonicalizationConservativeBounds:
    """End-to-end check that the patterns added in round 2 don't over-merge.
    Codex-blessed scope: legal-entity-level only, no parent-org grouping."""

    def test_seiu_locals_stay_distinct(self):
        """SEIU Local 721 and SEIU Local 1021 are different bargaining units
        — must NOT collapse to a generic 'SEIU' parent. Parent-org grouping
        belongs in the donor-sector classification pass."""
        result_721 = canonicalize_donor("SERVICE EMPLOYEES INTERNATIONAL UNION LOCAL 721 CTW, CLC ISSUES & INITIATIVES")
        result_1021 = canonicalize_donor("SERVICE EMPLOYEES INTERNATIONAL UNION LOCAL 1021")
        assert result_721 != result_1021


# ---------------------------------------------------------------------------
# recover_stance_from_committee — overrides + regex patterns
# ---------------------------------------------------------------------------

def test_stance_override_planned_parenthood_prop4_2008():
    """The broadened PROP_4_2008 / 'PLANNED PARENTHOOD' override fires for
    any PP affiliate (LA County, San Diego, Mar Monte, etc.) — not just the
    LA County name the original override was scoped to."""
    stance, label = recover_stance_from_committee(
        "PLANNED PARENTHOOD ADVOCACY PROJECT LOS ANGELES COUNTY",
        campaign_id="PROP_4_2008",
    )
    assert stance == "oppose"
    assert label and label.startswith("override:")

    stance, _ = recover_stance_from_committee(
        "Planned Parenthood Mar Monte",
        campaign_id="PROP_4_2008",
    )
    assert stance == "oppose"


def test_stance_override_planned_parenthood_prop4_2010_recovered_campaign():
    """Matcher v2 routes late PP filings (CalAccess year 2010) to a separate
    finance_campaign_id PROP_4_2010 — the override must fire for that
    campaign_id too, not just PROP_4_2008. Otherwise the 1,427 PP rows the
    matcher recovered would all sit in unknown_stance."""
    stance, _ = recover_stance_from_committee(
        "PLANNED PARENTHOOD ADVOCACY PROJECT LOS ANGELES COUNTY",
        campaign_id="PROP_4_2010",
    )
    assert stance == "oppose"


def test_stance_override_scoped_per_campaign_no_global_match():
    """The override table is campaign-scoped. PP committees filing on a
    hypothetical OTHER campaign must not auto-recover oppose just because
    of the PROP_4 override — they could legitimately support that measure."""
    stance, label = recover_stance_from_committee(
        "PLANNED PARENTHOOD MAR MONTE",
        campaign_id="PROP_1_2024",  # different campaign, no override
    )
    # Neither the override (different campaign) nor regex (no stance keyword
    # in name) should fire. Stays None → caller quarantines as unknown.
    assert stance is None
    assert label is None


def test_stance_recovery_regex_explicit_no():
    """Existing regex patterns continue to fire — 'NO ON PROPOSITION 4' etc."""
    stance, label = recover_stance_from_committee(
        "NO ON PROPOSITION 4",
        campaign_id="PROP_4_2008",
    )
    assert stance == "oppose"
    assert label == "explicit_no"


def test_stance_recovery_regex_defeat():
    stance, label = recover_stance_from_committee(
        "CREDO VICTORY FUND TO DEFEAT PROPOSITION 4",
        campaign_id="PROP_4_2008",
    )
    assert stance == "oppose"
    assert label == "verb_stop_or_defeat"


def test_stance_recovery_ambiguous_yes_and_no_returns_none():
    """Committees containing both YES ON and NO ON language (rare; usually
    oppositional reframing) are deliberately left ambiguous to avoid
    false-positive recovery."""
    stance, label = recover_stance_from_committee(
        "YES ON 4 AND NO ON 5 COALITION",
        campaign_id="PROP_4_2008",
    )
    assert stance is None
    assert label is None


def test_stance_recovery_no_stance_keyword_returns_none():
    """A committee with no clear stance keyword and no override should leave
    its stance unrecovered — caller quarantines the row."""
    stance, _ = recover_stance_from_committee(
        "Chico Chamber Of Commerce PAC",
        campaign_id="PROP_82_2006",
    )
    assert stance is None


def test_stance_recovery_no_committee_name_returns_none():
    stance, _ = recover_stance_from_committee("", campaign_id="PROP_4_2008")
    assert stance is None
    stance, _ = recover_stance_from_committee(None, campaign_id="PROP_4_2008")
    assert stance is None


def test_actual_election_year_exact_match_no_offset():
    """match_via with no year_offset_ prefix → actual == CalAccess."""
    row = {"election_year": 2020, "match_via": "short_form"}
    assert _actual_election_year(row) == 2020


def test_actual_election_year_offset_1():
    row = {"election_year": 2006, "match_via": "year_offset_1_title_short"}
    assert _actual_election_year(row) == 2005


def test_actual_election_year_offset_2():
    row = {"election_year": 2010, "match_via": "year_offset_2_title_short"}
    assert _actual_election_year(row) == 2008


def test_actual_election_year_handles_none_match_via():
    row = {"election_year": 2020, "match_via": None}
    assert _actual_election_year(row) == 2020


def test_actual_election_year_handles_empty_match_via():
    row = {"election_year": 2020, "match_via": ""}
    assert _actual_election_year(row) == 2020


def test_actual_election_year_unrelated_match_via_passes_through():
    row = {"election_year": 2020, "match_via": "some_other_via"}
    assert _actual_election_year(row) == 2020


# ---------------------------------------------------------------------------
# resolve_campaign collision determinism
# ---------------------------------------------------------------------------

def test_resolve_campaign_returns_oncycle_when_collision(fdb):
    """When two campaigns share a measure_db_id, resolve_campaign returns
    the earlier-year (on-cycle) one. ORDER BY election_year ASC guarantees
    this regardless of SQLite insertion order.
    """
    # Insert in reverse order: the recovery first, then the on-cycle.
    insert_campaign(fdb, "PROP_4_2010", "4", 2010, measure_db_id=1189,
                    match_via="year_offset_2_title_short")
    insert_campaign(fdb, "PROP_4_2008", "4", 2008, measure_db_id=1189,
                    match_via="title_short")
    fdb.conn.commit()
    assert fdb.resolve_campaign(measure_db_id=1189) == "PROP_4_2008"


def test_resolve_campaign_no_match_returns_none(fdb):
    assert fdb.resolve_campaign(measure_db_id=9999) is None


def test_resolve_campaign_by_measure_id_and_year(fdb):
    """The (measure_id, year) lookup path is unchanged and shouldn't be
    affected by collision logic."""
    insert_campaign(fdb, "PROP_22_2020", "22", 2020, measure_db_id=500)
    fdb.conn.commit()
    assert fdb.resolve_campaign(measure_id="PROP_22", year=2020) == "PROP_22_2020"


# ---------------------------------------------------------------------------
# aggregate_for_measure rollup
# ---------------------------------------------------------------------------

def test_aggregate_for_measure_returns_none_when_no_match(fdb):
    assert fdb.aggregate_for_measure(9999) is None


def test_aggregate_for_measure_non_collision_passthrough(fdb):
    """Non-collision case: a single campaign rolls up to itself."""
    insert_campaign(fdb, "PROP_22_2020", "22", 2020, measure_db_id=500)
    insert_summary(fdb, "PROP_22_2020", "support", 100.0, n_committees=2)
    insert_summary(fdb, "PROP_22_2020", "oppose", 50.0, n_committees=1)
    insert_donor(fdb, "PROP_22_2020", "support", "UBER", 60.0)
    insert_donor(fdb, "PROP_22_2020", "support", "LYFT", 40.0)
    insert_donor(fdb, "PROP_22_2020", "oppose", "SEIU", 50.0)
    fdb.conn.commit()

    agg = fdb.aggregate_for_measure(500)
    assert agg is not None
    assert agg["finance_campaign_id"] == "PROP_22_2020"
    assert agg["all_campaign_ids"] == ["PROP_22_2020"]
    by_stance = {s["stance"]: s for s in agg["summary"]}
    assert by_stance["support"]["total_receipts"] == 100.0
    assert by_stance["oppose"]["total_receipts"] == 50.0


def test_aggregate_for_measure_sums_across_collision(fdb):
    """Two campaigns linked to one measure_db_id roll up: receipts sum,
    donors union with merged amounts.
    """
    # On-cycle and recovery share measure_db_id=1189
    insert_campaign(fdb, "PROP_4_2008", "4", 2008, measure_db_id=1189)
    insert_campaign(fdb, "PROP_4_2010", "4", 2010, measure_db_id=1189,
                    match_via="year_offset_2_title_short")
    # Per-campaign summaries
    insert_summary(fdb, "PROP_4_2008", "oppose", 6000000.0, n_committees=5)
    insert_summary(fdb, "PROP_4_2010", "oppose", 800000.0, n_committees=1)
    insert_summary(fdb, "PROP_4_2008", "support", 1000000.0, n_committees=1)
    # Donors split across the two campaigns
    insert_donor(fdb, "PROP_4_2008", "oppose", "PLANNED PARENTHOOD CA", 4000000.0)
    insert_donor(fdb, "PROP_4_2008", "oppose", "CTA", 2000000.0)
    insert_donor(fdb, "PROP_4_2010", "oppose", "PLANNED PARENTHOOD CA", 500000.0)
    insert_donor(fdb, "PROP_4_2010", "oppose", "ACLU", 300000.0)
    insert_donor(fdb, "PROP_4_2008", "support", "KNIGHTS OF COLUMBUS", 1000000.0)
    fdb.conn.commit()

    agg = fdb.aggregate_for_measure(1189)
    assert agg is not None
    # On-cycle (2008) is the canonical primary cid
    assert agg["finance_campaign_id"] == "PROP_4_2008"
    assert set(agg["all_campaign_ids"]) == {"PROP_4_2008", "PROP_4_2010"}

    by_stance = {s["stance"]: s for s in agg["summary"]}
    # Oppose: 6M + 0.8M = 6.8M; n_committees: 5 + 1 = 6
    assert by_stance["oppose"]["total_receipts"] == pytest.approx(6800000.0)
    assert by_stance["oppose"]["n_committees"] == 6
    # Support unchanged
    assert by_stance["support"]["total_receipts"] == pytest.approx(1000000.0)

    # Donor union: PLANNED PARENTHOOD CA = 4M + 0.5M = 4.5M (merged)
    pp_donors = [d for d in agg["donors"] if d["donor_name_canon"] == "PLANNED PARENTHOOD CA"]
    assert len(pp_donors) == 1
    assert pp_donors[0]["total_amount"] == pytest.approx(4500000.0)
    # Donor ranking sorted desc within stance
    oppose_donors = [d for d in agg["donors"] if d["stance"] == "oppose"]
    assert oppose_donors[0]["donor_name_canon"] == "PLANNED PARENTHOOD CA"
    assert oppose_donors[1]["donor_name_canon"] == "CTA"


def test_aggregate_for_measure_top5_share_recomputed_on_merged_donors(fdb):
    """top5_share is recomputed against the merged donor list, not summed
    from per-campaign top5_share fields."""
    insert_campaign(fdb, "PROP_X_2008", "X", 2008, measure_db_id=42)
    insert_campaign(fdb, "PROP_X_2010", "X", 2010, measure_db_id=42)
    # Per-campaign summaries have stale top5_share values; rollup should ignore them
    insert_summary(fdb, "PROP_X_2008", "support", 100.0, n_committees=1, top5_share=99.0)
    insert_summary(fdb, "PROP_X_2010", "support", 100.0, n_committees=1, top5_share=99.0)
    # Six equal donors of $33.33 each across the two campaigns → top5 = ~83%, not 99%.
    for i in range(3):
        insert_donor(fdb, "PROP_X_2008", "support", f"DONOR_{i}", 33.33)
        insert_donor(fdb, "PROP_X_2010", "support", f"DONOR_{i+3}", 33.33)
    fdb.conn.commit()

    agg = fdb.aggregate_for_measure(42)
    sup = next(s for s in agg["summary"] if s["stance"] == "support")
    # Top 5 of 6 equal donors = 5/6 of total = ~83.3%
    assert 80 <= sup["top5_share"] <= 86, (
        f"Expected ~83% top5, got {sup['top5_share']} — should be recomputed not inherited"
    )


# ---------------------------------------------------------------------------
# get_calendar_year_receipts — Codex round-5 tests
# ---------------------------------------------------------------------------

def test_calendar_year_receipts_totals_equal_sum_of_weekly_receipts(fdb):
    """The calendar-year aggregation must not drop any weekly rows: SUM of
    calendar bucket totals == SUM of finance_timeline_weekly.weekly_receipts
    for matched campaigns. (Codex caution: tests that the aggregation is
    lossless.)"""
    insert_campaign(fdb, "PROP_22_2020", "22", 2020, measure_db_id=500)
    insert_campaign(fdb, "PROP_4_2008", "4", 2008, measure_db_id=1189)
    insert_campaign(fdb, "PROP_4_2010", "4", 2010, measure_db_id=1189,
                    match_via="year_offset_2_title_short")
    # Mix of years and stances so SUM is non-trivial
    insert_week(fdb, "PROP_22_2020", "support", "2020-06-29", 50.0, 50.0)
    insert_week(fdb, "PROP_22_2020", "support", "2020-10-26", 30.0, 80.0)
    insert_week(fdb, "PROP_22_2020", "oppose", "2020-10-19", 20.0, 20.0)
    insert_week(fdb, "PROP_4_2008", "oppose", "2008-10-06", 100.0, 100.0)
    insert_week(fdb, "PROP_4_2010", "oppose", "2010-01-04", 15.0, 15.0)
    fdb.conn.commit()

    raw_total = fdb.conn.execute(
        "SELECT SUM(weekly_receipts) FROM finance_timeline_weekly t "
        "JOIN finance_campaign c USING (finance_campaign_id) "
        "WHERE c.status = 'matched'"
    ).fetchone()[0]
    rows = fdb.get_calendar_year_receipts()
    agg_total = sum(r["total_receipts"] for r in rows)
    assert agg_total == pytest.approx(raw_total), (
        f"Calendar aggregation lost rows: raw={raw_total} agg={agg_total}"
    )


def test_calendar_year_receipts_collision_counts_one_measure(fdb):
    """When two campaigns sharing a measure_db_id both contribute to the
    same calendar year, n_measures must count 1 (not 2). Real-world case:
    PROP_4_2008 + PROP_4_2010 both link to db_id 1189; if both have
    weekly rows in 2010, the 2010 bucket sees one measure with the summed
    receipts. (Codex caution: tests measure-level rollup semantics.)"""
    insert_campaign(fdb, "PROP_4_2008", "4", 2008, measure_db_id=1189)
    insert_campaign(fdb, "PROP_4_2010", "4", 2010, measure_db_id=1189,
                    match_via="year_offset_2_title_short")
    # Both campaigns have receipts in 2010 (the on-cycle has late filings;
    # the recovery has its primary activity)
    insert_week(fdb, "PROP_4_2008", "oppose", "2010-03-01", 50.0, 50.0)
    insert_week(fdb, "PROP_4_2010", "oppose", "2010-04-05", 30.0, 30.0)
    fdb.conn.commit()

    rows = fdb.get_calendar_year_receipts()
    bucket_2010 = next((r for r in rows if r["year"] == 2010), None)
    assert bucket_2010 is not None
    assert bucket_2010["total_receipts"] == pytest.approx(80.0)
    assert bucket_2010["n_measures"] == 1, (
        f"Expected 1 distinct measure_db_id in 2010 bucket (PROP_4 collision), "
        f"got {bucket_2010['n_measures']}"
    )


def test_calendar_year_receipts_groups_by_week_start_year(fdb):
    """Weeks whose week_start falls in calendar year X go into bucket X,
    even if the week extends into year X+1. Codex's specific caveat: a
    transaction in the week of 2007-12-31 lands in the 2007 bucket."""
    insert_campaign(fdb, "PROP_X_2008", "X", 2008, measure_db_id=42)
    # The week starting Mon 2007-12-31 extends through Sun 2008-01-06.
    insert_week(fdb, "PROP_X_2008", "support", "2007-12-31", 200.0, 200.0)
    # A normal mid-2008 week for contrast.
    insert_week(fdb, "PROP_X_2008", "support", "2008-06-30", 100.0, 300.0)
    fdb.conn.commit()

    rows = fdb.get_calendar_year_receipts()
    by_year = {r["year"]: r for r in rows}
    assert 2007 in by_year, "Boundary week of 2007-12-31 must produce a 2007 bucket"
    assert by_year[2007]["total_receipts"] == pytest.approx(200.0)
    assert by_year[2008]["total_receipts"] == pytest.approx(100.0)


def test_calendar_year_receipts_skips_unmatched_campaigns(fdb):
    """Only status='matched' campaigns contribute. Missing/junk crosswalk
    rows aren't in finance_campaign at all, but defense in depth: even if
    they were, the JOIN filter excludes them."""
    insert_campaign(fdb, "PROP_22_2020", "22", 2020, measure_db_id=500)
    # Insert an unmatched campaign manually
    fdb.conn.execute(
        "INSERT INTO finance_campaign "
        "(finance_campaign_id, prop_num, election_year, measure_db_id, measure_id, status) "
        "VALUES ('PROP_99_2020', '99', 2020, 999, 'PROP_99', 'missing')"
    )
    # Weekly rows for both — but only the matched one should aggregate
    insert_week(fdb, "PROP_22_2020", "support", "2020-06-29", 50.0, 50.0)
    insert_week(fdb, "PROP_99_2020", "support", "2020-06-29", 999.0, 999.0)
    fdb.conn.commit()

    rows = fdb.get_calendar_year_receipts()
    bucket_2020 = next((r for r in rows if r["year"] == 2020), None)
    assert bucket_2020 is not None
    assert bucket_2020["total_receipts"] == pytest.approx(50.0)


def test_aggregate_for_measure_timeline_unions_weeks(fdb):
    """Timeline weeks union across campaigns, weekly_receipts sum per
    (stance, week_start), cumulative recomputed correctly."""
    insert_campaign(fdb, "PROP_4_2008", "4", 2008, measure_db_id=1189)
    insert_campaign(fdb, "PROP_4_2010", "4", 2010, measure_db_id=1189)
    insert_summary(fdb, "PROP_4_2008", "oppose", 100.0, n_committees=1)
    insert_summary(fdb, "PROP_4_2010", "oppose", 50.0, n_committees=1)
    # Overlapping week 2008-10-06: 30 on cycle, 20 from recovery → sum 50
    insert_week(fdb, "PROP_4_2008", "oppose", "2008-10-06", 30.0, 30.0)
    insert_week(fdb, "PROP_4_2010", "oppose", "2008-10-06", 20.0, 20.0)
    # Non-overlapping weeks
    insert_week(fdb, "PROP_4_2008", "oppose", "2008-10-13", 70.0, 100.0)
    insert_week(fdb, "PROP_4_2010", "oppose", "2010-01-04", 30.0, 50.0)
    fdb.conn.commit()

    agg = fdb.aggregate_for_measure(1189)
    timeline = agg["timeline"]
    # 3 distinct weeks expected after union (2008-10-06 merged, 2008-10-13, 2010-01-04)
    weeks = {(t["week_start"], t["weekly_receipts"]) for t in timeline}
    assert ("2008-10-06", 50.0) in weeks  # 30 + 20 merged
    assert ("2008-10-13", 70.0) in weeks
    assert ("2010-01-04", 30.0) in weeks

    # Cumulative recomputes in order: 50 → 120 → 150
    by_week = {t["week_start"]: t for t in timeline}
    assert by_week["2008-10-06"]["cumulative_receipts"] == pytest.approx(50.0)
    assert by_week["2008-10-13"]["cumulative_receipts"] == pytest.approx(120.0)
    assert by_week["2010-01-04"]["cumulative_receipts"] == pytest.approx(150.0)
