"""
Query layer for the v2 statewide proposition finance database.

Primary key is `finance_campaign_id` (e.g. "PROP_16_2020"), which is unique
per (prop_num, election_year). Consumers usually have a `measure_db_id`
(integer FK into measures.id) or a (`measure_id`, `year`) pair on hand and
need to resolve to a campaign id; `resolve_campaign()` handles that.

The bare `measure_id` ("PROP_16") alone is *not* unique — PROP_1 has a
distinct campaign in 2022 and another in 2024. Callers passing a bare
measure_id without a year that matches multiple active campaigns will get
a ValueError; pass `measure_db_id` or year to disambiguate.
"""
import sqlite3
from pathlib import Path
from typing import Iterable, List, Dict, Optional

from .schema import FINANCE_DB_PATH


class FinanceDatabase:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or FINANCE_DB_PATH
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    # ---- Resolution helpers ------------------------------------------------

    def resolve_campaign(
        self,
        *,
        measure_db_id: Optional[int] = None,
        measure_id: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Optional[str]:
        """Resolve to a single `finance_campaign_id` from any of:
            - `measure_db_id` (integer FK into measures.id) — always unambiguous
            - `(measure_id, year)` — typical case for callers with a measure dict
            - bare `measure_id` — fine when only one campaign matches; raises
              ValueError if multiple campaigns share that measure_id (caller
              must pass year or measure_db_id to disambiguate).

        Returns None if no matched campaign is found.
        """
        if measure_db_id is not None:
            row = self.conn.execute(
                "SELECT finance_campaign_id FROM finance_campaign "
                "WHERE measure_db_id = ? AND status = 'matched'",
                (measure_db_id,),
            ).fetchone()
            return row[0] if row else None

        if measure_id is None:
            return None

        if year is not None:
            row = self.conn.execute(
                "SELECT finance_campaign_id FROM finance_campaign "
                "WHERE measure_id = ? AND election_year = ? AND status = 'matched'",
                (measure_id, year),
            ).fetchone()
            return row[0] if row else None

        rows = self.conn.execute(
            "SELECT finance_campaign_id FROM finance_campaign "
            "WHERE measure_id = ? AND status = 'matched'",
            (measure_id,),
        ).fetchall()
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0][0]
        ambiguous = [r[0] for r in rows]
        raise ValueError(
            f"measure_id {measure_id!r} matches multiple campaigns: {ambiguous}. "
            "Pass year or measure_db_id to disambiguate."
        )

    # ---- Listings ----------------------------------------------------------

    def get_all_finance_campaign_ids(self) -> List[str]:
        cursor = self.conn.execute(
            "SELECT finance_campaign_id FROM finance_campaign "
            "WHERE status = 'matched' ORDER BY finance_campaign_id"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_all_campaigns(self) -> List[Dict]:
        """Full metadata rows for every matched campaign."""
        cursor = self.conn.execute(
            "SELECT finance_campaign_id, prop_num, election_year, election_month, "
            "       measure_db_id, measure_id, status, match_via "
            "FROM finance_campaign "
            "WHERE status = 'matched' ORDER BY election_year DESC, prop_num"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_campaign_metadata(self, finance_campaign_id: str) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM finance_campaign WHERE finance_campaign_id = ?",
            (finance_campaign_id,),
        ).fetchone()
        return dict(row) if row else None

    # ---- Per-campaign data -------------------------------------------------

    def get_finance_summary(self, finance_campaign_id: str) -> List[Dict]:
        cursor = self.conn.execute(
            "SELECT stance, total_receipts, n_committees, top5_share, hhi "
            "FROM finance_summary WHERE finance_campaign_id = ?",
            (finance_campaign_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_finance_timeline(self, finance_campaign_id: str) -> List[Dict]:
        cursor = self.conn.execute(
            "SELECT stance, week_start, weekly_receipts, cumulative_receipts "
            "FROM finance_timeline_weekly WHERE finance_campaign_id = ? "
            "ORDER BY week_start",
            (finance_campaign_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_top_donors(self, finance_campaign_id: str, limit: int = 10) -> List[Dict]:
        """Return top donors *per stance*, not per campaign. Codex caught this:
        a flat ORDER BY total_amount DESC LIMIT N across the campaign would
        crowd out the smaller side of an imbalanced fight (e.g. PROP_1_2024's
        oppose donors vanished entirely because support outspent ~30:1).
        Window function partitions the ranking by stance.
        """
        cursor = self.conn.execute(
            """
            SELECT stance, donor_name_canon, donor_type, total_amount
            FROM (
                SELECT stance, donor_name_canon, donor_type, total_amount,
                       ROW_NUMBER() OVER (PARTITION BY stance ORDER BY total_amount DESC, donor_name_canon) AS rn
                FROM finance_top_donors
                WHERE finance_campaign_id = ?
            )
            WHERE rn <= ?
            ORDER BY stance, total_amount DESC
            """,
            (finance_campaign_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_contribution_breakdown(self, finance_campaign_id: str) -> Dict:
        """Contribution-size distribution. The v2 rebuild does NOT yet have
        a per-campaign transaction table — that data layer is a future
        extension once we have a clean way to attribute individual transactions
        to campaigns (the v1 measure_committee_link join was the same source
        as the cross-cycle contamination Codex caught). For now, return an
        empty zero-buckets dict so consumers don't NPE.
        """
        return {
            "small": {"count": 0, "total": 0},
            "medium": {"count": 0, "total": 0},
            "large": {"count": 0, "total": 0},
            "mega": {"count": 0, "total": 0},
        }

    # ---- Cross-campaign aggregations ---------------------------------------

    def iter_summary_rows(self) -> Iterable[Dict]:
        """All (campaign, stance) summary rows, joined with campaign metadata.
        Used by build_finance_insights to compute cross-campaign aggregates
        (total receipts, better-funded-side win rate, etc.)."""
        cursor = self.conn.execute(
            "SELECT s.finance_campaign_id, s.stance, s.total_receipts, "
            "       s.n_committees, s.top5_share, s.hhi, "
            "       c.prop_num, c.election_year, c.measure_db_id, c.measure_id "
            "FROM finance_summary s "
            "JOIN finance_campaign c USING (finance_campaign_id) "
            "WHERE c.status = 'matched'"
        )
        for row in cursor:
            yield dict(row)

    def close(self):
        if self.conn:
            self.conn.close()


# ---------------------------------------------------------------------------
# Convenience wrappers for callers that historically passed a measure dict.
# These avoid scattering resolve_campaign() boilerplate across consumers.
# ---------------------------------------------------------------------------

def get_campaign_for_measure(db: FinanceDatabase, measure: Dict) -> Optional[str]:
    """Resolve a finance_campaign_id from a measure record. Tries id (db-id),
    then (measure_id, year). Returns None if no matched campaign exists.
    """
    if not measure:
        return None
    db_id = measure.get("id")
    if db_id is not None:
        cid = db.resolve_campaign(measure_db_id=int(db_id))
        if cid:
            return cid
    mid = measure.get("measure_id")
    year = measure.get("year")
    if mid:
        try:
            return db.resolve_campaign(measure_id=mid, year=int(year) if year else None)
        except ValueError:
            return None
    return None
