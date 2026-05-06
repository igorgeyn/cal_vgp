#!/usr/bin/env python3
"""
DEPRECATED 2026-05-04. DO NOT RUN. Use scripts/rebuild_finance_db.py instead.

This is the v1 ETL script for the original (contaminated) finance_statewide.db.
The crosswalk it built used `WHERE measure_id LIKE 'PROP_%'` and assigned
committees by receipt date instead of the source CSV's `year` column. That
collapsed cross-cycle proposition-number reuse — e.g. 2010 PG&E money was
attributed to the 2020 PROP_16 measure, 2012 Paycheck Protection money to
2024 PROP_32, etc. See plans/finance-panel-redesign.md for the full story.

This file is preserved for historical reference only. It will not import
because `SCHEMA_SQL` was removed from `src.finance.schema` during the v2
rewrite. The replacement is `scripts/rebuild_finance_db.py`, which produces
`data/finance/finance_statewide_v2.db` keyed on year-scoped
`finance_campaign_id`.

If you find yourself wanting to run this: stop. The thing you actually want
is `python -m scripts.rebuild_finance_db`.
"""
raise SystemExit(
    "build_statewide_prop_finance_db.py is deprecated. "
    "Run `python -m scripts.rebuild_finance_db` instead. "
    "See plans/finance-panel-redesign.md for context."
)
import argparse
import csv
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.finance.schema import FINANCE_DB_PATH, SCHEMA_SQL

DEFAULT_CSV = Path(__file__).parent.parent / "data" / "finance" / "calaccess_raw" / "ballot_measure_receipts_clean.csv"
MAIN_DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"


def parse_calaccess_date(raw: str) -> Optional[str]:
    """Parse CAL-ACCESS date 'M/D/YYYY 12:00:00 AM' -> 'YYYY-MM-DD'."""
    if not raw or not raw.strip():
        return None
    s = raw.strip().split(" ")[0]
    try:
        dt = datetime.strptime(s, "%m/%d/%Y")
        if dt.year < 1990 or dt.year > 2030:
            return None
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def iso_week_start(date_str: str) -> str:
    """Return the Monday of the ISO week containing the given date."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def build_prop_to_measure_id(main_db_path: Path) -> dict:
    """
    Build crosswalk from (prop_num, election_year) -> measure_id.

    Also builds a simpler prop_num -> [(measure_id, year)] lookup so we can
    assign receipts to the right election cycle based on receipt date.
    """
    conn = sqlite3.connect(str(main_db_path))
    cur = conn.cursor()
    cur.execute("""
        SELECT measure_id, year FROM measures
        WHERE county = 'Statewide' AND measure_id LIKE 'PROP_%'
        ORDER BY year
    """)
    rows = cur.fetchall()
    conn.close()

    # prop_num -> sorted list of (year, measure_id)
    prop_years = defaultdict(list)
    for mid, year in rows:
        # PROP_36 -> "36", PROP_1A -> "1A"
        pnum = mid.replace("PROP_", "")
        prop_years[pnum].append((year, mid))

    # Sort each by year
    for pnum in prop_years:
        prop_years[pnum].sort()

    return dict(prop_years)


def assign_measure_id(prop_num: str, receipt_date: Optional[str], prop_years: dict) -> Optional[str]:
    """
    Given a prop_num and receipt date, find the best matching measure_id.

    Strategy: assign to the election cycle whose year is closest to (and >= )
    the receipt's year. If no date, use the latest election cycle.
    """
    candidates = prop_years.get(prop_num)
    if not candidates:
        # Try uppercase
        candidates = prop_years.get(prop_num.upper())
    if not candidates:
        return None

    if receipt_date:
        try:
            receipt_year = int(receipt_date[:4])
        except (ValueError, TypeError):
            receipt_year = None
    else:
        receipt_year = None

    if receipt_year is None:
        # No date -> assign to latest cycle
        return candidates[-1][1]

    # Find the election cycle that this receipt most likely belongs to.
    # Receipts typically arrive 1-2 years before the election year.
    # Assign to the smallest election year >= receipt_year - 1.
    best = None
    for ey, mid in candidates:
        if ey >= receipt_year - 1:
            best = mid
            break
    if best is None:
        # Receipt is after all known elections — assign to latest
        best = candidates[-1][1]
    return best


def canonicalize_donor(last: str, first: str) -> str:
    """Basic donor name canonicalization."""
    name = last.strip().upper()
    # Strip trailing punctuation
    name = re.sub(r'[.,;:]+$', '', name)
    # Standardize common suffixes
    name = re.sub(r'\bINC\b\.?', 'INC', name)
    name = re.sub(r'\bLLC\b\.?', 'LLC', name)
    name = re.sub(r'\bCORP\b\.?', 'CORP', name)
    name = re.sub(r'\bCO\b\.?', 'CO', name)
    name = re.sub(r'\bL\.?P\.?\b', 'LP', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def build_db(csv_path: Path, db_path: Path, main_db_path: Path) -> None:
    # Build crosswalk
    print(f"Building prop->measure_id crosswalk from {main_db_path}...")
    prop_years = build_prop_to_measure_id(main_db_path)
    print(f"  {len(prop_years)} prop numbers with {sum(len(v) for v in prop_years.values())} measure_id mappings")

    # Create/reset finance DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)

    # Read CSV
    print(f"Reading {csv_path}...")
    rows = []
    skipped_no_measure = 0
    skipped_no_date = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_iso = parse_calaccess_date(row.get("date", ""))
            measure_id = assign_measure_id(row["prop_num"], date_iso, prop_years)
            if not measure_id:
                skipped_no_measure += 1
                continue
            row["_measure_id"] = measure_id
            row["_date_iso"] = date_iso
            rows.append(row)

    print(f"  {len(rows):,} rows mapped to measure_ids")
    print(f"  {skipped_no_measure:,} skipped (no matching measure_id)")

    # 1. Insert committees (deduplicated by filer_id)
    committees = {}
    for r in rows:
        fid = r["filer_id"]
        if fid not in committees:
            committees[fid] = (fid, r["committee_name"], "ballot_measure", "calaccess")
    conn.executemany(
        "INSERT INTO committee (committee_id, name, filer_type, source) VALUES (?, ?, ?, ?)",
        committees.values(),
    )
    print(f"Inserted {len(committees):,} committees")

    # 2. Insert transactions (batch for performance)
    txn_batch = []
    for r in rows:
        try:
            amt = float(r.get("amount", "0") or "0")
        except ValueError:
            continue
        date_iso = r["_date_iso"] or "1900-01-01"
        # Support both old format (donor_last/donor_first) and new format (donor_name)
        donor_name = r.get("donor_name", "").strip()
        if not donor_name:
            donor_raw = r.get("donor_last", "").strip()
            donor_first = r.get("donor_first", "").strip()
            donor_name = f"{donor_raw}, {donor_first}".strip(", ") if donor_first else donor_raw
        donor_display = donor_name
        donor_canon = canonicalize_donor(donor_name, "")
        entity_cd = r.get("entity_cd", r.get("donor_type", "")).strip()

        txn_batch.append((
            r["filer_id"], date_iso, amt, "monetary",
            donor_display, donor_canon, entity_cd, None, "calaccess"
        ))

    conn.executemany(
        """INSERT INTO transaction_record
           (committee_id, date, amount, txn_type, donor_name_raw, donor_name_canon, donor_type, donor_sector, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        txn_batch,
    )
    print(f"Inserted {len(txn_batch):,} transactions")

    # 3. Insert measure_committee_link (skip unknown stance)
    links = {}
    for r in rows:
        stance = r.get("stance", "").strip().lower()
        if stance not in ("support", "oppose"):
            continue
        key = (r["_measure_id"], r["filer_id"])
        if key not in links:
            links[key] = (r["_measure_id"], r["filer_id"], stance, "calaccess_cvr", 1.0, "calaccess")
    conn.executemany(
        "INSERT INTO measure_committee_link (measure_id, committee_id, stance, link_method, confidence, source) VALUES (?, ?, ?, ?, ?, ?)",
        links.values(),
    )
    print(f"Inserted {len(links):,} measure-committee links")

    # 4. Compute measure_finance_summary
    summary = defaultdict(lambda: {"total": 0.0, "committees": set()})
    donor_totals_by_group = defaultdict(lambda: defaultdict(float))

    for r in rows:
        try:
            amt = float(r.get("amount", "0") or "0")
        except ValueError:
            continue
        mid = r["_measure_id"]
        stance = r.get("stance", "").strip().lower()
        if stance not in ("support", "oppose"):
            continue
        key = (mid, stance)
        summary[key]["total"] += amt
        summary[key]["committees"].add(r["filer_id"])

        dn = r.get("donor_name", "") or f"{r.get('donor_last', '')}, {r.get('donor_first', '')}".strip(", ")
        donor_canon = canonicalize_donor(dn, "")
        if donor_canon:
            donor_totals_by_group[key][donor_canon] += amt

    for key, info in summary.items():
        total = info["total"]
        donors = donor_totals_by_group[key]
        sorted_amounts = sorted(donors.values(), reverse=True)

        top5_total = sum(sorted_amounts[:5])
        top5_share = (top5_total / total * 100) if total > 0 else None
        hhi = sum((a / total * 100) ** 2 for a in sorted_amounts) if total > 0 else None

        conn.execute(
            "INSERT INTO measure_finance_summary (measure_id, stance, total_receipts, n_committees, top5_share, hhi) VALUES (?, ?, ?, ?, ?, ?)",
            (key[0], key[1], round(total, 2), len(info["committees"]),
             round(top5_share, 2) if top5_share else None,
             round(hhi, 2) if hhi else None),
        )
    print(f"Inserted {len(summary):,} summary rows")

    # 5. Compute weekly timeline
    weekly = defaultdict(float)
    for r in rows:
        date_iso = r["_date_iso"]
        if not date_iso:
            continue
        stance = r.get("stance", "").strip().lower()
        if stance not in ("support", "oppose"):
            continue
        try:
            amt = float(r.get("amount", "0") or "0")
        except ValueError:
            continue
        wk = iso_week_start(date_iso)
        key = (r["_measure_id"], stance, wk)
        weekly[key] += amt

    timeline_groups = defaultdict(list)
    for (mid, stance, wk), amt in sorted(weekly.items()):
        timeline_groups[(mid, stance)].append((wk, amt))

    timeline_count = 0
    for (mid, stance), entries in timeline_groups.items():
        cumulative = 0.0
        for wk, amt in entries:
            cumulative += amt
            conn.execute(
                "INSERT INTO measure_finance_timeline_weekly (measure_id, stance, week_start, weekly_receipts, cumulative_receipts) VALUES (?, ?, ?, ?, ?)",
                (mid, stance, wk, round(amt, 2), round(cumulative, 2)),
            )
            timeline_count += 1
    print(f"Inserted {timeline_count:,} timeline rows")

    # 6. Compute top donors (top 10 per measure+stance)
    donor_meta = defaultdict(lambda: (None, None))
    for r in rows:
        stance = r.get("stance", "").strip().lower()
        if stance not in ("support", "oppose"):
            continue
        key = (r["_measure_id"], stance)
        dn = r.get("donor_name", "") or f"{r.get('donor_last', '')}, {r.get('donor_first', '')}".strip(", ")
        canon = canonicalize_donor(dn, "")
        if canon:
            entity_cd = r.get("entity_cd", r.get("donor_type", "")).strip()
            donor_meta[(key, canon)] = (entity_cd, None)

    donor_count = 0
    for (mid, stance), donors in donor_totals_by_group.items():
        sorted_donors = sorted(donors.items(), key=lambda x: x[1], reverse=True)[:10]
        for name, total_amt in sorted_donors:
            dtype, dsector = donor_meta.get(((mid, stance), name), (None, None))
            conn.execute(
                "INSERT INTO measure_top_donors (measure_id, stance, donor_name_canon, donor_type, donor_sector, total_amount) VALUES (?, ?, ?, ?, ?, ?)",
                (mid, stance, name, dtype, dsector, round(total_amt, 2)),
            )
            donor_count += 1
    print(f"Inserted {donor_count:,} top donor rows")

    conn.commit()
    conn.close()
    size_kb = db_path.stat().st_size / 1024
    if size_kb > 1024:
        print(f"\nFinance DB created at {db_path} ({size_kb / 1024:.1f} MB)")
    else:
        print(f"\nFinance DB created at {db_path} ({size_kb:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Build statewide prop finance DB from CAL-ACCESS receipts")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Input CSV path")
    parser.add_argument("--db", type=Path, default=FINANCE_DB_PATH, help="Output DB path")
    parser.add_argument("--main-db", type=Path, default=MAIN_DB_PATH, help="Main ballot measures DB (for crosswalk)")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"Error: CSV not found at {args.csv}", file=sys.stderr)
        sys.exit(1)
    if not args.main_db.exists():
        print(f"Error: Main DB not found at {args.main_db}", file=sys.stderr)
        sys.exit(1)

    build_db(args.csv, args.db, args.main_db)


if __name__ == "__main__":
    main()
