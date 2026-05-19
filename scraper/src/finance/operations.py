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
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Iterable, List, Dict, Optional

from .donor_sectors import get_donor_sector
from .schema import FINANCE_DB_PATH, FINANCE_DB_V3_PATH


class FinanceDatabase:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        v3_db_path: Optional[Path] = None,
    ):
        self.db_path = db_path or FINANCE_DB_PATH
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        # v3 connection is lazy — only opened when a get_*_total /
        # get_*_by_type method is called. Keeps v2-only consumers unaffected
        # if the v3 db isn't present (e.g. on a fresh checkout before
        # scripts/v3/ has been run).
        self._v3_db_path = v3_db_path or FINANCE_DB_V3_PATH
        self._v3_conn: Optional[sqlite3.Connection] = None

    @property
    def v3_conn(self) -> sqlite3.Connection:
        if self._v3_conn is None:
            self._v3_conn = sqlite3.connect(str(self._v3_db_path))
            self._v3_conn.row_factory = sqlite3.Row
        return self._v3_conn

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
            # ORDER BY election_year ASC so the on-cycle (earlier) campaign
            # wins over any year-offset recoveries that share this
            # measure_db_id — locks in deterministic behavior that previously
            # depended on SQLite insertion order. Most callers should now
            # prefer aggregate_for_measure() to see all campaigns; this is
            # kept for backwards-compat with single-id consumers.
            row = self.conn.execute(
                "SELECT finance_campaign_id FROM finance_campaign "
                "WHERE measure_db_id = ? AND status = 'matched' "
                "ORDER BY election_year ASC, finance_campaign_id ASC",
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
        """Full metadata rows for every matched campaign.

        Ordered so on-cycle campaigns come last for each measure_db_id — that
        way callers like `_load_finance_data` that key by measure_db_id and
        overwrite duplicates end up with the on-cycle campaign winning,
        regardless of SQLite insertion order. (Cleaner callers should use
        `aggregate_for_measure()` instead of overwriting.)
        """
        cursor = self.conn.execute(
            "SELECT finance_campaign_id, prop_num, election_year, election_month, "
            "       measure_db_id, measure_id, status, match_via "
            "FROM finance_campaign "
            "WHERE status = 'matched' "
            "ORDER BY measure_db_id, election_year DESC, finance_campaign_id"
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

        Each row also carries a `donor_sector` field — hand-curated lookup
        in `src/finance/donor_sectors.py`. Donors outside the lookup get
        `donor_sector=None` and render without a sector chip in the UI.
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
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            d["donor_sector"] = get_donor_sector(d["donor_name_canon"])
            rows.append(d)
        return rows

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

    # ---- Per-measure rollup (handles year-offset recovery collisions) ------

    def aggregate_for_measure(
        self,
        measure_db_id: int,
        donor_limit: int = 10,
    ) -> Optional[Dict]:
        """Roll up *all* matched finance campaigns linked to a single
        measure_db_id into one measure-level view. Necessary because the
        Bucket A year-lookback recovery (see `build_finance_crosswalk.py`)
        creates multiple finance_campaign_id rows that share a measure_db_id
        (e.g. PROP_4_2008 on-cycle + PROP_4_2010 late filings → both link
        to measure_db_id 1189). Per-campaign queries miss one side or the
        other; this rolls them together.

        Aggregation rules:
        - summary.total_receipts: SUM across campaigns per stance
        - summary.n_committees: SUM (best-effort; may double-count committees
          that filed across both campaigns, acceptable for display)
        - summary.top5_share + hhi: recomputed against the merged donor list
        - donors: union by donor_name_canon, summing total_amount, re-ranked
          top-N per stance
        - timeline: union weeks, summed weekly_receipts, cumulative recomputed
        - finance_campaign_id: returns the on-cycle (earliest-year) cid as the
          canonical primary; full list available in `all_campaign_ids`

        Returns None if no matched campaigns are linked to the measure_db_id.
        """
        rows = self.conn.execute(
            "SELECT finance_campaign_id FROM finance_campaign "
            "WHERE measure_db_id = ? AND status = 'matched' "
            "ORDER BY election_year ASC, finance_campaign_id ASC",
            (measure_db_id,),
        ).fetchall()
        if not rows:
            return None
        campaign_ids = [r[0] for r in rows]
        primary_cid = campaign_ids[0]
        placeholders = ",".join("?" for _ in campaign_ids)

        # 1. Merged donor list per stance (used for both summary recomputation
        #    and the top-donors output).
        donor_rows = self.conn.execute(
            f"""
            SELECT stance, donor_name_canon, donor_type,
                   SUM(total_amount) AS total_amount
            FROM finance_top_donors
            WHERE finance_campaign_id IN ({placeholders})
            GROUP BY stance, donor_name_canon, donor_type
            """,
            campaign_ids,
        ).fetchall()
        donors_by_stance: Dict[str, List[Dict]] = defaultdict(list)
        for d in donor_rows:
            donors_by_stance[d["stance"]].append({
                "donor_name_canon": d["donor_name_canon"],
                "donor_type": d["donor_type"],
                "total_amount": float(d["total_amount"] or 0),
            })
        # Sort each stance by amount desc with canonical-name tiebreak.
        for stance, lst in donors_by_stance.items():
            lst.sort(key=lambda d: (-d["total_amount"], d["donor_name_canon"]))

        # 2. Summary: sum receipts + committee counts per stance; recompute
        #    concentration metrics against the merged donor list.
        raw_summary = self.conn.execute(
            f"""
            SELECT stance,
                   SUM(total_receipts) AS total_receipts,
                   SUM(n_committees) AS n_committees
            FROM finance_summary
            WHERE finance_campaign_id IN ({placeholders})
            GROUP BY stance
            """,
            campaign_ids,
        ).fetchall()
        summary: List[Dict] = []
        for r in raw_summary:
            stance = r["stance"]
            stance_donors = donors_by_stance.get(stance, [])
            total = float(r["total_receipts"] or 0)
            top5_share: Optional[float] = None
            hhi: Optional[float] = None
            if total > 0 and stance_donors:
                top5_amount = sum(d["total_amount"] for d in stance_donors[:5])
                top5_share = (top5_amount / total) * 100
                # HHI = sum of (share% squared) across all donors. Capped at
                # 10000 by definition (one donor with 100% share -> 100^2).
                hhi = sum(
                    ((d["total_amount"] / total) * 100) ** 2
                    for d in stance_donors
                )
            summary.append({
                "stance": stance,
                "total_receipts": total,
                "n_committees": int(r["n_committees"] or 0),
                "top5_share": top5_share,
                "hhi": hhi,
            })

        # 3. Top donors per stance (after merging across campaigns). Sector
        #    lookup attached so consumers (modal, briefing, API) carry the
        #    same sector data without re-resolving it.
        top_donors: List[Dict] = []
        for stance, ranked in donors_by_stance.items():
            for d in ranked[:donor_limit]:
                top_donors.append({
                    "stance": stance,
                    "donor_name_canon": d["donor_name_canon"],
                    "donor_type": d["donor_type"],
                    "donor_sector": get_donor_sector(d["donor_name_canon"]),
                    "total_amount": d["total_amount"],
                })

        # 4. Timeline: union weeks, sum weekly_receipts, recompute cumulative.
        week_rows = self.conn.execute(
            f"""
            SELECT stance, week_start, SUM(weekly_receipts) AS weekly_receipts
            FROM finance_timeline_weekly
            WHERE finance_campaign_id IN ({placeholders})
            GROUP BY stance, week_start
            ORDER BY stance, week_start
            """,
            campaign_ids,
        ).fetchall()
        timeline: List[Dict] = []
        cumulative: Dict[str, float] = defaultdict(float)
        for r in week_rows:
            stance = r["stance"]
            weekly = float(r["weekly_receipts"] or 0)
            cumulative[stance] += weekly
            timeline.append({
                "stance": stance,
                "week_start": r["week_start"],
                "weekly_receipts": weekly,
                "cumulative_receipts": cumulative[stance],
            })

        return {
            "finance_campaign_id": primary_cid,
            "all_campaign_ids": campaign_ids,
            "summary": summary,
            "donors": top_donors,
            "timeline": timeline,
            "breakdown": self.get_contribution_breakdown(primary_cid),
        }

    # ---- Year-axis aggregates for the spending-arc chart ------------------

    def get_calendar_year_receipts(self) -> List[Dict]:
        """Sum `finance_timeline_weekly` receipts by the year of each week's
        Monday bucket (`week_start`). Used as the alternative lens in the
        spending-arc chart — counterpart to election-year aggregates.

        n_measures counts DISTINCT `measure_db_id`s so the Bucket A
        year-offset collisions (e.g. PROP_4_2008 + PROP_4_2010 both linked
        to measure_db_id 1189) collapse to one measure per calendar year.

        Reconciles to the election-year totals: SUM(total_receipts) across
        all calendar-year rows equals SUM(weekly_receipts) across the
        finance_timeline_weekly table (no rows dropped during aggregation).

        Caveat for callers/users: boundary weeks crossing Dec 31 are
        attributed to the week-start year (e.g. a transaction in the week
        of 2007-12-31 lands in the 2007 bucket even though the week
        extends into 2008). Real impact in the current DB: ~$18.8M at
        2007-12-31, ~$8.2M at 2012-12-31.
        """
        cursor = self.conn.execute(
            """
            SELECT
                CAST(substr(t.week_start, 1, 4) AS INTEGER) AS year,
                SUM(t.weekly_receipts) AS total_receipts,
                COUNT(DISTINCT c.measure_db_id) AS n_measures
            FROM finance_timeline_weekly t
            JOIN finance_campaign c USING (finance_campaign_id)
            WHERE c.status = 'matched'
            GROUP BY year
            ORDER BY year
            """
        )
        return [
            {
                "year": int(row["year"]),
                "total_receipts": float(row["total_receipts"] or 0),
                "n_measures": int(row["n_measures"] or 0),
            }
            for row in cursor.fetchall()
            if row["year"] is not None
        ]

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
        if self._v3_conn is not None:
            self._v3_conn.close()
            self._v3_conn = None

    # ---- v3: expanded-scope reads ----------------------------------------
    # All v3 methods key on `measure_db_id` (UI's natural handle) and roll
    # up year-offset collisions internally, mirroring `aggregate_for_measure`.
    # When a measure has multiple finance_campaign_ids (e.g. PROP_4_2008 +
    # PROP_4_2010 both linked to measure_db_id 1189), we SUM across them
    # per stance and recompute top5_share / hhi against the merged donor
    # list. UI gets one row per stance ([per receipt_type] for the by_type
    # variants), independent of the underlying campaign-id split.
    # ----------------------------------------------------------------------

    def _v3_campaign_ids_for_measure(self, measure_db_id: int) -> List[str]:
        """Pull every finance_campaign_id v3 has flows for under a measure.
        v3 carries `measure_db_id` directly on the fact table, so this is a
        single-table lookup (no join to finance_campaign).
        """
        rows = self.v3_conn.execute(
            "SELECT DISTINCT finance_campaign_id "
            "FROM finance_flow_v3 "
            "WHERE measure_db_id = ? AND quarantine_reason IS NULL "
            "  AND finance_campaign_id IS NOT NULL "
            "ORDER BY finance_campaign_id",
            (measure_db_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def _recompute_top5_hhi(
        self,
        total: float,
        merged_donors: List[Dict],
    ) -> tuple[Optional[float], Optional[float]]:
        """Recompute top5_share (%) and HHI (0..10000) against a merged
        donor list. Returns (None, None) when total <= 0 or no donors."""
        if total <= 0 or not merged_donors:
            return None, None
        top5_amount = sum(d["total_amount"] for d in merged_donors[:5])
        top5_share = (top5_amount / total) * 100
        hhi = sum(
            ((d["total_amount"] / total) * 100) ** 2 for d in merged_donors
        )
        return top5_share, hhi

    def get_finance_summary_total(self, measure_db_id: int) -> List[Dict]:
        """Per-stance totals across ALL receipt types (monetary + loan +
        in-kind + IE). Rolls up multi-campaign collisions.

        Each row: {stance, total_amount, n_committees, n_transactions,
                   top5_share, hhi}
        Empty list if no v3 flows for this measure.
        """
        campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
        if not campaign_ids:
            return []
        placeholders = ",".join("?" for _ in campaign_ids)

        raw = self.v3_conn.execute(
            f"""
            SELECT stance,
                   SUM(total_amount) AS total_amount,
                   SUM(n_committees) AS n_committees,
                   SUM(n_transactions) AS n_transactions
            FROM finance_summary_total
            WHERE finance_campaign_id IN ({placeholders})
            GROUP BY stance
            """,
            campaign_ids,
        ).fetchall()

        # Recompute top5_share + hhi against the merged donor list per
        # stance — view-level metrics are per-campaign, would be wrong
        # under rollup.
        donor_rows = self.v3_conn.execute(
            f"""
            SELECT stance, donor_name_canon, SUM(total_amount) AS total_amount
            FROM finance_top_donors_total
            WHERE finance_campaign_id IN ({placeholders})
            GROUP BY stance, donor_name_canon
            """,
            campaign_ids,
        ).fetchall()
        donors_by_stance: Dict[str, List[Dict]] = defaultdict(list)
        for r in donor_rows:
            donors_by_stance[r["stance"]].append({
                "donor_name_canon": r["donor_name_canon"],
                "total_amount": float(r["total_amount"] or 0),
            })
        for lst in donors_by_stance.values():
            lst.sort(key=lambda d: (-d["total_amount"], d["donor_name_canon"]))

        out: List[Dict] = []
        for r in raw:
            stance = r["stance"]
            total = float(r["total_amount"] or 0)
            top5_share, hhi = self._recompute_top5_hhi(
                total, donors_by_stance.get(stance, [])
            )
            out.append({
                "stance": stance,
                "total_amount": total,
                "n_committees": int(r["n_committees"] or 0),
                "n_transactions": int(r["n_transactions"] or 0),
                "top5_share": top5_share,
                "hhi": hhi,
            })
        return out

    def get_finance_breakdown_by_type(self, measure_db_id: int) -> List[Dict]:
        """Per-stance, per-receipt-type breakdown. Rolls up multi-campaign
        collisions; top5_share + hhi recomputed against merged donors
        within each (stance, receipt_type) slice.

        Each row: {stance, receipt_type, total_amount, n_committees,
                   n_transactions, top5_share, hhi}
        receipt_type ∈ {monetary_contribution, loan, in_kind,
                        independent_expenditure}
        """
        campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
        if not campaign_ids:
            return []
        placeholders = ",".join("?" for _ in campaign_ids)

        raw = self.v3_conn.execute(
            f"""
            SELECT stance, receipt_type,
                   SUM(total_amount) AS total_amount,
                   SUM(n_committees) AS n_committees,
                   SUM(n_transactions) AS n_transactions
            FROM finance_summary_by_type
            WHERE finance_campaign_id IN ({placeholders})
            GROUP BY stance, receipt_type
            ORDER BY stance, receipt_type
            """,
            campaign_ids,
        ).fetchall()

        # Per-(stance, receipt_type) merged donor lists for concentration
        # recomputation. finance_top_donors_by_type already keys on
        # receipt_type so this is one query.
        donor_rows = self.v3_conn.execute(
            f"""
            SELECT stance, receipt_type, donor_name_canon,
                   SUM(total_amount) AS total_amount
            FROM finance_top_donors_by_type
            WHERE finance_campaign_id IN ({placeholders})
            GROUP BY stance, receipt_type, donor_name_canon
            """,
            campaign_ids,
        ).fetchall()
        donors_by_slice: Dict[tuple, List[Dict]] = defaultdict(list)
        for r in donor_rows:
            donors_by_slice[(r["stance"], r["receipt_type"])].append({
                "donor_name_canon": r["donor_name_canon"],
                "total_amount": float(r["total_amount"] or 0),
            })
        for lst in donors_by_slice.values():
            lst.sort(key=lambda d: (-d["total_amount"], d["donor_name_canon"]))

        out: List[Dict] = []
        for r in raw:
            slice_key = (r["stance"], r["receipt_type"])
            total = float(r["total_amount"] or 0)
            top5_share, hhi = self._recompute_top5_hhi(
                total, donors_by_slice.get(slice_key, [])
            )
            out.append({
                "stance": r["stance"],
                "receipt_type": r["receipt_type"],
                "total_amount": total,
                "n_committees": int(r["n_committees"] or 0),
                "n_transactions": int(r["n_transactions"] or 0),
                "top5_share": top5_share,
                "hhi": hhi,
            })
        return out

    @staticmethod
    def _parse_json_array(raw: Optional[str]) -> List[str]:
        """Parse the json_group_array output from v3 views; tolerant of
        NULL / malformed entries."""
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        return [v for v in parsed if v is not None]

    def get_top_donors_total(
        self,
        measure_db_id: int,
        *,
        stance: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Top-N donors per stance across ALL receipt types, rolled up
        across any year-offset-collision campaigns under one measure.
        Ranking is partitioned by stance so the smaller side of an
        imbalanced fight doesn't get crowded out (v2 pattern).

        donor_sector is re-resolved at query time via
        `donor_sectors.get_donor_sector` so curated updates land in the
        UI without a v3 rebuild.

        Each row: {stance, donor_name_canon, donor_type, donor_sector,
                   total_amount, flow_types (list), primary_attribution_source,
                   n_underlying_rows}
        """
        campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
        if not campaign_ids:
            return []
        placeholders = ",".join("?" for _ in campaign_ids)

        params: List = list(campaign_ids)
        stance_clause = ""
        if stance is not None:
            stance_clause = "AND stance = ?"
            params.append(stance)

        # Roll up: SUM total_amount across campaigns, then per-stance
        # ROW_NUMBER. flow_types unioned across campaigns (parsed JSON
        # arrays merged). primary_attribution_source picked as the
        # source with the largest attr_total under the merged donor.
        cursor = self.v3_conn.execute(
            f"""
            WITH per_donor AS (
                SELECT stance, donor_name_canon,
                       SUM(total_amount) AS total_amount,
                       MAX(donor_type)   AS donor_type,
                       SUM(n_underlying_rows) AS n_underlying_rows,
                       json_group_array(flow_types) AS flow_types_nested,
                       json_group_array(primary_attribution_source)
                           AS attr_sources_nested
                FROM   finance_top_donors_total
                WHERE  finance_campaign_id IN ({placeholders}) {stance_clause}
                GROUP  BY stance, donor_name_canon
            ),
            ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY stance
                           ORDER BY total_amount DESC, donor_name_canon
                       ) AS rn
                FROM   per_donor
            )
            SELECT stance, donor_name_canon, donor_type, total_amount,
                   n_underlying_rows, flow_types_nested, attr_sources_nested
            FROM   ranked
            WHERE  rn <= ?
            ORDER  BY stance, total_amount DESC, donor_name_canon
            """,
            (*params, limit),
        )

        rows: List[Dict] = []
        for r in cursor.fetchall():
            # Merge nested json arrays: per_donor's json_group_array of
            # json arrays produces e.g. '["[\"loan\",\"in_kind\"]","[...]"]'.
            # Parse each leg, union into one flat list.
            flow_types: List[str] = []
            seen: set = set()
            for leg in self._parse_json_array(r["flow_types_nested"]):
                for ft in self._parse_json_array(leg):
                    if ft not in seen:
                        flow_types.append(ft)
                        seen.add(ft)
            attr_legs: List[str] = []
            for leg in self._parse_json_array(r["attr_sources_nested"]):
                if leg and leg not in attr_legs:
                    attr_legs.append(leg)
            rows.append({
                "stance": r["stance"],
                "donor_name_canon": r["donor_name_canon"],
                "donor_type": r["donor_type"],
                "donor_sector": get_donor_sector(r["donor_name_canon"]),
                "total_amount": float(r["total_amount"] or 0),
                "flow_types": flow_types,
                "primary_attribution_source": attr_legs[0] if attr_legs else None,
                "n_underlying_rows": int(r["n_underlying_rows"] or 0),
            })
        return rows

    def get_top_donors_by_type(
        self,
        measure_db_id: int,
        receipt_type: str,
        *,
        stance: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Top-N donors filtered to a single receipt_type, per stance,
        rolled up across collision campaigns.

        Each row: {stance, receipt_type, donor_name_canon, donor_type,
                   donor_sector, total_amount, n_underlying_rows,
                   attribution_source_mode}
        """
        campaign_ids = self._v3_campaign_ids_for_measure(measure_db_id)
        if not campaign_ids:
            return []
        placeholders = ",".join("?" for _ in campaign_ids)

        params: List = list(campaign_ids) + [receipt_type]
        stance_clause = ""
        if stance is not None:
            stance_clause = "AND stance = ?"
            params.append(stance)

        cursor = self.v3_conn.execute(
            f"""
            WITH per_donor AS (
                SELECT stance, receipt_type, donor_name_canon,
                       SUM(total_amount) AS total_amount,
                       MAX(donor_type)   AS donor_type,
                       SUM(n_underlying_rows) AS n_underlying_rows,
                       MAX(attribution_source_mode) AS attribution_source_mode
                FROM   finance_top_donors_by_type
                WHERE  finance_campaign_id IN ({placeholders})
                  AND  receipt_type = ?
                  {stance_clause}
                GROUP  BY stance, receipt_type, donor_name_canon
            ),
            ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY stance
                           ORDER BY total_amount DESC, donor_name_canon
                       ) AS rn
                FROM   per_donor
            )
            SELECT stance, receipt_type, donor_name_canon, donor_type,
                   total_amount, n_underlying_rows, attribution_source_mode
            FROM   ranked
            WHERE  rn <= ?
            ORDER  BY stance, total_amount DESC, donor_name_canon
            """,
            (*params, limit),
        )

        return [
            {
                "stance": r["stance"],
                "receipt_type": r["receipt_type"],
                "donor_name_canon": r["donor_name_canon"],
                "donor_type": r["donor_type"],
                "donor_sector": get_donor_sector(r["donor_name_canon"]),
                "total_amount": float(r["total_amount"] or 0),
                "n_underlying_rows": int(r["n_underlying_rows"] or 0),
                "attribution_source_mode": r["attribution_source_mode"],
            }
            for r in cursor.fetchall()
        ]


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
