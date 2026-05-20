"""
Tests for v3 expanded-scope FinanceDatabase read methods:
get_finance_summary_total, get_finance_breakdown_by_type,
get_top_donors_total, get_top_donors_by_type.

Hermetic: builds a minimal v3-shaped SQLite DB in tmp_path with the
exact view DDL the live `finance_statewide_v3.db` carries. No
dependency on whether the real v3 db has been built.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

SCRAPER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRAPER_ROOT))

from src.finance.operations import FinanceDatabase  # noqa: E402


# Minimal v3 schema: just the columns the 4 new methods touch.
V3_FLOW_DDL = """
CREATE TABLE finance_flow_v3 (
    flow_id              INTEGER PRIMARY KEY,
    finance_campaign_id  TEXT,
    measure_db_id        INTEGER,
    stance               TEXT,
    receipt_type         TEXT,
    amount               REAL,
    txn_date             TEXT,
    week_start           TEXT,
    source_table         TEXT,
    source_form_type     TEXT,
    filing_id            TEXT,
    amend_id             INTEGER,
    committee_id         TEXT,
    cover_committee_id   TEXT,
    cover_filer_id       TEXT,
    reported_filer       TEXT,
    donor_name_canon     TEXT,
    donor_type           TEXT,
    donor_sector         TEXT,
    attribution_source   TEXT,
    quarantine_reason    TEXT
);
"""

# Verbatim from the live v3 db. Updates here MUST track changes to the
# canonical view DDL in scripts/v3/ingest_ies.py (the script that creates
# these views during the initial v3 build).
V3_SUMMARY_TOTAL_VIEW = """
CREATE VIEW finance_summary_total AS
WITH per_donor AS (
    SELECT finance_campaign_id, stance, donor_name_canon,
           SUM(amount) AS donor_total
    FROM   finance_flow_v3
    WHERE  quarantine_reason IS NULL
    GROUP  BY finance_campaign_id, stance, donor_name_canon
),
campaign_totals AS (
    SELECT finance_campaign_id, stance,
           SUM(donor_total) AS grand_total
    FROM   per_donor
    GROUP  BY finance_campaign_id, stance
),
ranked AS (
    SELECT finance_campaign_id, stance, donor_total,
           ROW_NUMBER() OVER (
               PARTITION BY finance_campaign_id, stance
               ORDER BY donor_total DESC
           ) AS rk
    FROM per_donor
),
top5 AS (
    SELECT finance_campaign_id, stance,
           SUM(donor_total) AS top5_sum
    FROM   ranked
    WHERE  rk <= 5
    GROUP  BY finance_campaign_id, stance
),
hhi_calc AS (
    SELECT pd.finance_campaign_id, pd.stance,
           SUM(
               (100.0 * pd.donor_total / NULLIF(ct.grand_total, 0)) *
               (100.0 * pd.donor_total / NULLIF(ct.grand_total, 0))
           ) AS hhi
    FROM   per_donor pd
    JOIN   campaign_totals ct
        ON ct.finance_campaign_id = pd.finance_campaign_id
       AND ct.stance               = pd.stance
    GROUP  BY pd.finance_campaign_id, pd.stance
),
flow_agg AS (
    SELECT finance_campaign_id,
           MAX(measure_db_id)           AS measure_db_id,
           stance,
           SUM(amount)                  AS total_amount,
           COUNT(DISTINCT COALESCE(
               committee_id, cover_committee_id,
               cover_filer_id, reported_filer
           ))                           AS n_committees,
           COUNT(*)                     AS n_transactions
    FROM   finance_flow_v3
    WHERE  quarantine_reason IS NULL
    GROUP  BY finance_campaign_id, stance
)
SELECT
    fa.finance_campaign_id,
    fa.measure_db_id,
    fa.stance,
    fa.total_amount,
    fa.n_committees,
    fa.n_transactions,
    CASE
        WHEN ct.grand_total > 0
        THEN 100.0 * t5.top5_sum / ct.grand_total
        ELSE NULL
    END                                  AS top5_share,
    h.hhi                                AS hhi
FROM   flow_agg fa
LEFT JOIN campaign_totals ct
       ON ct.finance_campaign_id = fa.finance_campaign_id
      AND ct.stance               = fa.stance
LEFT JOIN top5 t5
       ON t5.finance_campaign_id = fa.finance_campaign_id
      AND t5.stance               = fa.stance
LEFT JOIN hhi_calc h
       ON h.finance_campaign_id = fa.finance_campaign_id
      AND h.stance               = fa.stance;
"""

V3_TOP_DONORS_TOTAL_VIEW = """
CREATE VIEW finance_top_donors_total AS
WITH flow_accepted AS (
    SELECT finance_campaign_id, measure_db_id, stance,
           donor_name_canon, receipt_type, attribution_source,
           donor_type, donor_sector, amount
    FROM   finance_flow_v3
    WHERE  quarantine_reason IS NULL
),
per_donor AS (
    SELECT finance_campaign_id,
           MAX(measure_db_id)                          AS measure_db_id,
           stance,
           donor_name_canon,
           SUM(amount)                                 AS total_amount,
           MAX(donor_type)                             AS donor_type,
           MAX(donor_sector)                           AS donor_sector,
           json_group_array(DISTINCT receipt_type)     AS flow_types,
           json_group_array(DISTINCT attribution_source) AS attribution_sources,
           COUNT(*)                                    AS n_underlying_rows
    FROM   flow_accepted
    GROUP  BY finance_campaign_id, stance, donor_name_canon
),
per_donor_attribution AS (
    SELECT finance_campaign_id, stance, donor_name_canon,
           attribution_source,
           SUM(amount) AS attr_total
    FROM   flow_accepted
    GROUP  BY finance_campaign_id, stance, donor_name_canon, attribution_source
),
ranked_attribution AS (
    SELECT finance_campaign_id, stance, donor_name_canon,
           attribution_source,
           ROW_NUMBER() OVER (
               PARTITION BY finance_campaign_id, stance, donor_name_canon
               ORDER BY attr_total DESC
           ) AS rk
    FROM   per_donor_attribution
)
SELECT
    pd.finance_campaign_id,
    pd.measure_db_id,
    pd.stance,
    pd.donor_name_canon,
    pd.total_amount,
    pd.donor_type,
    pd.donor_sector,
    pd.flow_types,
    pd.attribution_sources,
    ra.attribution_source                              AS primary_attribution_source,
    pd.n_underlying_rows
FROM per_donor pd
LEFT JOIN ranked_attribution ra
       ON ra.finance_campaign_id = pd.finance_campaign_id
      AND ra.stance               = pd.stance
      AND ra.donor_name_canon     = pd.donor_name_canon
      AND ra.rk                   = 1;
"""

V3_BY_TYPE_TABLES_DDL = """
CREATE TABLE finance_summary_by_type (
    finance_campaign_id  TEXT NOT NULL,
    measure_db_id        INTEGER NOT NULL,
    stance               TEXT NOT NULL,
    receipt_type         TEXT NOT NULL,
    total_amount         REAL NOT NULL,
    n_committees         INTEGER,
    n_transactions       INTEGER,
    top5_share           REAL,
    hhi                  REAL,
    PRIMARY KEY (finance_campaign_id, stance, receipt_type)
);
CREATE TABLE finance_top_donors_by_type (
    finance_campaign_id  TEXT NOT NULL,
    measure_db_id        INTEGER NOT NULL,
    stance               TEXT NOT NULL,
    receipt_type         TEXT NOT NULL,
    donor_name_canon     TEXT NOT NULL,
    donor_type           TEXT,
    donor_sector         TEXT,
    total_amount         REAL NOT NULL,
    n_underlying_rows    INTEGER,
    attribution_source_mode TEXT,
    PRIMARY KEY (finance_campaign_id, stance, receipt_type, donor_name_canon)
);
"""


def _build_v3_db(path: Path) -> sqlite3.Connection:
    """Build a fresh v3-shaped SQLite db at path. Returns a raw
    connection for the caller to populate before handing off to
    FinanceDatabase."""
    raw = sqlite3.connect(str(path))
    raw.executescript(V3_FLOW_DDL)
    raw.executescript(V3_BY_TYPE_TABLES_DDL)
    raw.executescript(V3_SUMMARY_TOTAL_VIEW)
    raw.executescript(V3_TOP_DONORS_TOTAL_VIEW)
    return raw


def _insert_flow(
    conn,
    *,
    flow_id,
    finance_campaign_id,
    measure_db_id,
    stance,
    receipt_type,
    amount,
    donor_name_canon,
    committee_id="C1",
    donor_type="other",
    donor_sector=None,
    attribution_source="filer",
    quarantine_reason=None,
):
    conn.execute(
        """
        INSERT INTO finance_flow_v3
        (flow_id, finance_campaign_id, measure_db_id, stance, receipt_type,
         amount, source_table, source_form_type, filing_id, amend_id,
         committee_id, donor_name_canon, donor_type, donor_sector,
         attribution_source, quarantine_reason)
        VALUES (?, ?, ?, ?, ?, ?, 'EXPN_CD', 'F461P5', '1', 0,
                ?, ?, ?, ?, ?, ?)
        """,
        (flow_id, finance_campaign_id, measure_db_id, stance, receipt_type,
         amount, committee_id, donor_name_canon, donor_type, donor_sector,
         attribution_source, quarantine_reason),
    )


def _insert_summary_by_type(
    conn, *, finance_campaign_id, measure_db_id, stance, receipt_type,
    total_amount, n_committees=1, n_transactions=1, top5_share=None, hhi=None,
):
    conn.execute(
        "INSERT INTO finance_summary_by_type "
        "(finance_campaign_id, measure_db_id, stance, receipt_type, "
        " total_amount, n_committees, n_transactions, top5_share, hhi) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (finance_campaign_id, measure_db_id, stance, receipt_type,
         total_amount, n_committees, n_transactions, top5_share, hhi),
    )


def _insert_top_donor_by_type(
    conn, *, finance_campaign_id, measure_db_id, stance, receipt_type,
    donor_name_canon, total_amount, donor_type="other", donor_sector=None,
    n_underlying_rows=1, attribution_source_mode="filer",
):
    conn.execute(
        "INSERT INTO finance_top_donors_by_type "
        "(finance_campaign_id, measure_db_id, stance, receipt_type, "
        " donor_name_canon, donor_type, donor_sector, total_amount, "
        " n_underlying_rows, attribution_source_mode) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (finance_campaign_id, measure_db_id, stance, receipt_type,
         donor_name_canon, donor_type, donor_sector, total_amount,
         n_underlying_rows, attribution_source_mode),
    )


@pytest.fixture
def fdb_v3(tmp_path):
    """A FinanceDatabase with a real v2 path (empty stub) and a v3 path
    pointing at the test-built db. v2 conn is opened but never used in
    these tests."""
    v2_path = tmp_path / "v2_stub.db"
    sqlite3.connect(str(v2_path)).close()  # empty file, just so connect works
    v3_path = tmp_path / "v3_test.db"
    raw = _build_v3_db(v3_path)
    raw.commit()
    raw.close()
    db = FinanceDatabase(db_path=v2_path, v3_db_path=v3_path)
    yield db
    db.close()


def _v3_raw(db: FinanceDatabase) -> sqlite3.Connection:
    """Expose the v3 connection for test-data insertion."""
    return db.v3_conn


# ---------------------------------------------------------------------------
# get_finance_summary_total
# ---------------------------------------------------------------------------

class TestSummaryTotal:
    def test_single_campaign_one_stance(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_22_2020",
                     measure_db_id=100, stance="support",
                     receipt_type="monetary_contribution", amount=1_000_000,
                     donor_name_canon="Uber Technologies")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_22_2020",
                     measure_db_id=100, stance="support",
                     receipt_type="in_kind", amount=500_000,
                     donor_name_canon="Lyft, Inc")
        raw.commit()

        result = fdb_v3.get_finance_summary_total(100)
        assert len(result) == 1
        row = result[0]
        assert row["stance"] == "support"
        assert row["total_amount"] == 1_500_000.0
        # 1.5M total, top donor Uber at 1M, second Lyft at 500K
        # top5_share = 100% (only 2 donors, both in top 5)
        assert row["top5_share"] == pytest.approx(100.0)
        # HHI = (1000/1500*100)^2 + (500/1500*100)^2
        #     = 66.67^2 + 33.33^2 = 4444.4 + 1111.1 = 5555.6
        assert row["hhi"] == pytest.approx(5555.555, rel=1e-3)

    def test_no_flows_returns_empty(self, fdb_v3):
        assert fdb_v3.get_finance_summary_total(99999) == []

    def test_quarantined_rows_excluded(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=200, stance="support",
                     receipt_type="monetary_contribution", amount=1_000,
                     donor_name_canon="Good Donor")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=200, stance="support",
                     receipt_type="independent_expenditure", amount=10_000_000,
                     donor_name_canon="Bad Donor",
                     quarantine_reason="ambiguous_multi_prop")
        raw.commit()

        result = fdb_v3.get_finance_summary_total(200)
        assert len(result) == 1
        assert result[0]["total_amount"] == 1_000.0

    def test_rolls_up_year_offset_collision(self, fdb_v3):
        """measure_db_id 300 has two campaigns (PROP_4_2008 + PROP_4_2010).
        Summary must sum across them per stance and recompute concentration
        against the merged donor list — not return separate rows per
        campaign id."""
        raw = _v3_raw(fdb_v3)
        # On-cycle campaign
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_4_2008",
                     measure_db_id=300, stance="oppose",
                     receipt_type="monetary_contribution", amount=600_000,
                     donor_name_canon="Planned Parenthood")
        # Year-offset late-filed campaign
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_4_2010",
                     measure_db_id=300, stance="oppose",
                     receipt_type="monetary_contribution", amount=400_000,
                     donor_name_canon="Planned Parenthood")
        _insert_flow(raw, flow_id=3, finance_campaign_id="PROP_4_2010",
                     measure_db_id=300, stance="oppose",
                     receipt_type="monetary_contribution", amount=200_000,
                     donor_name_canon="ACLU")
        raw.commit()

        result = fdb_v3.get_finance_summary_total(300)
        assert len(result) == 1, "should collapse 2 cids into 1 row per stance"
        assert result[0]["stance"] == "oppose"
        assert result[0]["total_amount"] == 1_200_000.0
        # Merged donors: Planned Parenthood $1M, ACLU $200K, total $1.2M
        # top5_share = 100% (2 donors, both in top 5)
        assert result[0]["top5_share"] == pytest.approx(100.0)
        # HHI = (1M/1.2M*100)^2 + (200K/1.2M*100)^2
        #     = 83.33^2 + 16.67^2 = 6944.4 + 277.8 = 7222.2
        assert result[0]["hhi"] == pytest.approx(7222.222, rel=1e-3)


# ---------------------------------------------------------------------------
# get_finance_breakdown_by_type
# ---------------------------------------------------------------------------

class TestBreakdownByType:
    def test_separates_receipt_types(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, rt, amt in [
            (1, "monetary_contribution", 5_000_000),
            (2, "in_kind", 1_000_000),
            (3, "independent_expenditure", 20_000_000),
            (4, "loan", 500_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_27_2022",
                         measure_db_id=400, stance="support",
                         receipt_type=rt, amount=amt,
                         donor_name_canon=f"Donor{fid}")
        raw.commit()

        result = fdb_v3.get_finance_breakdown_by_type(400)
        assert len(result) == 4
        types = sorted(r["receipt_type"] for r in result)
        assert types == ["in_kind", "independent_expenditure",
                         "loan", "monetary_contribution"]
        total_sum = sum(r["total_amount"] for r in result)
        assert total_sum == 26_500_000.0

    def test_rolls_up_collision_per_type(self, fdb_v3):
        """When measure has 2 campaigns, breakdown sums each receipt_type
        across both."""
        raw = _v3_raw(fdb_v3)
        for fid, cid, rt, amt in [
            (1, "PROP_A_2020", "monetary_contribution", 1_000_000),
            (2, "PROP_A_2022", "monetary_contribution", 500_000),
            (3, "PROP_A_2020", "in_kind", 200_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id=cid,
                         measure_db_id=500, stance="oppose",
                         receipt_type=rt, amount=amt,
                         donor_name_canon=f"Donor{fid}")
        raw.commit()

        result = fdb_v3.get_finance_breakdown_by_type(500)
        by_type = {r["receipt_type"]: r for r in result}
        assert by_type["monetary_contribution"]["total_amount"] == 1_500_000.0
        assert by_type["in_kind"]["total_amount"] == 200_000.0

    def test_no_flows_returns_empty(self, fdb_v3):
        assert fdb_v3.get_finance_breakdown_by_type(99999) == []


# ---------------------------------------------------------------------------
# get_top_donors_total
# ---------------------------------------------------------------------------

class TestTopDonorsTotal:
    def test_per_stance_ranking(self, fdb_v3):
        """Both stances ranked separately — smaller side shouldn't be
        crowded out (v2 invariant)."""
        raw = _v3_raw(fdb_v3)
        # support side: 1 big donor
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=600, stance="support",
                     receipt_type="independent_expenditure", amount=50_000_000,
                     donor_name_canon="MegaDonor")
        # oppose side: 1 small donor
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=600, stance="oppose",
                     receipt_type="monetary_contribution", amount=10_000,
                     donor_name_canon="SmallDonor")
        raw.commit()

        result = fdb_v3.get_top_donors_total(600, limit=5)
        assert len(result) == 2
        stances = {r["stance"] for r in result}
        assert stances == {"support", "oppose"}

    def test_stance_filter(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=700, stance="support",
                     receipt_type="monetary_contribution", amount=1000,
                     donor_name_canon="Yes Donor")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=700, stance="oppose",
                     receipt_type="monetary_contribution", amount=2000,
                     donor_name_canon="No Donor")
        raw.commit()

        result = fdb_v3.get_top_donors_total(700, stance="support")
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Yes Donor"

    def test_unions_flow_types_across_campaigns(self, fdb_v3):
        """Donor appearing across multiple flow_types should carry all
        of them in flow_types (deduped, no order guarantees)."""
        raw = _v3_raw(fdb_v3)
        for fid, rt, amt in [
            (1, "monetary_contribution", 100_000),
            (2, "in_kind", 50_000),
            (3, "independent_expenditure", 200_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=800, stance="support",
                         receipt_type=rt, amount=amt,
                         donor_name_canon="Versatile Donor")
        raw.commit()

        result = fdb_v3.get_top_donors_total(800)
        assert len(result) == 1
        assert set(result[0]["flow_types"]) == {
            "monetary_contribution", "in_kind", "independent_expenditure"
        }
        assert result[0]["total_amount"] == 350_000.0

    def test_donor_sector_resolved_at_query_time(self, fdb_v3):
        """Sector comes from get_donor_sector(), NOT the stored
        donor_sector column. Insert a flow with stored sector='STALE_VAL'
        and confirm the returned row gets the real sector for that name."""
        raw = _v3_raw(fdb_v3)
        # 'San Manuel Band of Mission Indians' is curated as Tribal Gaming
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=900, stance="oppose",
                     receipt_type="independent_expenditure", amount=1_000_000,
                     donor_name_canon="San Manuel Band of Mission Indians",
                     donor_sector="STALE_VAL")
        raw.commit()

        result = fdb_v3.get_top_donors_total(900)
        assert result[0]["donor_sector"] == "Tribal Gaming"

    def test_rolls_up_collision_with_merged_donor(self, fdb_v3):
        """Same donor across two collision campaigns should appear ONCE
        with summed total — not twice."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_A_2008",
                     measure_db_id=1000, stance="oppose",
                     receipt_type="monetary_contribution", amount=600_000,
                     donor_name_canon="Planned Parenthood")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_A_2010",
                     measure_db_id=1000, stance="oppose",
                     receipt_type="monetary_contribution", amount=400_000,
                     donor_name_canon="Planned Parenthood")
        raw.commit()

        result = fdb_v3.get_top_donors_total(1000)
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Planned Parenthood"
        assert result[0]["total_amount"] == 1_000_000.0

    def test_no_flows_returns_empty(self, fdb_v3):
        assert fdb_v3.get_top_donors_total(99999) == []


# ---------------------------------------------------------------------------
# get_top_donors_by_type
# ---------------------------------------------------------------------------

class TestTopDonorsByType:
    def test_filters_to_one_receipt_type(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, rt, donor, amt in [
            (1, "monetary_contribution", "Cash Donor", 1_000_000),
            (2, "in_kind", "InKind Donor", 500_000),
            (3, "independent_expenditure", "IE Donor", 3_000_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=1100, stance="support",
                         receipt_type=rt, amount=amt,
                         donor_name_canon=donor)
        raw.commit()

        ie_result = fdb_v3.get_top_donors_by_type(
            1100, "independent_expenditure",
        )
        assert len(ie_result) == 1
        assert ie_result[0]["receipt_type"] == "independent_expenditure"
        assert ie_result[0]["donor_name_canon"] == "IE Donor"

    def test_stance_filter(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=1200, stance="support",
                     receipt_type="monetary_contribution", amount=1000,
                     donor_name_canon="Sup")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=1200, stance="oppose",
                     receipt_type="monetary_contribution", amount=2000,
                     donor_name_canon="Opp")
        raw.commit()

        result = fdb_v3.get_top_donors_by_type(
            1200, "monetary_contribution", stance="oppose",
        )
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Opp"

    def test_donor_sector_resolved_at_query_time(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        # Insert IE flow for Lyft, with a STALE stored donor_sector that
        # should NOT bleed through — the method re-resolves via get_donor_sector.
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=1300, stance="support",
                     receipt_type="independent_expenditure", amount=5_000_000,
                     donor_name_canon="Lyft, Inc",
                     donor_sector="STALE")
        raw.commit()

        result = fdb_v3.get_top_donors_by_type(
            1300, "independent_expenditure",
        )
        assert result[0]["donor_sector"] == "Gig Economy"

    def test_rolls_up_collision_within_type(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, cid, amt in [
            (1, "PROP_A_2008", 600_000),
            (2, "PROP_A_2010", 400_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id=cid,
                         measure_db_id=1400, stance="oppose",
                         receipt_type="monetary_contribution", amount=amt,
                         donor_name_canon="Planned Parenthood")
        raw.commit()

        result = fdb_v3.get_top_donors_by_type(
            1400, "monetary_contribution",
        )
        assert len(result) == 1
        assert result[0]["total_amount"] == 1_000_000.0

    def test_no_flows_returns_empty(self, fdb_v3):
        assert fdb_v3.get_top_donors_by_type(
            99999, "monetary_contribution",
        ) == []


# ---------------------------------------------------------------------------
# Codex round-1 follow-ups: n_committees NULL preservation, amount-weighted
# attribution_source rollup, 3-campaign collision, limit boundaries, NULL
# donor invariant.
# ---------------------------------------------------------------------------

class TestNCommitteesNullPreservation:
    """Codex finding: finance_summary_by_type currently stores NULL
    n_committees for IE rows (the source has no committee_id /
    cover_committee_id / cover_filer_id / reported_filer for IE).
    Coercing NULL -> 0 misrepresents 'not applicable' as 'zero'."""

    def test_breakdown_preserves_none_when_source_is_null(self, fdb_v3):
        """IE rows in the source have NULL committee_id, cover_committee_id,
        cover_filer_id, AND reported_filer (the donor is the filer of an
        independent expenditure — no receiving committee). COUNT(DISTINCT
        COALESCE(...)) on these is 0; NULLIF coerces 0 to NULL; result
        surfaces as None for "not applicable."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=2100, stance="oppose",
                     receipt_type="independent_expenditure", amount=5_000_000,
                     donor_name_canon="IE Filer",
                     committee_id=None)  # all 4 COALESCE fields NULL
        raw.commit()

        result = fdb_v3.get_finance_breakdown_by_type(2100)
        assert len(result) == 1
        assert result[0]["receipt_type"] == "independent_expenditure"
        assert result[0]["n_committees"] is None, (
            "all-NULL committee keys must surface as None, not 0"
        )
        # n_transactions still counts rows, so it's 1
        assert result[0]["n_transactions"] == 1

    def test_breakdown_preserves_int_when_source_is_nonzero(self, fdb_v3):
        """When flows have non-NULL committee_id, n_committees is the
        DISTINCT count."""
        raw = _v3_raw(fdb_v3)
        for fid, cid in [(1, "C1"), (2, "C2"), (3, "C3")]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=2110, stance="support",
                         receipt_type="monetary_contribution", amount=1_000,
                         donor_name_canon=f"Donor{fid}",
                         committee_id=cid)
        # Plus 2 more from C1 (duplicate committee — should NOT bump count)
        for fid in [4, 5]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=2110, stance="support",
                         receipt_type="monetary_contribution", amount=1_000,
                         donor_name_canon=f"DonorRepeat{fid}",
                         committee_id="C1")
        raw.commit()

        result = fdb_v3.get_finance_breakdown_by_type(2110)
        assert len(result) == 1
        assert result[0]["n_committees"] == 3, (
            "3 distinct committees (C1, C2, C3) across 5 flows"
        )
        assert result[0]["n_transactions"] == 5


class TestAttributionSourceAmountWeighted:
    """Codex finding: primary_attribution_source rollup must be weighted
    by amount across colliding campaigns, NOT just first-non-null or
    lexicographic MAX. The bigger source (by SUM amount) wins."""

    def test_total_picks_larger_source_across_two_campaigns(self, fdb_v3):
        """Same donor has 'filer'-attributed $80M in one campaign and
        'funding_source'-attributed $20M in another. Rollup primary
        should be 'filer' (the bigger one), regardless of insertion or
        view ordering."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_A_2008",
                     measure_db_id=2200, stance="oppose",
                     receipt_type="independent_expenditure", amount=80_000_000,
                     donor_name_canon="Big Tech Co",
                     attribution_source="filer")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_A_2010",
                     measure_db_id=2200, stance="oppose",
                     receipt_type="independent_expenditure", amount=20_000_000,
                     donor_name_canon="Big Tech Co",
                     attribution_source="funding_source")
        raw.commit()

        result = fdb_v3.get_top_donors_total(2200)
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Big Tech Co"
        assert result[0]["primary_attribution_source"] == "filer", (
            "amount-weighted rollup should pick 'filer' ($80M) over "
            "'funding_source' ($20M)"
        )

    def test_total_picks_amount_winner_regardless_of_lex_order(self, fdb_v3):
        """Same scenario but with sources whose alphabetical MAX would
        give the wrong answer. 'apple_source' is lex-LT 'zebra_source'
        but carries more amount."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_A_2008",
                     measure_db_id=2210, stance="support",
                     receipt_type="monetary_contribution", amount=100,
                     donor_name_canon="Anchor",
                     attribution_source="zebra_source")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_A_2010",
                     measure_db_id=2210, stance="oppose",
                     receipt_type="independent_expenditure", amount=10_000_000,
                     donor_name_canon="Donor with Mixed Sources",
                     attribution_source="apple_source")
        _insert_flow(raw, flow_id=3, finance_campaign_id="PROP_A_2008",
                     measure_db_id=2210, stance="oppose",
                     receipt_type="independent_expenditure", amount=1_000,
                     donor_name_canon="Donor with Mixed Sources",
                     attribution_source="zebra_source")
        raw.commit()

        result = fdb_v3.get_top_donors_total(2210, stance="oppose")
        donor_row = next(
            r for r in result if r["donor_name_canon"] == "Donor with Mixed Sources"
        )
        assert donor_row["primary_attribution_source"] == "apple_source", (
            "amount-weighted ($10M vs $1K) should beat lexicographic MAX "
            "(which would pick 'zebra_source')"
        )

    def test_by_type_picks_amount_winner_within_type(self, fdb_v3):
        """Codex flagged the by_type variant used MAX(attribution_source_mode)
        which is lexicographic. The new field 'attribution_source' must
        be amount-weighted within the receipt_type slice."""
        raw = _v3_raw(fdb_v3)
        # Need by-type table rows so the donor surfaces in the ranking
        for cid, amt in [("PROP_A_2008", 80_000_000), ("PROP_A_2010", 20_000_000)]:
            _insert_top_donor_by_type(
                raw, finance_campaign_id=cid, measure_db_id=2220,
                stance="oppose", receipt_type="independent_expenditure",
                donor_name_canon="Big Tech Co", total_amount=amt,
                attribution_source_mode="ignored_old_field",
            )
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_A_2008",
                     measure_db_id=2220, stance="oppose",
                     receipt_type="independent_expenditure", amount=80_000_000,
                     donor_name_canon="Big Tech Co",
                     attribution_source="filer")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_A_2010",
                     measure_db_id=2220, stance="oppose",
                     receipt_type="independent_expenditure", amount=20_000_000,
                     donor_name_canon="Big Tech Co",
                     attribution_source="funding_source")
        raw.commit()

        result = fdb_v3.get_top_donors_by_type(
            2220, "independent_expenditure",
        )
        assert len(result) == 1
        assert result[0]["attribution_source"] == "filer"
        # Sanity: the old field name is GONE from the returned shape
        assert "attribution_source_mode" not in result[0]


class TestThreeCampaignCollision:
    """Codex test gap: 2-campaign collision was covered, 3-campaign
    wasn't. Three campaigns can stress GROUP BY behavior in ways two
    don't (e.g. partial overlap, varying receipt_types per leg)."""

    def test_summary_total_rolls_up_three_campaigns(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, cid, amt in [
            (1, "PROP_A_2008", 600_000),
            (2, "PROP_A_2010", 400_000),
            (3, "PROP_A_2012", 200_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id=cid,
                         measure_db_id=2300, stance="oppose",
                         receipt_type="monetary_contribution", amount=amt,
                         donor_name_canon="Persistent Donor")
        raw.commit()

        result = fdb_v3.get_finance_summary_total(2300)
        assert len(result) == 1, "3 campaigns must collapse to 1 row per stance"
        assert result[0]["total_amount"] == 1_200_000.0

    def test_top_donors_total_merges_donor_across_three_campaigns(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, cid, amt in [
            (1, "PROP_A_2008", 1_000_000),
            (2, "PROP_A_2010", 500_000),
            (3, "PROP_A_2012", 250_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id=cid,
                         measure_db_id=2310, stance="oppose",
                         receipt_type="in_kind", amount=amt,
                         donor_name_canon="Persistent Donor")
        raw.commit()

        result = fdb_v3.get_top_donors_total(2310)
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Persistent Donor"
        assert result[0]["total_amount"] == 1_750_000.0


class TestLimitBoundaries:
    """Codex test gap: limit=1 (single-donor return) and limit > donor
    count (no padding, no error)."""

    def test_limit_one_returns_single_donor_per_stance(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, donor, amt in [
            (1, "Top Donor", 10_000_000),
            (2, "Middle Donor", 5_000_000),
            (3, "Small Donor", 100_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=2400, stance="support",
                         receipt_type="monetary_contribution", amount=amt,
                         donor_name_canon=donor)
        raw.commit()

        result = fdb_v3.get_top_donors_total(2400, limit=1)
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Top Donor"

    def test_limit_larger_than_donor_count_returns_all(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=2410, stance="support",
                     receipt_type="monetary_contribution", amount=1_000,
                     donor_name_canon="Only Donor")
        raw.commit()

        result = fdb_v3.get_top_donors_total(2410, limit=100)
        assert len(result) == 1, "limit > donor count returns all, no error"

    def test_by_type_limit_one_per_stance(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, stance, donor, amt in [
            (1, "support", "Sup Top", 1_000_000),
            (2, "support", "Sup Mid", 500_000),
            (3, "oppose", "Opp Top", 800_000),
            (4, "oppose", "Opp Mid", 400_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=2420, stance=stance,
                         receipt_type="monetary_contribution", amount=amt,
                         donor_name_canon=donor)
            _insert_top_donor_by_type(
                raw, finance_campaign_id="PROP_X_2020", measure_db_id=2420,
                stance=stance, receipt_type="monetary_contribution",
                donor_name_canon=donor, total_amount=amt,
            )
        raw.commit()

        result = fdb_v3.get_top_donors_by_type(
            2420, "monetary_contribution", limit=1,
        )
        # One donor per stance — partition is by stance, so limit=1 gives
        # 2 rows (one per side).
        assert len(result) == 2
        donors = {(r["stance"], r["donor_name_canon"]) for r in result}
        assert donors == {("support", "Sup Top"), ("oppose", "Opp Top")}


class TestMeasureGuardDefenseInDepth:
    """Codex finding C: even though no campaign currently spans multiple
    measure_db_ids, the rollup queries should guard against future drift
    by explicitly filtering on measure_db_id alongside finance_campaign_id."""

    def test_cross_measure_flow_with_shared_campaign_id_is_excluded(self, fdb_v3):
        """Inject a row with the same finance_campaign_id but a DIFFERENT
        measure_db_id. The guard must exclude it from the rollup for
        either measure."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="SHARED_CID",
                     measure_db_id=2500, stance="support",
                     receipt_type="monetary_contribution", amount=1_000,
                     donor_name_canon="Legit Donor")
        _insert_flow(raw, flow_id=2, finance_campaign_id="SHARED_CID",
                     measure_db_id=2999, stance="support",
                     receipt_type="monetary_contribution", amount=999_999,
                     donor_name_canon="Other Measure's Donor")
        raw.commit()

        result = fdb_v3.get_finance_summary_total(2500)
        assert len(result) == 1
        assert result[0]["total_amount"] == 1_000.0, (
            "rollup must not leak the other-measure row even though it "
            "shares finance_campaign_id"
        )
        donors = fdb_v3.get_top_donors_total(2500)
        donor_names = {d["donor_name_canon"] for d in donors}
        assert donor_names == {"Legit Donor"}


class TestEmptyStringCommitteeKey:
    """Codex round-2 finding: CAL-ACCESS ships empty-string
    cover_committee_id ubiquitously (every accepted row has it). The
    naive COALESCE(committee_id, cover_committee_id, ...) short-circuits
    on '' and counts it as one distinct "committee," so per-slice
    COUNT(DISTINCT) returns 1 regardless of how many real filers exist.
    Fix: COALESCE(NULLIF(TRIM(col), ''), ...) so empty / whitespace
    values skip past instead of being counted."""

    def test_empty_string_cover_committee_does_not_mask_real_filers(self, fdb_v3):
        """Three flows: each has an empty-string cover_committee_id but
        distinct reported_filer values. Expect n_committees=3, not 1."""
        raw = _v3_raw(fdb_v3)
        for fid, filer in [
            (1, "Tribe A"),
            (2, "Tribe B"),
            (3, "Tribe C"),
        ]:
            # committee_id NULL, cover_committee_id empty-string,
            # cover_filer_id NULL, reported_filer = the real entity.
            # _insert_flow only sets committee_id; we patch the rest
            # via raw UPDATE because the helper doesn't expose those
            # columns. This matches the live-DB shape.
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=3000, stance="oppose",
                         receipt_type="independent_expenditure", amount=1_000_000,
                         donor_name_canon=f"Donor{fid}",
                         committee_id=None)
            raw.execute(
                "UPDATE finance_flow_v3 SET cover_committee_id = '', "
                "reported_filer = ? WHERE flow_id = ?",
                (filer, fid),
            )
        raw.commit()

        result = fdb_v3.get_finance_breakdown_by_type(3000)
        assert len(result) == 1
        assert result[0]["receipt_type"] == "independent_expenditure"
        assert result[0]["n_committees"] == 3, (
            f"empty-string cover_committee_id must not mask real filers; "
            f"got n_committees={result[0]['n_committees']}"
        )

    def test_space_only_committee_key_does_not_mask_real_filers(self, fdb_v3):
        """Same as above but with space-only ('   ') instead of empty
        string. SQLite's default TRIM strips ASCII spaces, so the fix
        also handles this case. (CAL-ACCESS has zero whitespace-only
        values in the wild per live-DB diagnostic, but defense-in-depth
        for future drift.)

        Caveat: SQLite TRIM() strips only ASCII space (0x20). Tab /
        newline / carriage-return characters in committee_id columns
        would NOT be stripped by the current fix and could still mask
        real filers. Out of scope today (none observed in live data);
        if it becomes a concern, expand to
        `TRIM(col, char(9)||char(10)||char(13)||' ')` in operations.py,
        schema.sql, and rebuild_derived.py.
        """
        raw = _v3_raw(fdb_v3)
        for fid, filer in [(1, "Filer X"), (2, "Filer Y")]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=3010, stance="support",
                         receipt_type="independent_expenditure", amount=500_000,
                         donor_name_canon=f"D{fid}",
                         committee_id="   ")
            raw.execute(
                "UPDATE finance_flow_v3 SET cover_committee_id = '   ', "
                "reported_filer = ? WHERE flow_id = ?",
                (filer, fid),
            )
        raw.commit()

        result = fdb_v3.get_finance_breakdown_by_type(3010)
        assert result[0]["n_committees"] == 2

    def test_committee_id_populated_still_correct(self, fdb_v3):
        """Sanity: when committee_id IS populated (non-empty), the fix
        shouldn't regress the count. 3 flows under 2 distinct
        committee_ids → n_committees=2."""
        raw = _v3_raw(fdb_v3)
        for fid, cid in [(1, "C1"), (2, "C1"), (3, "C2")]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=3020, stance="support",
                         receipt_type="monetary_contribution", amount=1000,
                         donor_name_canon=f"D{fid}",
                         committee_id=cid)
        raw.commit()

        result = fdb_v3.get_finance_breakdown_by_type(3020)
        assert result[0]["n_committees"] == 2


class TestNullDonorSortTiebreak:
    """Codex round-2 finding: the donor-list sort tiebreak used
    `d["donor_name_canon"]` as the secondary key. If a NULL donor and a
    non-NULL donor have the same amount, Python raises TypeError
    comparing None to str. Fix: tuple (is_None_flag, name_or_empty)."""

    def test_null_donor_with_tied_amount_does_not_crash(self, fdb_v3):
        """Two donors, same amount, one of them has NULL donor_name_canon.
        The sort must not raise TypeError."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=3100, stance="support",
                     receipt_type="monetary_contribution", amount=5_000,
                     donor_name_canon=None)
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=3100, stance="support",
                     receipt_type="monetary_contribution", amount=5_000,
                     donor_name_canon="Real Donor")
        raw.commit()

        # Must not raise. summary_total triggers the donor sort during
        # top5/HHI recompute.
        summary = fdb_v3.get_finance_summary_total(3100)
        assert summary[0]["total_amount"] == 10_000.0
        # NULL donor sorts AFTER named donors (deterministic).
        breakdown = fdb_v3.get_finance_breakdown_by_type(3100)
        assert breakdown[0]["total_amount"] == 10_000.0


class TestAttributionSourceTieBreak:
    """Codex round-2 documenting test: when two attribution_sources have
    exactly tied SUM(amount), the rollup picks the lexicographically
    earlier one via the secondary ORDER BY clause. Deterministic but
    arbitrary — UI copy should treat the field as 'primary / modal'
    rather than implying it's the unique source."""

    def test_tied_amounts_break_lexicographically(self, fdb_v3):
        """One donor, two attribution_sources, exactly equal amounts.
        Lex-earlier 'filer' wins over 'funding_source'."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=3200, stance="support",
                     receipt_type="monetary_contribution", amount=10_000,
                     donor_name_canon="Tied Donor",
                     attribution_source="filer")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=3200, stance="support",
                     receipt_type="monetary_contribution", amount=10_000,
                     donor_name_canon="Tied Donor",
                     attribution_source="funding_source")
        raw.commit()

        result = fdb_v3.get_top_donors_total(3200)
        assert len(result) == 1
        assert result[0]["primary_attribution_source"] == "filer", (
            "tie should break alphabetically: 'filer' < 'funding_source'"
        )


class TestSqlNullLastOrdering:
    """Codex round-3 non-blocking note: the SQL-level ORDER BY (both
    the ROW_NUMBER ranking and the final result-set ORDER) needs the
    same NULL-last tiebreak the Python sort got in round-2. Otherwise,
    SQLite's default (NULLs sort BEFORE strings) would let a NULL
    donor rank ahead of a named donor on tied amounts near the limit
    boundary."""

    def test_null_donor_with_tied_amount_ranks_after_named(self, fdb_v3):
        """Two donors with the same total_amount, one with NULL name.
        The named donor must rank ahead in the ROW_NUMBER ordering
        (which controls the limit truncation)."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=3300, stance="support",
                     receipt_type="monetary_contribution", amount=10_000,
                     donor_name_canon=None)
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=3300, stance="support",
                     receipt_type="monetary_contribution", amount=10_000,
                     donor_name_canon="Real Named Donor")
        raw.commit()

        # limit=1 forces the truncation; if NULL ranks ahead, named
        # donor falls off.
        result = fdb_v3.get_top_donors_total(3300, limit=1)
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Real Named Donor", (
            "NULL donor must NOT rank ahead of named donor on tied amount"
        )

    def test_by_type_null_donor_with_tied_amount_ranks_after_named(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=3310, stance="support",
                     receipt_type="independent_expenditure", amount=10_000,
                     donor_name_canon=None)
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=3310, stance="support",
                     receipt_type="independent_expenditure", amount=10_000,
                     donor_name_canon="Real IE Filer")
        raw.commit()

        result = fdb_v3.get_top_donors_by_type(
            3310, "independent_expenditure", limit=1,
        )
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Real IE Filer"


class TestTimelineTotal:
    """Phase 5 step 2a: get_finance_timeline_total returns per-stance
    weekly + cumulative receipts across all receipt types, rolling up
    collision campaigns."""

    def test_single_stance_cumulative_runs(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, week, amt in [
            (1, "2020-01-06", 100_000),
            (2, "2020-01-13", 50_000),
            (3, "2020-01-27", 25_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=4000, stance="support",
                         receipt_type="monetary_contribution", amount=amt,
                         donor_name_canon=f"D{fid}")
            raw.execute(
                "UPDATE finance_flow_v3 SET week_start = ? WHERE flow_id = ?",
                (week, fid),
            )
        raw.commit()

        result = fdb_v3.get_finance_timeline_total(4000)
        assert len(result) == 3
        # Weekly amounts in order
        assert result[0]["week_start"] == "2020-01-06"
        assert result[0]["weekly_amount"] == 100_000.0
        assert result[0]["cumulative_amount"] == 100_000.0
        assert result[1]["cumulative_amount"] == 150_000.0
        assert result[2]["cumulative_amount"] == 175_000.0

    def test_per_stance_cumulative_independent(self, fdb_v3):
        """Cumulative resets at the first week of each stance — they
        don't share a running total."""
        raw = _v3_raw(fdb_v3)
        for fid, stance, week, amt in [
            (1, "support", "2020-01-06", 10_000),
            (2, "support", "2020-01-13", 5_000),
            (3, "oppose", "2020-01-06", 8_000),
            (4, "oppose", "2020-01-20", 12_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=4010, stance=stance,
                         receipt_type="monetary_contribution", amount=amt,
                         donor_name_canon=f"D{fid}")
            raw.execute(
                "UPDATE finance_flow_v3 SET week_start = ? WHERE flow_id = ?",
                (week, fid),
            )
        raw.commit()

        result = fdb_v3.get_finance_timeline_total(4010)
        oppose = [r for r in result if r["stance"] == "oppose"]
        support = [r for r in result if r["stance"] == "support"]
        # Each stance's cumulative ends with its own total, not the sum
        assert support[-1]["cumulative_amount"] == 15_000.0
        assert oppose[-1]["cumulative_amount"] == 20_000.0

    def test_rolls_up_across_collision_campaigns(self, fdb_v3):
        """Two collision campaigns sharing a measure_db_id and a week
        should collapse into one weekly row with summed amount."""
        raw = _v3_raw(fdb_v3)
        for fid, cid, amt in [
            (1, "PROP_A_2008", 600_000),
            (2, "PROP_A_2010", 400_000),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id=cid,
                         measure_db_id=4020, stance="oppose",
                         receipt_type="monetary_contribution", amount=amt,
                         donor_name_canon=f"D{fid}")
            raw.execute(
                "UPDATE finance_flow_v3 SET week_start = '2008-09-22' WHERE flow_id = ?",
                (fid,),
            )
        raw.commit()

        result = fdb_v3.get_finance_timeline_total(4020)
        assert len(result) == 1, "single week, single stance, both campaigns merged"
        assert result[0]["weekly_amount"] == 1_000_000.0

    def test_quarantined_rows_excluded(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=4030, stance="support",
                     receipt_type="monetary_contribution", amount=5_000,
                     donor_name_canon="Good")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=4030, stance="support",
                     receipt_type="independent_expenditure", amount=10_000_000,
                     donor_name_canon="Bad",
                     quarantine_reason="ambiguous_multi_prop")
        for fid in [1, 2]:
            raw.execute(
                "UPDATE finance_flow_v3 SET week_start = '2020-01-06' WHERE flow_id = ?",
                (fid,),
            )
        raw.commit()

        result = fdb_v3.get_finance_timeline_total(4030)
        assert len(result) == 1
        assert result[0]["weekly_amount"] == 5_000.0

    def test_null_week_start_dropped(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=4040, stance="support",
                     receipt_type="monetary_contribution", amount=5_000,
                     donor_name_canon="Has Date")
        raw.execute(
            "UPDATE finance_flow_v3 SET week_start = '2020-01-06' WHERE flow_id = 1"
        )
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=4040, stance="support",
                     receipt_type="monetary_contribution", amount=99_999,
                     donor_name_canon="No Date")
        # week_start stays NULL (default)
        raw.commit()

        result = fdb_v3.get_finance_timeline_total(4040)
        assert len(result) == 1
        assert result[0]["weekly_amount"] == 5_000.0, (
            "NULL-week_start rows must drop, not contribute"
        )

    def test_no_flows_returns_empty(self, fdb_v3):
        assert fdb_v3.get_finance_timeline_total(99999) == []


class TestCalendarYearReceiptsV3:
    """Phase 5 step 2a: get_calendar_year_receipts_v3 is the v3
    counterpart to v2's get_calendar_year_receipts — cross-measure
    spending arc summed by year of week_start."""

    def test_groups_by_year_of_week_start(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for fid, week, amt, mid in [
            (1, "2018-03-05", 100_000, 5000),
            (2, "2018-11-19", 200_000, 5000),
            (3, "2019-06-10", 50_000, 5010),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id=f"PROP_{fid}_X",
                         measure_db_id=mid, stance="support",
                         receipt_type="monetary_contribution", amount=amt,
                         donor_name_canon=f"D{fid}")
            raw.execute(
                "UPDATE finance_flow_v3 SET week_start = ? WHERE flow_id = ?",
                (week, fid),
            )
        raw.commit()

        result = fdb_v3.get_calendar_year_receipts_v3()
        by_year = {r["year"]: r for r in result}
        assert by_year[2018]["total_amount"] == 300_000.0
        assert by_year[2018]["n_measures"] == 1  # both flows under measure 5000
        assert by_year[2019]["total_amount"] == 50_000.0
        assert by_year[2019]["n_measures"] == 1  # only measure 5010

    def test_collision_campaigns_count_one_measure_per_year(self, fdb_v3):
        """Two collision campaigns under one measure_db_id with flows
        in the same calendar year should count as one measure."""
        raw = _v3_raw(fdb_v3)
        for fid, cid, week in [
            (1, "PROP_A_2008", "2008-09-22"),
            (2, "PROP_A_2010", "2008-12-15"),
        ]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id=cid,
                         measure_db_id=5100, stance="oppose",
                         receipt_type="monetary_contribution", amount=10_000,
                         donor_name_canon=f"D{fid}")
            raw.execute(
                "UPDATE finance_flow_v3 SET week_start = ? WHERE flow_id = ?",
                (week, fid),
            )
        raw.commit()

        result = fdb_v3.get_calendar_year_receipts_v3()
        assert len(result) == 1
        assert result[0]["year"] == 2008
        assert result[0]["total_amount"] == 20_000.0
        assert result[0]["n_measures"] == 1

    def test_quarantined_rows_excluded(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=5200, stance="support",
                     receipt_type="monetary_contribution", amount=5_000,
                     donor_name_canon="Good")
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=5200, stance="support",
                     receipt_type="independent_expenditure", amount=10_000_000,
                     donor_name_canon="Bad",
                     quarantine_reason="ambiguous_multi_prop")
        for fid in [1, 2]:
            raw.execute(
                "UPDATE finance_flow_v3 SET week_start = '2020-01-06' WHERE flow_id = ?",
                (fid,),
            )
        raw.commit()

        result = fdb_v3.get_calendar_year_receipts_v3()
        assert result[0]["total_amount"] == 5_000.0

    def test_null_week_start_dropped(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=5300, stance="support",
                     receipt_type="monetary_contribution", amount=1_000,
                     donor_name_canon="No Date")
        # week_start NULL by default
        raw.commit()

        result = fdb_v3.get_calendar_year_receipts_v3()
        assert result == []

    def test_no_flows_returns_empty(self, fdb_v3):
        # Fresh fixture has no flows at all.
        assert fdb_v3.get_calendar_year_receipts_v3() == []


class TestCombinedMethods:
    """Phase 5 step 2b: get_combined_* methods stitch v2 monetary
    contributions onto the v3 non-monetary slice (loans + in-kind + IE).
    These tests need a v2-shaped fixture too — the per-test fdb_v3 only
    builds v3, so we build a small v2 db alongside."""

    @pytest.fixture
    def fdb_combined(self, tmp_path):
        """A FinanceDatabase pointing at both a hermetic v2 stub AND a
        hermetic v3 stub."""
        # v2 schema (subset of what's in test_finance_db.py)
        v2_path = tmp_path / "v2_combo.db"
        v2 = sqlite3.connect(str(v2_path))
        v2.executescript("""
            CREATE TABLE finance_campaign (
                finance_campaign_id TEXT PRIMARY KEY,
                prop_num TEXT, election_year INTEGER, election_month INTEGER,
                measure_db_id INTEGER, measure_id TEXT,
                status TEXT NOT NULL, match_via TEXT,
                csv_row_count INTEGER, csv_total_amount REAL, notes TEXT
            );
            CREATE TABLE finance_summary (
                finance_campaign_id TEXT NOT NULL, stance TEXT NOT NULL,
                total_receipts REAL NOT NULL, n_committees INTEGER NOT NULL,
                top5_share REAL, hhi REAL,
                PRIMARY KEY (finance_campaign_id, stance)
            );
            CREATE TABLE finance_top_donors (
                finance_campaign_id TEXT NOT NULL, stance TEXT NOT NULL,
                donor_name_canon TEXT NOT NULL, donor_type TEXT,
                total_amount REAL NOT NULL,
                PRIMARY KEY (finance_campaign_id, stance, donor_name_canon)
            );
            CREATE TABLE finance_timeline_weekly (
                finance_campaign_id TEXT NOT NULL, stance TEXT NOT NULL,
                week_start TEXT NOT NULL,
                weekly_receipts REAL NOT NULL, cumulative_receipts REAL NOT NULL,
                PRIMARY KEY (finance_campaign_id, stance, week_start)
            );
        """)
        v2.commit()
        v2.close()
        v3_path = tmp_path / "v3_combo.db"
        v3 = _build_v3_db(v3_path)
        v3.commit()
        v3.close()
        db = FinanceDatabase(db_path=v2_path, v3_db_path=v3_path)
        yield db
        db.close()

    def test_combined_summary_adds_v2_and_v3(self, fdb_combined):
        """v2 has $1M monetary on support; v3 has $500K in-kind +
        $200K IE on support. Combined total should be $1.7M."""
        db = fdb_combined
        # v2 side
        db.conn.execute(
            "INSERT INTO finance_campaign "
            "(finance_campaign_id, prop_num, election_year, measure_db_id, "
            " measure_id, status, match_via) "
            "VALUES ('PROP_X_2020', 'X', 2020, 7000, 'PROP_X', 'matched', 'short_form')"
        )
        db.conn.execute(
            "INSERT INTO finance_summary VALUES "
            "('PROP_X_2020', 'support', 1000000, 2, 80, 4500)"
        )
        db.conn.execute(
            "INSERT INTO finance_top_donors VALUES "
            "('PROP_X_2020', 'support', 'Big v2 Donor', 'committee', 1000000)"
        )
        db.conn.commit()
        # v3 side
        for fid, rt, amt in [
            (1, "in_kind", 500_000),
            (2, "independent_expenditure", 200_000),
        ]:
            _insert_flow(db.v3_conn, flow_id=fid, finance_campaign_id="PROP_X_2020",
                         measure_db_id=7000, stance="support",
                         receipt_type=rt, amount=amt,
                         donor_name_canon=f"v3 donor {fid}")
        db.v3_conn.commit()

        result = db.get_combined_summary(7000)
        assert len(result) == 1
        row = result[0]
        assert row["total_receipts"] == 1_700_000.0
        assert row["monetary_amount"] == 1_000_000.0
        assert row["non_monetary_amount"] == 700_000.0

    def test_combined_summary_v2_only_measure(self, fdb_combined):
        """Measure with v2 data but no v3 flows should still surface."""
        db = fdb_combined
        db.conn.execute(
            "INSERT INTO finance_campaign "
            "(finance_campaign_id, prop_num, election_year, measure_db_id, "
            " measure_id, status, match_via) "
            "VALUES ('PROP_Y_2000', 'Y', 2000, 7100, 'PROP_Y', 'matched', 'short_form')"
        )
        db.conn.execute(
            "INSERT INTO finance_summary VALUES "
            "('PROP_Y_2000', 'oppose', 500000, 1, 100, 10000)"
        )
        db.conn.commit()

        result = db.get_combined_summary(7100)
        assert len(result) == 1
        assert result[0]["total_receipts"] == 500_000.0
        assert result[0]["monetary_amount"] == 500_000.0
        assert result[0]["non_monetary_amount"] == 0.0

    def test_combined_summary_v3_only_measure(self, fdb_combined):
        """Measure with v3 IE but no v2 monetary (rare today, but
        possible if all v2 monetary rows got quarantined)."""
        db = fdb_combined
        _insert_flow(db.v3_conn, flow_id=1, finance_campaign_id="PROP_Z_2024",
                     measure_db_id=7200, stance="oppose",
                     receipt_type="independent_expenditure", amount=300_000,
                     donor_name_canon="v3 IE Filer")
        db.v3_conn.commit()

        result = db.get_combined_summary(7200)
        assert len(result) == 1
        assert result[0]["total_receipts"] == 300_000.0
        assert result[0]["monetary_amount"] == 0.0
        assert result[0]["non_monetary_amount"] == 300_000.0

    def test_combined_top_donors_merges_same_name(self, fdb_combined):
        """Same donor appears in both v2 monetary and v3 IE. Combined
        donor total = sum, flow_types union, ranked once."""
        db = fdb_combined
        db.conn.execute(
            "INSERT INTO finance_campaign "
            "(finance_campaign_id, prop_num, election_year, measure_db_id, "
            " measure_id, status, match_via) "
            "VALUES ('PROP_A_2020', 'A', 2020, 7300, 'PROP_A', 'matched', 'short_form')"
        )
        db.conn.execute(
            "INSERT INTO finance_summary VALUES "
            "('PROP_A_2020', 'oppose', 5000000, 1, 100, 10000)"
        )
        db.conn.execute(
            "INSERT INTO finance_top_donors VALUES "
            "('PROP_A_2020', 'oppose', 'San Manuel Band of Mission Indians', 'committee', 5000000)"
        )
        db.conn.commit()
        _insert_flow(db.v3_conn, flow_id=1, finance_campaign_id="PROP_A_2020",
                     measure_db_id=7300, stance="oppose",
                     receipt_type="independent_expenditure", amount=3_000_000,
                     donor_name_canon="San Manuel Band of Mission Indians")
        db.v3_conn.commit()

        result = db.get_combined_top_donors(7300, limit=5)
        assert len(result) == 1
        d = result[0]
        assert d["donor_name_canon"] == "San Manuel Band of Mission Indians"
        assert d["total_amount"] == 8_000_000.0
        assert set(d["flow_types"]) == {"monetary_contribution", "independent_expenditure"}
        assert d["donor_sector"] == "Tribal Gaming"  # re-resolved at query time

    def test_combined_breakdown_includes_all_four_types(self, fdb_combined):
        db = fdb_combined
        db.conn.execute(
            "INSERT INTO finance_campaign "
            "(finance_campaign_id, prop_num, election_year, measure_db_id, "
            " measure_id, status, match_via) "
            "VALUES ('PROP_B_2020', 'B', 2020, 7400, 'PROP_B', 'matched', 'short_form')"
        )
        db.conn.execute(
            "INSERT INTO finance_summary VALUES "
            "('PROP_B_2020', 'support', 1000000, 1, 100, 10000)"
        )
        db.conn.commit()
        for fid, rt, amt in [
            (1, "loan", 200_000),
            (2, "in_kind", 100_000),
            (3, "independent_expenditure", 500_000),
        ]:
            _insert_flow(db.v3_conn, flow_id=fid, finance_campaign_id="PROP_B_2020",
                         measure_db_id=7400, stance="support",
                         receipt_type=rt, amount=amt,
                         donor_name_canon=f"D{fid}")
        db.v3_conn.commit()

        result = db.get_combined_breakdown_by_type(7400)
        types = sorted(r["receipt_type"] for r in result)
        assert types == [
            "in_kind", "independent_expenditure",
            "loan", "monetary_contribution"
        ]
        total = sum(r["total_amount"] for r in result)
        assert total == 1_800_000.0

    def test_combined_summary_omits_n_transactions(self, fdb_combined):
        """Codex round-4 #4: n_transactions was v3-only but exposed in
        the combined response as if it were combined. Fix: omit it
        entirely from get_combined_summary rows."""
        db = fdb_combined
        db.conn.execute(
            "INSERT INTO finance_campaign "
            "(finance_campaign_id, prop_num, election_year, measure_db_id, "
            " measure_id, status, match_via) "
            "VALUES ('PROP_T_2020', 'T', 2020, 8000, 'PROP_T', 'matched', 'short_form')"
        )
        db.conn.execute(
            "INSERT INTO finance_summary VALUES "
            "('PROP_T_2020', 'support', 1000, 1, 100, 10000)"
        )
        db.conn.commit()
        _insert_flow(db.v3_conn, flow_id=1, finance_campaign_id="PROP_T_2020",
                     measure_db_id=8000, stance="support",
                     receipt_type="independent_expenditure", amount=5000,
                     donor_name_canon="IE Donor")
        db.v3_conn.commit()

        result = db.get_combined_summary(8000)
        assert len(result) == 1
        assert "n_transactions" not in result[0], (
            "n_transactions must be omitted from combined summary — "
            "v2 has no per-side transaction count so a 'combined' value "
            "would be v3-only and misleading"
        )

    def test_combined_calendar_year_n_measures_is_true_union(self, fdb_combined):
        """Codex round-4 #3: combined helper used max(v2_count, v3_count)
        for n_measures, undercounting when v2 and v3 had disjoint
        measure sets. Fix: query distinct (year, measure_db_id) from
        both sources and union in Python."""
        db = fdb_combined
        # Year 2020: v2 has measure 9001 + 9002; v3 has measure 9003 + 9004.
        # All disjoint. True union = 4. Max = 2 (the broken behavior).
        for mid in [9001, 9002]:
            db.conn.execute(
                "INSERT INTO finance_campaign "
                "(finance_campaign_id, prop_num, election_year, measure_db_id, "
                " measure_id, status, match_via) "
                f"VALUES ('PROP_{mid}_2020', '{mid}', 2020, {mid}, "
                f"'PROP_{mid}', 'matched', 'short_form')"
            )
            db.conn.execute(
                f"INSERT INTO finance_summary VALUES "
                f"('PROP_{mid}_2020', 'support', 1000, 1, 100, 10000)"
            )
            db.conn.execute(
                f"INSERT INTO finance_timeline_weekly VALUES "
                f"('PROP_{mid}_2020', 'support', '2020-03-02', 1000, 1000)"
            )
        db.conn.commit()
        for fid, mid in [(1, 9003), (2, 9004)]:
            _insert_flow(db.v3_conn, flow_id=fid, finance_campaign_id=f"PROP_{mid}_2020",
                         measure_db_id=mid, stance="oppose",
                         receipt_type="independent_expenditure", amount=500,
                         donor_name_canon=f"D{fid}")
            db.v3_conn.execute(
                "UPDATE finance_flow_v3 SET week_start = '2020-04-06' WHERE flow_id = ?",
                (fid,),
            )
        db.v3_conn.commit()

        result = db.get_combined_calendar_year_receipts()
        by_year = {r["year"]: r for r in result}
        assert 2020 in by_year
        # Pre-fix this returned max(2, 2) = 2. Post-fix it returns the
        # true union of {9001, 9002, 9003, 9004} = 4.
        assert by_year[2020]["n_measures"] == 4, (
            f"true union should be 4, got {by_year[2020]['n_measures']}"
        )
        # Dollars must still reconcile.
        assert by_year[2020]["total_receipts"] == 3000.0  # 1000+1000+500+500

    def test_combined_timeline_merges_weeks(self, fdb_combined):
        """v2 has weekly $1000 on week W; v3 has weekly $500 on same
        week W. Combined weekly = $1500."""
        db = fdb_combined
        db.conn.execute(
            "INSERT INTO finance_campaign "
            "(finance_campaign_id, prop_num, election_year, measure_db_id, "
            " measure_id, status, match_via) "
            "VALUES ('PROP_C_2020', 'C', 2020, 7500, 'PROP_C', 'matched', 'short_form')"
        )
        db.conn.execute(
            "INSERT INTO finance_summary VALUES "
            "('PROP_C_2020', 'support', 1000, 1, 100, 10000)"
        )
        db.conn.execute(
            "INSERT INTO finance_timeline_weekly VALUES "
            "('PROP_C_2020', 'support', '2020-01-06', 1000, 1000)"
        )
        db.conn.commit()
        _insert_flow(db.v3_conn, flow_id=1, finance_campaign_id="PROP_C_2020",
                     measure_db_id=7500, stance="support",
                     receipt_type="in_kind", amount=500,
                     donor_name_canon="D1")
        db.v3_conn.execute(
            "UPDATE finance_flow_v3 SET week_start = '2020-01-06' WHERE flow_id = 1"
        )
        db.v3_conn.commit()

        result = db.get_combined_timeline(7500)
        assert len(result) == 1
        assert result[0]["weekly_receipts"] == 1500.0
        assert result[0]["cumulative_receipts"] == 1500.0


class TestAcceptedRowNullDonorInvariant:
    """Codex test gap: ingest acceptance gates should reject any row with
    NULL donor_name_canon. This test documents the expected invariant —
    if a NULL ever slips through, the v3 read methods must not crash on
    it, even if the row is filtered (or surfaces with None handling)."""

    def test_null_donor_canon_does_not_crash(self, fdb_v3):
        """Even though accepted rows shouldn't have NULL donor_name_canon,
        the read methods must not crash if one ever surfaces."""
        raw = _v3_raw(fdb_v3)
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=2600, stance="support",
                     receipt_type="monetary_contribution", amount=1_000,
                     donor_name_canon=None)
        _insert_flow(raw, flow_id=2, finance_campaign_id="PROP_X_2020",
                     measure_db_id=2600, stance="support",
                     receipt_type="monetary_contribution", amount=500,
                     donor_name_canon="Real Donor")
        raw.commit()

        # Should not raise. Sum still reflects both rows (NULL donor still
        # contributes to amount).
        summary = fdb_v3.get_finance_summary_total(2600)
        assert len(summary) == 1
        assert summary[0]["total_amount"] == 1_500.0
        # Top-donors output may include or exclude the NULL row; we just
        # require it not to crash and to surface the Real Donor.
        top = fdb_v3.get_top_donors_total(2600)
        real_donor = next(
            (d for d in top if d["donor_name_canon"] == "Real Donor"), None,
        )
        assert real_donor is not None
