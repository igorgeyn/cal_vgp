"""Investigate the no_cover_sheet bucket from diagnose_schedule_c.

Codex round-6 pushback: $434.7M of Schedule C lands in no_cover_sheet
not because the cover sheet is missing entirely, but because the
filer's cover sheet on THAT filing has blank BAL_NAME / BAL_NUM. The
filing may still be from a ballot-measure committee that filed other
cover sheets with prop attribution elsewhere.

Concrete question: for each FILING_ID in the no_cover_sheet bucket,
look up its cover sheet (any cover sheet — not filtered to ballot-
measure), then look at the FILER_NAML on that cover. If the filer
name itself identifies a prop ("YES ON 14: CALIFORNIANS FOR..."),
this filing's Schedule C is recoverable via the same filer-name
extraction we're about to build for bad_prop_or_year.

If, on the other hand, the no_cover_sheet filings are from
candidates / parties / general PACs with non-prop names, the bucket
is correctly out of scope and we don't need CMTE_ID-based recovery.

Output: top filer names within no_cover_sheet by dollar volume.
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
else:
    from . import lib


def investigate(dump_dir: Path, verbose: bool = True) -> dict:
    """Scan no_cover_sheet Schedule C rows, look up their cover sheets
    in CVR (unfiltered), report top filers by dollar volume."""

    # Pass 1: from CVR, build FILING_ID -> cover-sheet metadata for
    # ALL filings (not just ballot-measure ones).
    cvr_path = dump_dir / "CVR_CAMPAIGN_DISCLOSURE_CD.TSV"
    if verbose:
        print(f"Pass 1: load all CVR cover sheets ({cvr_path.stat().st_size / 1e6:.0f}MB)...")
    all_filings: dict[str, dict] = {}
    has_ballot_metadata: set[str] = set()
    with cvr_path.open(encoding="latin-1", newline="") as f:
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
            prior = all_filings.get(fid)
            if prior is None or amend > prior["amend_id"]:
                all_filings[fid] = {
                    "amend_id": amend,
                    "form_type": c(row, "FORM_TYPE"),
                    "filer_id": c(row, "FILER_ID"),
                    "filer_name": c(row, "FILER_NAML"),
                    "committee_id": c(row, "CMTTE_ID"),
                }
            bal_name = c(row, "BAL_NAME")
            bal_num = c(row, "BAL_NUM")
            if not lib.is_null(bal_name) or not lib.is_null(bal_num):
                has_ballot_metadata.add(fid)

    if verbose:
        print(f"  Unique FILING_IDs in CVR: {len(all_filings):,}")
        print(f"  With ballot metadata:     {len(has_ballot_metadata):,}")
        print()

    # Pass 2: RCPT_CD Schedule C amend dedup
    rcpt_path = dump_dir / "RCPT_CD.TSV"
    if verbose:
        print(f"Pass 2: latest-amend dedup over RCPT_CD ({rcpt_path.stat().st_size / 1e9:.1f}GB)...")
    latest_amend: dict[str, int] = {}
    with rcpt_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}
        fid_idx = cols.get("FILING_ID")
        amend_idx = cols.get("AMEND_ID")
        for row in reader:
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

    # Pass 3: classify Schedule C rows landing in no_cover_sheet bucket
    if verbose:
        print(f"Pass 3: bucket no_cover_sheet rows by filer name...")
    by_filer: Counter[str] = Counter()
    by_filer_form: dict[str, Counter[str]] = defaultdict(Counter)
    no_cvr_at_all = 0.0
    no_cvr_rows = 0
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
            if (c(row, "FORM_TYPE") or "").strip() != "C":
                continue
            if not lib.is_null(c(row, "MEMO_CODE")):
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
            if lib.parse_calaccess_date(c(row, "RCPT_DATE")) is None:
                continue
            # Now: only count rows whose FILING_ID is NOT in the
            # ballot-measure cover-sheet set (i.e. the no_cover_sheet
            # bucket in the original diagnostic)
            if fid in has_ballot_metadata:
                continue
            cover = all_filings.get(fid)
            if cover is None:
                no_cvr_at_all += amount
                no_cvr_rows += 1
                continue
            label = cover.get("filer_name") or "(no filer name)"
            by_filer[label] += amount
            by_filer_form[label][cover.get("form_type", "")] += amount

    return {
        "no_cvr_at_all_dollars": no_cvr_at_all,
        "no_cvr_at_all_rows": no_cvr_rows,
        "top_filers": by_filer.most_common(50),
        "form_type_by_filer": {
            k: dict(by_filer_form[k]) for k, _ in by_filer.most_common(50)
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", default=str(lib.DUMP_DIR))
    parser.add_argument(
        "--report",
        default=str(Path("data/CalAccess/no_cover_sheet_diagnostic.md")),
    )
    args = parser.parse_args()

    stats = investigate(Path(args.dump_dir), verbose=True)

    lines = ["# no_cover_sheet bucket investigation", ""]
    lines.append("Schedule C dollar amounts grouped by FILER_NAML on the "
                 "filing's (non-ballot-measure) cover sheet.")
    lines.append("")
    lines.append(f"FILING_IDs with no CVR cover sheet at all: "
                 f"{stats['no_cvr_at_all_rows']:,} rows, "
                 f"${stats['no_cvr_at_all_dollars']:,.2f}")
    lines.append("")
    lines.append("## Top 50 filer names in no_cover_sheet by dollar volume")
    lines.append("")
    lines.append("| Filer name | Form type(s) | Dollars |")
    lines.append("|---|---|---|")
    for filer, amt in stats["top_filers"]:
        ft_map = stats["form_type_by_filer"].get(filer, {})
        ft_str = ", ".join(f"{k}=${v/1e6:.1f}M" for k, v in sorted(
            ft_map.items(), key=lambda kv: kv[1], reverse=True
        )[:3])
        f_disp = (filer or "(empty)")[:80].replace("|", "\\|")
        lines.append(f"| {f_disp} | {ft_str} | ${amt:,.2f} |")
    lines.append("")

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    print()
    print(f"Report written to {args.report}")
    print()
    print(f"=== Headline ===")
    print(f"No-CVR-at-all: {stats['no_cvr_at_all_rows']:,} rows / "
          f"${stats['no_cvr_at_all_dollars']:,.2f}")
    print(f"Top 5 filers in remaining no_cover_sheet bucket:")
    for filer, amt in stats["top_filers"][:5]:
        f_disp = (filer or "(empty)")[:60]
        print(f"  ${amt:>14,.2f}  {f_disp}")


if __name__ == "__main__":
    main()
