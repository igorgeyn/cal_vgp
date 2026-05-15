"""Phase 3: ingest RCPT_CD Schedule C (in-kind contributions) into
finance_flow_v3.

Mirrors ingest_loans.py but for non-monetary contributions, which
share RCPT_CD with monetary (FORM_TYPE='C' vs 'A'). Uses the unified
attribution index (scripts/v3/attribution.py) so the full resolver
chain runs:
    cover_sheet -> filer_name_explicit -> manual_override

Filters applied (Codex round-2 / 3 / 5 / 7 / 9):
- FORM_TYPE = 'C' (Schedule C non-monetary). FORM_TYPE 'I' and 'F401A'
  quarantined as unsupported_form_type (Codex round-3 design).
- Latest AMEND_ID per FILING_ID (Codex round-5: amendments are
  complete refiles, not incremental).
- MEMO_CODE rows excluded (memo_row).
- AMOUNT parseable and > 0 (non_positive_amount / unparseable_amount).
- RCPT_DATE parseable.
- Attribution via build_filing_attribution_index (full resolver
  chain). Failures get the resolver's quarantine_reason.

Usage:
    python -m scripts.v3.ingest_inkind
    python -m scripts.v3.ingest_inkind --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
    from v3.attribution import build_filing_attribution_index
else:
    from . import lib
    from .attribution import build_filing_attribution_index


def ingest_inkind(dump_dir: Path, v2_db: Path, v3_db: Path,
                  manual_overrides_path: Path | None = None,
                  dry_run: bool = False, verbose: bool = True) -> dict:
    """Ingest RCPT_CD Schedule C rows into finance_flow_v3.

    Returns stats dict with counts per quarantine reason / accepted.
    """
    # Phase 1: unified attribution index (cover_sheet + filer_name +
    # manual_override + canonicalization + multi-cand wind-down)
    idx = build_filing_attribution_index(
        dump_dir, v2_db,
        manual_overrides_path=manual_overrides_path,
        verbose=verbose,
    )

    rcpt_path = dump_dir / "RCPT_CD.TSV"
    if not rcpt_path.exists():
        raise SystemExit(f"Missing source: {rcpt_path}")

    if verbose:
        print()
        print(f"Pass 1: latest-amend dedup over RCPT_CD "
              f"({rcpt_path.stat().st_size / 1e9:.1f}GB)...")

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

    if verbose:
        print(f"  Total RCPT_CD rows: {rows_scanned:,}")
        print(f"  Unique FILING_IDs:  {len(latest_amend):,}")
        print()
        print(f"Pass 2: build Schedule C ingest rows...")

    rows_for_insert: list[dict] = []
    stats: Counter[str] = Counter()

    with rcpt_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}

        def c(row, name):
            i = cols.get(name)
            return row[i] if i is not None and i < len(row) else ""

        for row in reader:
            stats["source_rows"] += 1
            fid = c(row, "FILING_ID")
            if not fid:
                stats["bad_filing_id"] += 1
                continue
            try:
                amend = int(c(row, "AMEND_ID") or 0)
            except ValueError:
                amend = 0
            if amend != latest_amend.get(fid, -1):
                stats["superseded_amendment"] += 1
                continue

            form_type = (c(row, "FORM_TYPE") or "").strip()
            # Out-of-scope FORM_TYPEs (Codex round-3): don't carry into
            # the fact table. RCPT_CD 'A' (monetary), 'I' (intermediary),
            # 'F401A' (slate mailer contributions) are not in scope for
            # Phase 3 in-kind ingest.
            if form_type != "C":
                stats["skipped_non_scheduleC"] += 1
                continue

            # Parse all source fields up front
            memo_code = c(row, "MEMO_CODE")
            tran_id = c(row, "TRAN_ID")
            line = c(row, "LINE_ITEM")
            bakref = c(row, "BAKREF_TID")
            memo_refno = c(row, "MEMO_REFNO")
            xref = c(row, "XREF_SCHNM")
            committee_id = c(row, "CMTE_ID")
            ctrib_last = c(row, "CTRIB_NAML")
            ctrib_first = c(row, "CTRIB_NAMF")
            ctrib_full = (
                f"{ctrib_last}, {ctrib_first}".strip(", ")
                if ctrib_first and not lib.is_null(ctrib_first)
                else (ctrib_last or "")
            ).strip()
            entity_cd = c(row, "ENTITY_CD")
            date_str = c(row, "RCPT_DATE")
            txn_date = lib.parse_calaccess_date(date_str)
            amt_raw = c(row, "AMOUNT")
            if lib.is_null(amt_raw):
                amount: float | None = None
            else:
                try:
                    amount = float(amt_raw)
                except (ValueError, TypeError):
                    amount = None

            donor_canon = (
                lib.canonicalize_donor(ctrib_full) if ctrib_full else None
            )
            txn_date_iso = txn_date.isoformat() if txn_date else None
            week_start = lib.week_start_iso(txn_date) if txn_date else None

            source_fingerprint = (
                f"RCPT_CD|{form_type}|{fid}|{amend}|{line}|{tran_id}"
            )
            economic_fingerprint = (
                f"{(donor_canon or '')}|{txn_date_iso or ''}|"
                f"{(amount if amount is not None else ''):}|"
                f"{(committee_id or '')}|in_kind"
            )

            base = {c: None for c in lib.FLOW_COLUMNS}
            base.update({
                "amount": amount,
                "txn_date": txn_date_iso,
                "week_start": week_start,
                "receipt_type": "in_kind",   # cleared if quarantined
                "source_table": "RCPT_CD",
                "source_form_type": form_type,
                "filing_id": fid,
                "amend_id": amend,
                "source_line_item": line,
                "source_tran_id": tran_id,
                "source_bakref_tid": bakref if not lib.is_null(bakref) else None,
                "source_memo_refno": (
                    memo_refno if not lib.is_null(memo_refno) else None
                ),
                "source_xref_schnm": xref if not lib.is_null(xref) else None,
                "amount_field_used": "AMOUNT",
                "committee_id": (
                    committee_id if not lib.is_null(committee_id) else None
                ),
                "donor_name_raw": ctrib_full or None,
                "donor_name_canon": donor_canon,
                "donor_type": (
                    "individual"
                    if (entity_cd or "").strip().upper() == "IND"
                    else "other"
                ),
                "memo_code": memo_code if not lib.is_null(memo_code) else None,
                "source_fingerprint": source_fingerprint,
                "economic_fingerprint": economic_fingerprint,
            })

            # Cover-sheet lineage from unified attribution index
            attr = idx.get(fid)
            if attr:
                base.update({
                    "cover_form_type": attr.cover_form_type,
                    "cover_filer_id": attr.cover_filer_id,
                    "cover_filer_name": attr.cover_filer_name,
                    "cover_committee_id": attr.cover_committee_id,
                    "cover_bal_num": attr.cover_bal_num,
                    "cover_bal_name": attr.cover_bal_name,
                    "cover_bal_juris": attr.cover_bal_juris,
                    "cover_sup_opp_cd": attr.cover_sup_opp_cd,
                    "cover_elect_date": attr.cover_elect_date,
                    "cover_from_date": attr.cover_from_date,
                    "cover_thru_date": attr.cover_thru_date,
                    "attribution_method": attr.attribution_method,
                })

            # Gate sequence (first failure wins; same shape as
            # ingest_loans)
            quarantine_reason = None
            if not lib.is_null(memo_code):
                quarantine_reason = "memo_row"
            elif attr is None:
                quarantine_reason = "no_cover_sheet"
            elif attr.finance_campaign_id is None:
                # Resolver already populated quarantine_reason; reuse it
                # (no_campaign_match / bad_prop_or_year / ambiguous_year
                # / ambiguous_multi_prop / filer_name_no_prop /
                # single_candidate_stale_out_of_window)
                quarantine_reason = (
                    attr.quarantine_reason or "no_campaign_match"
                )
            elif attr.stance is None:
                quarantine_reason = "unknown_stance"
            elif txn_date is None:
                quarantine_reason = "unparseable_date"
            elif amount is None:
                quarantine_reason = "unparseable_amount"
            elif amount <= 0:
                quarantine_reason = "non_positive_amount"

            if quarantine_reason:
                base["quarantine_reason"] = quarantine_reason
                base["receipt_type"] = None
                stats[f"quarantine_{quarantine_reason}"] += 1
            else:
                base["finance_campaign_id"] = attr.finance_campaign_id
                base["source_crosswalk_campaign_id"] = (
                    attr.finance_campaign_id  # FilingAttribution's
                    # canonical cid already; ingest writes the canonical
                    # for now. Future enhancement: read the pre-
                    # canonical match from a richer FilingAttribution.
                )
                base["measure_db_id"] = attr.measure_db_id
                base["stance"] = attr.stance
                # Schedule C donor IS the funding source (in-kind
                # contributions are reported by the contributor's
                # identity, not via an intermediary committee).
                base["attribution_source"] = "funding_source"
                base["dedupe_key"] = (
                    f"in_kind|{attr.finance_campaign_id}|{attr.stance}|"
                    f"{donor_canon}||{txn_date_iso}|{amount:.2f}|"
                    f"{committee_id or ''}"
                )
                stats[f"accepted_via_{attr.attribution_method}"] += 1
                stats["accepted"] += 1

            rows_for_insert.append(base)

    if verbose:
        print()
        print(f"=== Schedule C scan stats ===")
        for k, v in stats.most_common():
            print(f"  {k:45} {v:>10,}")

    if dry_run:
        if verbose:
            print()
            print("--dry-run: not writing to v3.db")
        return {
            "stats": dict(stats),
            "rows_to_insert": len(rows_for_insert),
        }

    # Write to v3.db (DELETE-then-INSERT idempotent per source_table)
    placeholders = ",".join("?" for _ in lib.FLOW_COLUMNS)
    columns = ",".join(lib.FLOW_COLUMNS)
    insert_sql = (
        f"INSERT INTO finance_flow_v3 ({columns}) VALUES ({placeholders})"
    )

    con = sqlite3.connect(str(v3_db), isolation_level=None)
    try:
        cur = con.cursor()
        cur.execute("BEGIN")
        try:
            cur.execute(
                "DELETE FROM finance_flow_v3 "
                "WHERE source_table=? AND source_form_type='C'",
                ("RCPT_CD",),
            )
            deleted = cur.rowcount
            cur.executemany(
                insert_sql,
                [tuple(r[c] for c in lib.FLOW_COLUMNS)
                 for r in rows_for_insert],
            )
            inserted = len(rows_for_insert)
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise

        if verbose:
            print()
            print(f"Wrote to {v3_db.name}: deleted {deleted} prior "
                  f"Schedule C rows, inserted {inserted}")
    finally:
        con.close()

    return {"stats": dict(stats), "rows_inserted": len(rows_for_insert)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", default=str(lib.DUMP_DIR))
    parser.add_argument("--v2-db", default=str(lib.V2_DB))
    parser.add_argument("--v3-db", default=str(lib.V3_DB))
    parser.add_argument(
        "--manual-overrides",
        default=str(Path("data/CalAccess/manual_attribution_overrides.json")),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    overrides = (Path(args.manual_overrides)
                 if args.manual_overrides
                 and Path(args.manual_overrides).exists()
                 else None)
    ingest_inkind(
        Path(args.dump_dir), Path(args.v2_db), Path(args.v3_db),
        manual_overrides_path=overrides,
        dry_run=args.dry_run, verbose=True,
    )


if __name__ == "__main__":
    main()
