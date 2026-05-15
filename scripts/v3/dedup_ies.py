"""Phase 4 post-ingest dedup pass for IE flows.

Codex round-10: same underlying IE transaction can be reported in
S496_CD (24-hour late filing) AND in EXPN_CD F465P3 / F461P5
(periodic Form 465 / 461 schedules). Rule 5 precedence collapses
these to a single winning row.

This pass runs AFTER ingest_ies has written accepted rows. For each
group of accepted rows sharing the same economic_fingerprint, picks
the winner via source-table priority (lower number = wins):

    1  EXPN_CD F461P5  (periodic major-donor IE)
    2  EXPN_CD F465P3  (periodic Form 465 supplemental IE)
    3  S496_CD F496    (24-hour late IE)

Tiebreaker: lowest source_fingerprint string (deterministic).

Losers are marked:
    quarantine_reason = 'duplicate_economic_fingerprint'
    dedupe_winner_flow_id = <winner's flow_id>
    dedupe_rule = 'source_table_priority'

Idempotent: clears any prior duplicate_economic_fingerprint marks
before re-running. Winner's dedupe_winner_flow_id / dedupe_rule
stay NULL (it wasn't dedup-eliminated).

Usage:
    python scripts/v3/dedup_ies.py
    python scripts/v3/dedup_ies.py --dry-run
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
else:
    from . import lib


PRIORITY = {
    ("EXPN_CD", "F461P5"): 1,
    ("EXPN_CD", "F465P3"): 2,
    ("S496_CD", "F496"): 3,
}


def dedup_ies(v3_db: Path, dry_run: bool = False,
              verbose: bool = True) -> dict:
    con = sqlite3.connect(str(v3_db), isolation_level=None)
    try:
        cur = con.cursor()

        # Step 1: clear any prior duplicate_economic_fingerprint marks
        # so we start clean (idempotent re-run)
        if not dry_run:
            cur.execute("BEGIN")
            cur.execute(
                "UPDATE finance_flow_v3 "
                "SET quarantine_reason = NULL, "
                "    dedupe_winner_flow_id = NULL, "
                "    dedupe_rule = NULL "
                "WHERE quarantine_reason = 'duplicate_economic_fingerprint'"
            )
            cur.execute("COMMIT")

        # Step 2: identify duplicate groups. Only accepted IE rows
        # (those with quarantine_reason IS NULL and receipt_type
        # 'independent_expenditure') participate.
        rows = list(cur.execute(
            "SELECT flow_id, source_table, source_form_type, "
            "       source_fingerprint, economic_fingerprint, amount "
            "FROM finance_flow_v3 "
            "WHERE receipt_type = 'independent_expenditure' "
            "  AND quarantine_reason IS NULL "
            "  AND economic_fingerprint IS NOT NULL"
        ))

        groups: dict[str, list] = defaultdict(list)
        for r in rows:
            flow_id, src, ft, src_fp, econ_fp, amount = r
            groups[econ_fp].append(
                (flow_id, src, ft, src_fp, amount)
            )

        winners: dict[str, int] = {}
        losers: list[tuple[int, int]] = []  # (loser_flow_id, winner_flow_id)
        groups_with_dups = 0
        total_losers_amount = 0.0
        total_winners_amount = 0.0

        for econ_fp, group in groups.items():
            if len(group) == 1:
                continue
            groups_with_dups += 1
            # Pick winner: lowest priority, then lowest source_fingerprint
            ranked = sorted(
                group,
                key=lambda g: (
                    PRIORITY.get((g[1], g[2]), 99),
                    g[3] or "",
                ),
            )
            winner = ranked[0]
            winner_flow_id = winner[0]
            winners[econ_fp] = winner_flow_id
            total_winners_amount += winner[4] or 0
            for loser in ranked[1:]:
                losers.append((loser[0], winner_flow_id))
                total_losers_amount += loser[4] or 0

        if verbose:
            print(f"Accepted IE rows scanned:       {len(rows):,}")
            print(f"Distinct economic_fingerprints: {len(groups):,}")
            print(f"Groups with duplicates:         {groups_with_dups:,}")
            print(f"Losers to mark:                 {len(losers):,}")
            print(f"  Loser dollars (would be removed from totals): "
                  f"${total_losers_amount:,.2f}")
            print(f"  Winner dollars retained: "
                  f"${total_winners_amount:,.2f}")

        if dry_run:
            return {
                "groups_with_dups": groups_with_dups,
                "losers": len(losers),
                "loser_dollars": total_losers_amount,
            }

        # Step 3: mark losers
        if losers:
            cur.execute("BEGIN")
            cur.executemany(
                "UPDATE finance_flow_v3 "
                "SET quarantine_reason = 'duplicate_economic_fingerprint', "
                "    dedupe_winner_flow_id = ?, "
                "    dedupe_rule = 'source_table_priority' "
                "WHERE flow_id = ?",
                [(winner_id, loser_id) for loser_id, winner_id in losers],
            )
            cur.execute("COMMIT")

        if verbose:
            print(f"Marked {len(losers):,} losers as "
                  f"duplicate_economic_fingerprint")

        return {
            "groups_with_dups": groups_with_dups,
            "losers": len(losers),
            "loser_dollars": total_losers_amount,
        }
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-db", default=str(lib.V3_DB))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dedup_ies(Path(args.v3_db), dry_run=args.dry_run, verbose=True)


if __name__ == "__main__":
    main()
