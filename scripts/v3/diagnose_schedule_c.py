"""Diagnose Schedule C (in-kind) attribution loss before Phase 3.

Codex round-5 raised the alarm: cover-sheet-only attribution may drop
material Schedule C dollar volume. Their quick scan estimated:

  accepted_by_cover:   $637.2M
  no_cover:            $718.4M
  no_campaign_match:   $386.5M
  unknown_stance:      $2.0M

Before designing Phase 3 (in-kind ingest), classify what's actually in
those buckets:
- How much is non-ballot-measure filer activity (correctly out of
  scope)
- How much is ballot-measure activity for non-statewide / recall /
  out-of-v2-crosswalk props (broaden crosswalk?)
- How much is genuine v2-scope statewide activity getting missed
  (extract_prop_num bug, ELECT_DATE parser, etc.)

This script applies the same filter chain as the planned in-kind
ingest (latest amend per FILING_ID, FORM_TYPE='C', non-memo, positive
amount, parseable RCPT_DATE) but is read-only — no DB writes.

Output:
- Bucket sums by attribution status
- Top 25 filers in each non-accepted bucket (so we can see whether
  it's "famous statewide committee we missed" vs "Joe's Plumbing for
  Mayor")
- For no_campaign_match: top 10 missing (prop_num, year) pairs

Usage:
    python scripts/v3/diagnose_schedule_c.py
    python scripts/v3/diagnose_schedule_c.py --report data/CalAccess/schedule_c_diagnostic.md
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
    from v3.ingest_loans import load_cover_attributions
else:
    from . import lib
    from .ingest_loans import load_cover_attributions


def diagnose(dump_dir: Path, v2_db: Path, verbose: bool = True) -> dict:
    attribs = load_cover_attributions(v2_db, dump_dir, verbose=verbose)
    if verbose:
        print()

    rcpt_path = dump_dir / "RCPT_CD.TSV"
    if not rcpt_path.exists():
        raise SystemExit(f"Missing source: {rcpt_path}")

    # Pass 1: latest amend per FILING_ID (across all RCPT_CD rows;
    # ballot-measure filings are a subset)
    if verbose:
        print(f"Scanning RCPT_CD ({rcpt_path.stat().st_size / 1e9:.2f}GB) "
              f"for latest-amend dedup...")
    latest_amend: dict[str, int] = {}
    rows_scanned = 0
    with rcpt_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}
        fid_idx = cols.get("FILING_ID")
        amend_idx = cols.get("AMEND_ID")
        for row in reader:
            rows_scanned += 1
            if rows_scanned % 1_000_000 == 0 and verbose:
                print(f"  ... {rows_scanned:,} rows")
            if fid_idx is None or fid_idx >= len(row):
                continue
            fid = row[fid_idx]
            if not fid:
                continue
            try:
                amend = int(row[amend_idx] or 0) if (amend_idx is not None
                    and amend_idx < len(row)) else 0
            except ValueError:
                amend = 0
            if amend > latest_amend.get(fid, -1):
                latest_amend[fid] = amend
    if verbose:
        print(f"  Total RCPT_CD rows: {rows_scanned:,}")
        print(f"  Unique FILING_IDs:  {len(latest_amend):,}")
        print()
        print(f"Pass 2: classify Schedule C rows by attribution status...")

    # Pass 2: filter to FORM_TYPE='C' latest-amend non-memo
    # positive-amount parseable-date rows; classify by attribution
    buckets: Counter[str] = Counter()
    dollars: Counter[str] = Counter()
    rows_per_bucket: dict[str, int] = Counter()
    top_filers_by_bucket: dict[str, Counter[str]] = defaultdict(Counter)
    missing_props: Counter[tuple[str, int]] = Counter()

    with rcpt_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}

        def c(row, name):
            i = cols.get(name)
            return row[i] if i is not None and i < len(row) else ""

        for row in reader:
            fid = c(row, "FILING_ID")
            if not fid:
                continue
            try:
                amend = int(c(row, "AMEND_ID") or 0)
            except ValueError:
                amend = 0
            if amend != latest_amend.get(fid, -1):
                continue
            form_type = (c(row, "FORM_TYPE") or "").strip()
            if form_type != "C":
                continue
            memo = c(row, "MEMO_CODE")
            if not lib.is_null(memo):
                continue
            amt_raw = c(row, "AMOUNT")
            if lib.is_null(amt_raw):
                continue
            try:
                amount = float(amt_raw)
            except (ValueError, TypeError):
                continue
            if amount <= 0:
                continue
            txn_date = lib.parse_calaccess_date(c(row, "RCPT_DATE"))
            if txn_date is None:
                continue

            attr = attribs.get(fid)
            ctrib_last = c(row, "CTRIB_NAML")
            ctrib_first = c(row, "CTRIB_NAMF")
            donor_label = (
                f"{ctrib_last}, {ctrib_first}".strip(", ")
                if ctrib_first and not lib.is_null(ctrib_first)
                else (ctrib_last or "")
            ).strip()

            if attr is None:
                bucket = "no_cover_sheet"
                filer_label = "(no cover sheet)"
            elif attr.finance_campaign_id is None:
                if attr.prop_num is None or attr.election_year is None:
                    bucket = "bad_prop_or_year"
                else:
                    bucket = "no_campaign_match"
                    missing_props[(attr.prop_num,
                                   attr.election_year)] += amount
                filer_label = attr.cover_filer_name or "(no filer)"
            elif attr.stance is None:
                bucket = "unknown_stance"
                filer_label = attr.cover_filer_name or "(no filer)"
            else:
                bucket = "accepted"
                filer_label = attr.cover_filer_name or "(no filer)"

            buckets[bucket] += 1
            dollars[bucket] += amount
            rows_per_bucket[bucket] += 1
            top_filers_by_bucket[bucket][filer_label] += amount

    return {
        "buckets": dict(buckets),
        "dollars": dict(dollars),
        "rows_per_bucket": dict(rows_per_bucket),
        "top_filers_by_bucket": {
            k: v.most_common(25) for k, v in top_filers_by_bucket.items()
        },
        "missing_props_by_dollars": missing_props.most_common(20),
    }


def render_report(stats: dict, report_path: Path | None,
                  verbose: bool = True) -> None:
    lines = ["# Schedule C (in-kind) attribution diagnostic", ""]
    lines.append(f"Run 2026-05-13 from current v3 dump. Filters applied:")
    lines.append("- FORM_TYPE = 'C' (Schedule C non-monetary)")
    lines.append("- Latest AMEND_ID per FILING_ID")
    lines.append("- MEMO_CODE blank")
    lines.append("- AMOUNT parseable + > 0")
    lines.append("- RCPT_DATE parseable")
    lines.append("")
    lines.append("## Bucket totals")
    lines.append("")
    lines.append("| Bucket | Rows | Dollar amount |")
    lines.append("|---|---|---|")
    for bucket in ["accepted", "no_cover_sheet", "no_campaign_match",
                   "bad_prop_or_year", "unknown_stance"]:
        rows = stats["buckets"].get(bucket, 0)
        amt = stats["dollars"].get(bucket, 0.0)
        lines.append(f"| `{bucket}` | {rows:,} | ${amt:,.2f} |")
    lines.append("")

    for bucket in ["accepted", "no_cover_sheet", "no_campaign_match",
                   "bad_prop_or_year", "unknown_stance"]:
        rows = stats["top_filers_by_bucket"].get(bucket, [])
        if not rows:
            continue
        lines.append(f"## Top 25 filers in `{bucket}`")
        lines.append("")
        lines.append("| Filer | Dollar amount |")
        lines.append("|---|---|")
        for filer, amt in rows:
            f_display = (filer or "(empty)")[:80].replace("|", "\\|")
            lines.append(f"| {f_display} | ${amt:,.2f} |")
        lines.append("")

    lines.append("## Top 20 unmatched (prop_num, election_year) by dollar volume")
    lines.append("(Rows where prop_num + year extract but no v2 crosswalk entry)")
    lines.append("")
    lines.append("| prop_num | year | dollars |")
    lines.append("|---|---|---|")
    for (prop, year), amt in stats["missing_props_by_dollars"]:
        lines.append(f"| {prop} | {year} | ${amt:,.2f} |")
    lines.append("")

    text = "\n".join(lines)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
        if verbose:
            print(f"Report written to {report_path}")
    if verbose:
        print()
        print("=" * 60)
        for bucket in ["accepted", "no_cover_sheet", "no_campaign_match",
                       "bad_prop_or_year", "unknown_stance"]:
            r = stats["buckets"].get(bucket, 0)
            d = stats["dollars"].get(bucket, 0.0)
            print(f"  {bucket:20} {r:>8,} rows  ${d:>16,.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", default=str(lib.DUMP_DIR))
    parser.add_argument("--v2-db", default=str(lib.V2_DB))
    parser.add_argument(
        "--report",
        default=str(Path("data/CalAccess/schedule_c_diagnostic.md"))
    )
    args = parser.parse_args()

    stats = diagnose(Path(args.dump_dir), Path(args.v2_db), verbose=True)
    render_report(stats, Path(args.report) if args.report else None,
                  verbose=True)


if __name__ == "__main__":
    main()
