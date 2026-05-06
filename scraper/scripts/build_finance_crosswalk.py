"""
Build the (prop_num, election_year, election_month) -> measure_db_id crosswalk.

Step 2 of the finance rebuild. The current finance DB joins everything by bare
PROP_xx, which conflates election cycles (e.g. PROP_16 covers both the 2010
PG&E anti-municipal-utility prop and the 2020 repeal-Prop-209 measure). This
script walks the cleaned CalAccess source CSV (`ballot_measure_receipts_clean.csv`),
collects every distinct (prop_num, election_year) pair, and tries to resolve
each one to exactly one active row in the measures DB.

Output: `scraper/data/finance/finance_crosswalk.csv` with one row per
(prop_num, election_year, election_month) tuple, classified as:

    matched      — exactly one measures-DB record matches; safe to link
    duplicate    — multiple measures-DB records match; needs hand-resolution
    missing      — no measures-DB record found (likely a campaign before
                   our coverage window, or that didn't qualify)
    no_prop_number — prop_num is non-numeric junk (recall petitions,
                   circulating initiatives, "SEE_ATTACHMENT" placeholders)

The script also assigns each crosswalk row a stable `finance_campaign_id`
of the form `PROP_<num>_<year>` (e.g. `PROP_16_2020`, `PROP_1_2024`), which
Step 3 will use as the canonical campaign identity in the rebuilt finance DB.

This script is idempotent: rerun any time without side effects, just rewrites
the CSV.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_CSV = REPO_ROOT / "scraper" / "data" / "finance" / "calaccess_raw" / "ballot_measure_receipts_clean.csv"
MEASURES_DB = REPO_ROOT / "scraper" / "data" / "ballot_measures.db"
OUTPUT_CSV = REPO_ROOT / "scraper" / "data" / "finance" / "finance_crosswalk.csv"


# A prop_num is "real" iff it's purely digits (1, 22, 50) or a digit+letter
# (1A, 1B). Everything else is recall language, circulating-petition titles,
# or import garbage — we can't link those to numbered props.
PROP_NUM_RE = re.compile(r"^(\d+)([A-Z])?$")


def is_real_prop_num(s: str) -> bool:
    return bool(PROP_NUM_RE.match((s or "").strip().upper()))


def collect_csv_pairs(csv_path: Path) -> tuple[dict, Counter]:
    """Walk the source CSV once. Return:
       - pairs: {(prop_num_canonical, year_int): {n_rows, total_amount}}
       - quarantine_counts: Counter of why-rows-were-quarantined buckets
    """
    pairs: dict[tuple[str, int], dict] = defaultdict(lambda: {"n_rows": 0, "total_amount": 0.0})
    quarantine = Counter()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prop_num_raw = (row.get("prop_num") or "").strip()
            year_raw = (row.get("year") or "").strip()

            try:
                amount = float(row.get("amount") or 0)
            except ValueError:
                amount = 0.0

            if not is_real_prop_num(prop_num_raw):
                quarantine["non_numeric_prop_num"] += 1
                continue

            if not year_raw:
                quarantine["empty_year"] += 1
                continue

            try:
                year = int(year_raw)
            except ValueError:
                quarantine["bad_year"] += 1
                continue

            if year < 1990 or year > 2030:
                # 1900 placeholders, future-dated noise. Real CalAccess
                # statewide prop coverage starts mid-90s.
                quarantine["out_of_range_year"] += 1
                continue

            prop_canonical = prop_num_raw.upper()
            key = (prop_canonical, year)
            pairs[key]["n_rows"] += 1
            pairs[key]["total_amount"] += amount

    return pairs, quarantine


def load_measures_index(measures_db: Path) -> dict:
    """Build a lookup: (prop_num_str, year_int) -> list of (measure_db_id,
    measure_id_str, election_date_str).

    Indexes the active, non-duplicate statewide measures by extracting the
    prop number from either the short PROP_xx form (2018+) or the long-form
    "Proposition X" / "Proposition Item N" titles (2014/2016 and earlier).
    """
    conn = sqlite3.connect(str(measures_db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, measure_id, year, election_date, title
        FROM measures
        WHERE county = 'Statewide'
          AND is_active = 1
          AND is_duplicate = 0
          AND year IS NOT NULL
        """
    ).fetchall()
    conn.close()

    index: dict[tuple[str, int], list] = defaultdict(list)

    short_re = re.compile(r"^PROP_(\d+[A-Z]?)$", re.IGNORECASE)
    # 2018 (and some 2014/2016) records have measure_id literally set to
    # "Proposition 10", "Proposition Item 15", etc. — not in the title field.
    mid_long_re = re.compile(r"^Proposition\s+(?:Item\s+)?(\d+[A-Z]?)\b", re.IGNORECASE)
    title_short_re = re.compile(r"\bProposition\s+(\d+[A-Z]?)\b", re.IGNORECASE)
    title_item_re = re.compile(r"\bProposition\s+Item\s+(\d+)\b", re.IGNORECASE)

    def add_match(prop_canonical: str, year: int, row, via: str) -> None:
        index[(prop_canonical, year)].append({
            "measure_db_id": row["id"],
            "measure_id": row["measure_id"] or "",
            "election_date": row["election_date"],
            "title": row["title"] or "",
            "match_via": via,
        })

    for r in rows:
        year = int(r["year"])
        mid = r["measure_id"] or ""
        title = r["title"] or ""

        # 1. Canonical short form (2018+).
        m = short_re.match(mid)
        if m:
            add_match(m.group(1).upper(), year, r, "short_form")
            continue

        # 2. Long form embedded in the measure_id itself (2014/2016/2018 mix).
        m = mid_long_re.match(mid)
        if m:
            add_match(m.group(1).upper(), year, r, "mid_long")
            continue

        # 3. Long form in the title (rare fallback).
        m = title_short_re.search(title)
        if m:
            add_match(m.group(1).upper(), year, r, "title_short")
            continue

        m = title_item_re.search(title)
        if m:
            add_match(m.group(1).upper(), year, r, "title_item")

    return index


def parse_election_month(election_date: str | None) -> int | None:
    """`election_date` looks like '2020-03-05T00:00:00' or 'November 3, 2026' or
    is null. Try a couple of patterns; return None if we can't parse.
    """
    if not election_date:
        return None
    s = election_date.strip()
    # ISO-like
    m = re.match(r"^\d{4}-(\d{2})-\d{2}", s)
    if m:
        return int(m.group(1))
    # 'Month D, YYYY'
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
        "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
        "november": 11, "december": 12,
    }
    m = re.match(r"^([A-Za-z]+)", s)
    if m:
        return months.get(m.group(1).lower())
    return None


def resolve_pair(prop_num: str, year: int, candidates: list) -> dict:
    """Decide on a single measure_db_id for this (prop_num, year). Returns a
    dict with status, measure_db_id (or None), election_month, and a note.

    Preference rule for multiple candidates: id-based matches (short_form,
    mid_long) outrank title-based matches (title_short, title_item). This
    handles the 2014/2016 case where the measures DB has two active records
    per prop — one with `measure_id='Proposition 46'` (descriptive title)
    and one with `measure_id='CA1213'` (stub from a different ingest source
    whose title happens to be 'Proposition 46'). The first is canonical;
    the second should be treated as a soft duplicate that the dedup flags
    missed.
    """
    if not candidates:
        return {
            "status": "missing",
            "measure_db_id": None,
            "measure_id": None,
            "election_month": None,
            "match_via": None,
            "notes": "no measures-DB record",
        }

    # Filter to id-based matches if any exist; otherwise keep all.
    id_based = [c for c in candidates if c["match_via"] in ("short_form", "mid_long")]
    pool = id_based if id_based else candidates
    pool_was_filtered = len(id_based) > 0 and len(id_based) < len(candidates)

    if len(pool) == 1:
        c = pool[0]
        notes = ""
        if pool_was_filtered:
            n_dropped = len(candidates) - len(pool)
            notes = f"resolved by id-match preference; {n_dropped} title-only candidate(s) treated as soft duplicate"
        return {
            "status": "matched",
            "measure_db_id": c["measure_db_id"],
            "measure_id": c["measure_id"],
            "election_month": parse_election_month(c["election_date"]),
            "match_via": c["match_via"],
            "notes": notes,
        }

    # Multiple candidates remain even after preferring id-based matches.
    # Try to disambiguate by election month (March vs November 2020 case).
    by_month: dict[int | None, list] = defaultdict(list)
    for c in pool:
        by_month[parse_election_month(c["election_date"])].append(c)

    if len(by_month) == len(pool):
        # Each candidate has a distinct election month — clean disambiguation.
        # The CSV row only carries year, not month, so we still can't pick
        # one without more context. Mark as duplicate; Step 3 will need to
        # split receipts (by date) into the right month.
        months = sorted(m for m in by_month if m is not None)
        return {
            "status": "duplicate",
            "measure_db_id": None,
            "measure_id": None,
            "election_month": None,
            "match_via": None,
            "notes": f"multiple election months in same year: {months} — Step 3 must split by transaction date",
        }

    return {
        "status": "duplicate",
        "measure_db_id": None,
        "measure_id": None,
        "election_month": None,
        "match_via": None,
        "notes": f"{len(pool)} measures-DB records with no distinguishing election month",
    }


def main() -> None:
    print(f"Reading source CSV: {SOURCE_CSV}")
    pairs, quarantine = collect_csv_pairs(SOURCE_CSV)
    print(f"  Distinct (prop_num, year) tuples: {len(pairs)}")
    print("  Rows quarantined during CSV walk:")
    for reason, count in quarantine.most_common():
        print(f"    {reason}: {count:,}")

    print(f"\nIndexing measures DB: {MEASURES_DB}")
    measures_index = load_measures_index(MEASURES_DB)
    print(f"  Active statewide measures indexed by (prop_num, year): {sum(len(v) for v in measures_index.values())}")
    print(f"  Distinct (prop_num, year) keys in measures: {len(measures_index)}")

    print("\nResolving each CSV (prop_num, year) tuple against the measures index")

    results = []
    status_counts = Counter()
    matched_amount = 0.0
    unmatched_amount = 0.0

    for (prop_num, year), info in sorted(pairs.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        candidates = measures_index.get((prop_num, year), [])
        resolution = resolve_pair(prop_num, year, candidates)

        finance_campaign_id = f"PROP_{prop_num}_{year}"

        results.append({
            "finance_campaign_id": finance_campaign_id,
            "prop_num": prop_num,
            "election_year": year,
            "election_month": resolution["election_month"],
            "measure_db_id": resolution["measure_db_id"],
            "measure_id": resolution["measure_id"],
            "status": resolution["status"],
            "match_via": resolution["match_via"],
            "csv_row_count": info["n_rows"],
            "csv_total_amount": round(info["total_amount"], 2),
            "notes": resolution["notes"],
        })

        status_counts[resolution["status"]] += 1
        if resolution["status"] == "matched":
            matched_amount += info["total_amount"]
        else:
            unmatched_amount += info["total_amount"]

    print("\n=== Resolution summary ===")
    for status, count in status_counts.most_common():
        print(f"  {status}: {count}")
    print(f"\n  $ matched:   ${matched_amount/1e6:>11,.1f}M")
    print(f"  $ unmatched: ${unmatched_amount/1e6:>11,.1f}M")

    # Write CSV output
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "finance_campaign_id", "prop_num", "election_year", "election_month",
            "measure_db_id", "measure_id", "status", "match_via",
            "csv_row_count", "csv_total_amount", "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"\nWrote {len(results)} rows to {OUTPUT_CSV}")

    # Print the duplicates and any large unmatched campaigns for manual review.
    print("\n=== Duplicates (need Step 3 attention) ===")
    for r in results:
        if r["status"] == "duplicate":
            print(f"  {r['finance_campaign_id']}: ${r['csv_total_amount']/1e6:.2f}M  notes: {r['notes']}")

    print("\n=== Largest 'missing' campaigns (no measures-DB match) ===")
    missing = [r for r in results if r["status"] == "missing"]
    missing.sort(key=lambda r: -r["csv_total_amount"])
    for r in missing[:15]:
        print(f"  {r['finance_campaign_id']}: ${r['csv_total_amount']/1e6:>9.2f}M  ({r['csv_row_count']:,} rows)")


if __name__ == "__main__":
    main()
