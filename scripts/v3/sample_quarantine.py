"""Manual-review samplers for Schedule C quarantine buckets.

Codex round-8 spec for the filer_name_no_prop bucket:
  Include: normalized_filer_name, raw top filer name, filer_id, row
  count, dollars, min/max transaction date, cover date range, form
  types, top committee/payee/contributor names if available, current
  quarantine reason, and blank columns for reviewer classification /
  override target.

  Do top 100 by dollars plus a stratified random sample.

Also produces a top-25 sample of ambiguous_year for validation.

Outputs two CSV files in data/CalAccess/, ready for spreadsheet review.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
    from v3.attribution import build_filing_attribution_index
else:
    from . import lib
    from .attribution import build_filing_attribution_index


def collect(dump_dir: Path, v2_db: Path, *, verbose: bool = True) -> dict:
    """Stream RCPT_CD Schedule C, group by (FILER_NAML, quarantine_reason).

    For each filer x reason bucket, aggregate:
        row_count, dollars, min/max txn_date, cover form_types,
        top 5 contributor names, top 5 payee names.

    Returns: { (normalized_filer, raw_filer, filer_id, reason): info_dict }
    """
    idx = build_filing_attribution_index(dump_dir, v2_db, verbose=verbose)

    rcpt_path = dump_dir / "RCPT_CD.TSV"
    if verbose:
        print(f"\nScanning RCPT_CD ({rcpt_path.stat().st_size / 1e9:.1f}GB)...")

    # Pass 1: latest amend per FILING_ID
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
                amend = int(row[amend_idx] or 0) if (
                    amend_idx is not None and amend_idx < len(row)
                ) else 0
            except ValueError:
                amend = 0
            if amend > latest_amend.get(fid, -1):
                latest_amend[fid] = amend

    # Pass 2: collect per-(filer, reason) aggregates for filer_name_no_prop
    # and ambiguous_year buckets. Other quarantine reasons skipped to keep
    # output focused.
    target_reasons = {"filer_name_no_prop", "ambiguous_year"}
    buckets: dict = defaultdict(lambda: {
        "row_count": 0,
        "dollars": 0.0,
        "min_txn_date": None,
        "max_txn_date": None,
        "form_types": Counter(),
        "contributors": Counter(),
        "cover_form_types": Counter(),
        "cover_from_date": "",
        "cover_thru_date": "",
        "cover_elect_date": "",
        "filing_ids_sample": [],
    })

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
            txn_date = lib.parse_calaccess_date(c(row, "RCPT_DATE"))
            if txn_date is None:
                continue

            att = idx.get(fid)
            if att is None:
                continue
            reason = att.quarantine_reason
            if reason not in target_reasons:
                continue

            filer_name = att.cover_filer_name or "(no filer name)"
            filer_id = att.cover_filer_id or ""
            normalized = " ".join(filer_name.split()).lower()
            key = (normalized, filer_name, filer_id, reason)

            b = buckets[key]
            b["row_count"] += 1
            b["dollars"] += amount
            iso = txn_date.isoformat()
            if b["min_txn_date"] is None or iso < b["min_txn_date"]:
                b["min_txn_date"] = iso
            if b["max_txn_date"] is None or iso > b["max_txn_date"]:
                b["max_txn_date"] = iso
            b["form_types"][(c(row, "FORM_TYPE") or "").strip()] += 1
            ctrib_last = c(row, "CTRIB_NAML")
            ctrib_first = c(row, "CTRIB_NAMF")
            ctrib_name = (
                f"{ctrib_last}, {ctrib_first}".strip(", ")
                if ctrib_first and not lib.is_null(ctrib_first)
                else (ctrib_last or "")
            ).strip()
            if ctrib_name:
                b["contributors"][ctrib_name] += amount
            b["cover_form_types"][att.cover_form_type or ""] += 1
            # Capture cover dates from one representative attribution
            if not b["cover_from_date"]:
                b["cover_from_date"] = att.cover_from_date or ""
                b["cover_thru_date"] = att.cover_thru_date or ""
                b["cover_elect_date"] = att.cover_elect_date or ""
            if len(b["filing_ids_sample"]) < 5:
                b["filing_ids_sample"].append(fid)

    return buckets


def write_csv(rows: list[dict], path: Path) -> None:
    fields = [
        "normalized_filer_name", "raw_filer_name", "filer_id",
        "quarantine_reason", "row_count", "total_dollars",
        "min_txn_date", "max_txn_date",
        "cover_elect_date", "cover_from_date", "cover_thru_date",
        "cover_form_types", "rcpt_form_types",
        "top_contributors_by_dollars",
        "sample_filing_ids",
        # Blank reviewer columns
        "reviewer_classification",
        "reviewer_target_campaign_id",
        "reviewer_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def render_row(key, b) -> dict:
    normalized, raw, filer_id, reason = key
    return {
        "normalized_filer_name": normalized,
        "raw_filer_name": raw,
        "filer_id": filer_id,
        "quarantine_reason": reason,
        "row_count": b["row_count"],
        "total_dollars": round(b["dollars"], 2),
        "min_txn_date": b["min_txn_date"],
        "max_txn_date": b["max_txn_date"],
        "cover_elect_date": b["cover_elect_date"],
        "cover_from_date": b["cover_from_date"],
        "cover_thru_date": b["cover_thru_date"],
        "cover_form_types": ", ".join(
            f"{k}={v}" for k, v in
            sorted(b["cover_form_types"].items(),
                   key=lambda kv: kv[1], reverse=True)
            if k
        ),
        "rcpt_form_types": ", ".join(
            f"{k}={v}" for k, v in b["form_types"].items()
        ),
        "top_contributors_by_dollars": "; ".join(
            f"{n} (${a:,.0f})" for n, a in
            b["contributors"].most_common(5)
        ),
        "sample_filing_ids": ", ".join(b["filing_ids_sample"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", default=str(lib.DUMP_DIR))
    parser.add_argument("--v2-db", default=str(lib.V2_DB))
    parser.add_argument("--out-dir",
                        default=str(Path("data/CalAccess")))
    parser.add_argument("--random-sample-size", type=int, default=50,
                        help="Stratified random sample size for "
                             "filer_name_no_prop (in addition to top 100)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    out_dir = Path(args.out_dir)

    buckets = collect(Path(args.dump_dir), Path(args.v2_db), verbose=True)

    # Split by reason
    no_prop = [(k, v) for k, v in buckets.items()
               if k[3] == "filer_name_no_prop"]
    amb_year = [(k, v) for k, v in buckets.items()
                if k[3] == "ambiguous_year"]

    no_prop_sorted = sorted(no_prop, key=lambda kv: kv[1]["dollars"],
                            reverse=True)
    amb_year_sorted = sorted(amb_year, key=lambda kv: kv[1]["dollars"],
                             reverse=True)

    # filer_name_no_prop: top 100 + stratified random sample
    top_100 = no_prop_sorted[:100]
    remaining = no_prop_sorted[100:]
    # Stratify by dollar tier
    tiers: dict[str, list] = {"$10k-100k": [], "$1k-10k": [], "<$1k": []}
    for k, v in remaining:
        d = v["dollars"]
        if d >= 10000:
            tiers["$10k-100k"].append((k, v))
        elif d >= 1000:
            tiers["$1k-10k"].append((k, v))
        else:
            tiers["<$1k"].append((k, v))
    random_sample = []
    per_tier = max(1, args.random_sample_size // 3)
    for tier_rows in tiers.values():
        if tier_rows:
            random_sample.extend(
                random.sample(tier_rows, min(per_tier, len(tier_rows)))
            )

    no_prop_review = [render_row(k, v) for k, v in top_100]
    for k, v in random_sample:
        row = render_row(k, v)
        row["reviewer_classification"] = "[random sample]"
        no_prop_review.append(row)

    write_csv(no_prop_review, out_dir / "sample_filer_name_no_prop.csv")
    print(f"\nfiler_name_no_prop sample: {len(no_prop_review)} rows "
          f"({len(top_100)} top + {len(random_sample)} random) -> "
          f"{out_dir / 'sample_filer_name_no_prop.csv'}")

    # ambiguous_year: top 25
    amb_review = [render_row(k, v) for k, v in amb_year_sorted[:25]]
    write_csv(amb_review, out_dir / "sample_ambiguous_year.csv")
    print(f"ambiguous_year sample: {len(amb_review)} rows -> "
          f"{out_dir / 'sample_ambiguous_year.csv'}")


if __name__ == "__main__":
    main()
