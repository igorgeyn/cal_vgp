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
        for cid, rt, amt in [
            ("PROP_27_2022", "monetary_contribution", 5_000_000),
            ("PROP_27_2022", "in_kind", 1_000_000),
            ("PROP_27_2022", "independent_expenditure", 20_000_000),
            ("PROP_27_2022", "loan", 500_000),
        ]:
            _insert_summary_by_type(
                raw, finance_campaign_id=cid, measure_db_id=400,
                stance="support", receipt_type=rt, total_amount=amt,
            )
        # Need finance_flow_v3 rows too so _v3_campaign_ids_for_measure
        # finds the campaign.
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_27_2022",
                     measure_db_id=400, stance="support",
                     receipt_type="monetary_contribution", amount=5_000_000,
                     donor_name_canon="Anchor")
        raw.commit()

        result = fdb_v3.get_finance_breakdown_by_type(400)
        # 4 rows, one per receipt_type
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
        for cid, rt, amt in [
            ("PROP_A_2020", "monetary_contribution", 1_000_000),
            ("PROP_A_2022", "monetary_contribution", 500_000),
            ("PROP_A_2020", "in_kind", 200_000),
        ]:
            _insert_summary_by_type(
                raw, finance_campaign_id=cid, measure_db_id=500,
                stance="oppose", receipt_type=rt, total_amount=amt,
            )
        for fid, cid in [(1, "PROP_A_2020"), (2, "PROP_A_2022")]:
            _insert_flow(raw, flow_id=fid, finance_campaign_id=cid,
                         measure_db_id=500, stance="oppose",
                         receipt_type="monetary_contribution", amount=100,
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
        for cid, rt, donor, amt in [
            ("PROP_X_2020", "monetary_contribution", "Cash Donor", 1_000_000),
            ("PROP_X_2020", "in_kind", "InKind Donor", 500_000),
            ("PROP_X_2020", "independent_expenditure", "IE Donor", 3_000_000),
        ]:
            _insert_top_donor_by_type(
                raw, finance_campaign_id=cid, measure_db_id=1100,
                stance="support", receipt_type=rt,
                donor_name_canon=donor, total_amount=amt,
            )
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=1100, stance="support",
                     receipt_type="monetary_contribution", amount=100,
                     donor_name_canon="anchor")
        raw.commit()

        ie_result = fdb_v3.get_top_donors_by_type(
            1100, "independent_expenditure",
        )
        assert len(ie_result) == 1
        assert ie_result[0]["receipt_type"] == "independent_expenditure"
        assert ie_result[0]["donor_name_canon"] == "IE Donor"

    def test_stance_filter(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_top_donor_by_type(
            raw, finance_campaign_id="PROP_X_2020", measure_db_id=1200,
            stance="support", receipt_type="monetary_contribution",
            donor_name_canon="Sup", total_amount=1000,
        )
        _insert_top_donor_by_type(
            raw, finance_campaign_id="PROP_X_2020", measure_db_id=1200,
            stance="oppose", receipt_type="monetary_contribution",
            donor_name_canon="Opp", total_amount=2000,
        )
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=1200, stance="support",
                     receipt_type="monetary_contribution", amount=100,
                     donor_name_canon="anchor")
        raw.commit()

        result = fdb_v3.get_top_donors_by_type(
            1200, "monetary_contribution", stance="oppose",
        )
        assert len(result) == 1
        assert result[0]["donor_name_canon"] == "Opp"

    def test_donor_sector_resolved_at_query_time(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        _insert_top_donor_by_type(
            raw, finance_campaign_id="PROP_X_2020", measure_db_id=1300,
            stance="support", receipt_type="independent_expenditure",
            donor_name_canon="Lyft, Inc",
            total_amount=5_000_000, donor_sector="STALE",
        )
        _insert_flow(raw, flow_id=1, finance_campaign_id="PROP_X_2020",
                     measure_db_id=1300, stance="support",
                     receipt_type="monetary_contribution", amount=100,
                     donor_name_canon="anchor")
        raw.commit()

        result = fdb_v3.get_top_donors_by_type(
            1300, "independent_expenditure",
        )
        assert result[0]["donor_sector"] == "Gig Economy"

    def test_rolls_up_collision_within_type(self, fdb_v3):
        raw = _v3_raw(fdb_v3)
        for cid, amt in [("PROP_A_2008", 600_000), ("PROP_A_2010", 400_000)]:
            _insert_top_donor_by_type(
                raw, finance_campaign_id=cid, measure_db_id=1400,
                stance="oppose", receipt_type="monetary_contribution",
                donor_name_canon="Planned Parenthood", total_amount=amt,
            )
            _insert_flow(raw, flow_id=hash(cid) & 0xFFFF, finance_campaign_id=cid,
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
