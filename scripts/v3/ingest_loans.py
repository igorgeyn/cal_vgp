"""Phase 2: ingest LOAN_CD into finance_flow_v3.

Loads Schedule B Part 1 (loans received) from CAL-ACCESS LOAN_CD.TSV,
joined to CVR_CAMPAIGN_DISCLOSURE_CD for cover-sheet attribution, into
the v3 fact table.

Filters applied (Codex round-2 + round-3 rules):
- FORM_TYPE = 'B1' (Schedule B Part 1 only). B2 (guarantors),
  B3 (paid back), H/H1/H2/H3 (loans MADE by filer) are quarantined.
- Latest AMEND_ID per FILING_ID
- MEMO_CODE rows excluded (quarantined as 'memo_row')
- Amount = LOAN_AMT1 (amount received this reporting period). LOAN_AMT2
  is cumulative (would double-count across periods); LOAN_AMT3..8 are
  balance / repayment / interest semantics not relevant to "received".
- Amount <= 0 quarantined as 'non_positive_amount'
- Cover-sheet attribution: FILING_ID -> CVR -> (prop_num, election_year)
  -> v2 finance_campaign for (finance_campaign_id, measure_db_id).
  If lookup fails, row is quarantined with appropriate reason.

Usage:
    python -m scripts.v3.ingest_loans
    python -m scripts.v3.ingest_loans --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Allow running as a script (python scripts/v3/ingest_loans.py) by
# pushing the parent dir onto sys.path
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib
else:
    from . import lib


def load_cover_attributions(v2_db: Path, dump_dir: Path,
                            verbose: bool = True) -> dict:
    """Build FILING_ID -> CoverAttribution mapping.

    Reads CVR_CAMPAIGN_DISCLOSURE_CD, filters to ballot-measure filings
    (BAL_NAME or BAL_NUM populated), keeps latest AMEND_ID per
    FILING_ID, resolves (prop_num, election_year) via v2's
    finance_campaign crosswalk.
    """
    # Load v2 crosswalk into memory
    crosswalk: dict[tuple[str, int], tuple[str, int]] = {}
    with sqlite3.connect(str(v2_db)) as v2:
        for r in v2.execute(
            "SELECT prop_num, election_year, finance_campaign_id, measure_db_id "
            "FROM finance_campaign WHERE status = 'matched'"
        ):
            prop_num, year, cid, mdb = r
            if year and mdb is not None:
                crosswalk[(prop_num, int(year))] = (cid, int(mdb))
    if verbose:
        print(f"v2 crosswalk: {len(crosswalk):,} (prop_num, year) entries")

    cvr_path = dump_dir / "CVR_CAMPAIGN_DISCLOSURE_CD.TSV"
    if not cvr_path.exists():
        raise SystemExit(f"Missing source: {cvr_path}")

    # Pass 1: collect raw rows that look like ballot-measure filings,
    # keep the latest AMEND_ID per FILING_ID
    by_filing: dict[str, dict] = {}
    bm_count = 0
    with cvr_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {name: i for i, name in enumerate(header)}

        def col(row, name):
            i = cols.get(name)
            return row[i] if i is not None and i < len(row) else ""

        for row in reader:
            bal_name = col(row, "BAL_NAME")
            bal_num = col(row, "BAL_NUM")
            if lib.is_null(bal_name) and lib.is_null(bal_num):
                continue
            bm_count += 1
            fid = col(row, "FILING_ID")
            if not fid:
                continue
            try:
                amend = int(col(row, "AMEND_ID") or 0)
            except ValueError:
                amend = 0
            prior = by_filing.get(fid)
            if prior is None or amend > prior["amend_id"]:
                by_filing[fid] = {
                    "amend_id": amend,
                    "cover_form_type": col(row, "FORM_TYPE"),
                    "cover_filer_id": col(row, "FILER_ID"),
                    "cover_filer_name": col(row, "FILER_NAML"),
                    "cover_committee_id": col(row, "CMTTE_ID"),
                    "cover_bal_num": bal_num,
                    "cover_bal_name": bal_name,
                    "cover_bal_juris": col(row, "BAL_JURIS"),
                    "cover_sup_opp_cd": col(row, "SUP_OPP_CD"),
                    "cover_elect_date": col(row, "ELECT_DATE"),
                    "cover_from_date": col(row, "FROM_DATE"),
                    "cover_thru_date": col(row, "THRU_DATE"),
                }

    if verbose:
        print(f"CVR ballot-measure rows scanned: {bm_count:,}")
        print(f"Unique ballot-measure FILING_IDs: {len(by_filing):,}")

    # Pass 2: resolve attribution via crosswalk
    attribs: dict[str, lib.CoverAttribution] = {}
    stats = Counter()
    for fid, info in by_filing.items():
        bal_num = info["cover_bal_num"]
        bal_name = info["cover_bal_name"]
        elect = lib.parse_calaccess_date(info["cover_elect_date"])
        election_year = elect.year if elect else None
        prop_num = lib.extract_prop_num(bal_name, bal_num)

        finance_campaign_id = None
        measure_db_id = None
        method = "failed"
        if prop_num and election_year:
            hit = crosswalk.get((prop_num, election_year))
            if hit:
                finance_campaign_id, measure_db_id = hit
                method = "crosswalk"
            else:
                stats["crosswalk_miss"] += 1
        else:
            stats["bad_prop_or_year"] += 1

        # Stance from cover-sheet SUP_OPP_CD
        cover_stance_raw = (info["cover_sup_opp_cd"] or "").strip().upper()
        stance: str | None
        if cover_stance_raw == "S":
            stance = "support"
        elif cover_stance_raw == "O":
            stance = "oppose"
        else:
            stance = None
            # Try stance recovery from filer / committee name
            for committee_field in ("cover_filer_name",):
                name = info.get(committee_field) or ""
                if name and finance_campaign_id:
                    recovered, _label = lib.recover_stance_from_committee(
                        name, campaign_id=finance_campaign_id
                    )
                    if recovered:
                        stance = recovered
                        break

        attribs[fid] = lib.CoverAttribution(
            filing_id=fid,
            cover_form_type=info["cover_form_type"],
            cover_filer_id=info["cover_filer_id"],
            cover_filer_name=info["cover_filer_name"],
            cover_committee_id=info["cover_committee_id"],
            cover_bal_num=info["cover_bal_num"],
            cover_bal_name=info["cover_bal_name"],
            cover_bal_juris=info["cover_bal_juris"],
            cover_sup_opp_cd=info["cover_sup_opp_cd"],
            cover_elect_date=info["cover_elect_date"],
            cover_from_date=info["cover_from_date"],
            cover_thru_date=info["cover_thru_date"],
            election_year=election_year,
            prop_num=prop_num,
            finance_campaign_id=finance_campaign_id,
            measure_db_id=measure_db_id,
            stance=stance,
            attribution_method=method,
        )

    if verbose:
        print(f"Cover attributions resolved: "
              f"{sum(1 for a in attribs.values() if a.finance_campaign_id):,}")
        print(f"  crosswalk miss: {stats['crosswalk_miss']:,}")
        print(f"  bad prop/year: {stats['bad_prop_or_year']:,}")
    return attribs


def ingest_loans(dump_dir: Path, v2_db: Path, v3_db: Path,
                 dry_run: bool = False, verbose: bool = True) -> dict:
    """Read LOAN_CD, filter, attribute, insert into finance_flow_v3."""
    attribs = load_cover_attributions(v2_db, dump_dir, verbose=verbose)

    loan_path = dump_dir / "LOAN_CD.TSV"
    if not loan_path.exists():
        raise SystemExit(f"Missing source: {loan_path}")

    # Pass 1: identify latest AMEND_ID per (FILING_ID, LINE_ITEM) so we
    # can supersede prior amendments deterministically. CalAccess Loan
    # schedules amend the whole schedule, so the FILING_ID+LINE_ITEM
    # together identify a single source row across amendments.
    if verbose:
        print()
        print(f"Scanning LOAN_CD ({loan_path.stat().st_size / 1e6:.1f}MB)...")

    latest_amend: dict[tuple[str, str], int] = {}
    with loan_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {name: i for i, name in enumerate(header)}

        def col(row, name):
            i = cols.get(name)
            return row[i] if i is not None and i < len(row) else ""

        for row in reader:
            fid = col(row, "FILING_ID")
            line = col(row, "LINE_ITEM")
            if not fid:
                continue
            try:
                amend = int(col(row, "AMEND_ID") or 0)
            except ValueError:
                amend = 0
            key = (fid, line)
            if amend > latest_amend.get(key, -1):
                latest_amend[key] = amend

    if verbose:
        print(f"Unique (FILING_ID, LINE_ITEM) keys in LOAN_CD: "
              f"{len(latest_amend):,}")

    # Pass 2: build finance_flow_v3 rows
    rows_for_insert: list[dict] = []
    stats = Counter()

    with loan_path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {name: i for i, name in enumerate(header)}

        def col(row, name):
            i = cols.get(name)
            return row[i] if i is not None and i < len(row) else ""

        for row in reader:
            stats["source_rows"] += 1
            fid = col(row, "FILING_ID")
            line = col(row, "LINE_ITEM")
            try:
                amend = int(col(row, "AMEND_ID") or 0)
            except ValueError:
                amend = 0
            if not fid:
                stats["bad_filing_id"] += 1
                continue
            if amend != latest_amend.get((fid, line), -1):
                stats["superseded_amendment"] += 1
                continue

            form_type = (col(row, "FORM_TYPE") or "").strip()
            memo_code = col(row, "MEMO_CODE")
            tran_id = col(row, "TRAN_ID")
            bakref = col(row, "BAKREF_TID")
            memo_refno = col(row, "MEMO_REFNO")
            xref = col(row, "XREF_SCHNM")
            committee_id = col(row, "CMTE_ID")
            lender_last = col(row, "LNDR_NAML")
            lender_first = col(row, "LNDR_NAMF")
            lender_full = (
                f"{lender_last}, {lender_first}".strip(", ")
                if lender_first and not lib.is_null(lender_first)
                else (lender_last or "")
            ).strip()
            entity_cd = col(row, "ENTITY_CD")
            date1_str = col(row, "LOAN_DATE1")
            txn_date = lib.parse_calaccess_date(date1_str)
            try:
                amount = float(col(row, "LOAN_AMT1") or 0)
            except (ValueError, TypeError):
                amount = 0.0

            base = {c: None for c in lib.FLOW_COLUMNS}
            base.update({
                "source_table": "LOAN_CD",
                "source_form_type": form_type,
                "filing_id": fid,
                "amend_id": amend,
                "source_line_item": line,
                "source_tran_id": tran_id,
                "source_bakref_tid": bakref if not lib.is_null(bakref) else None,
                "source_memo_refno": memo_refno if not lib.is_null(memo_refno) else None,
                "source_xref_schnm": xref if not lib.is_null(xref) else None,
                "amount_field_used": "LOAN_AMT1",
                "committee_id": committee_id if not lib.is_null(committee_id) else None,
                "donor_name_raw": lender_full or None,
                "donor_name_canon": lib.canonicalize_donor(lender_full) if lender_full else None,
                "donor_type": "individual" if (entity_cd or "").strip().upper() == "IND" else "other",
                "memo_code": memo_code if not lib.is_null(memo_code) else None,
                "source_fingerprint":
                    f"LOAN_CD|{form_type}|{fid}|{amend}|{line}|{tran_id}",
            })

            # Cover-sheet lineage
            attr = attribs.get(fid)
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

            # Quarantine gates (applied in order; first failure wins)
            quarantine_reason = None
            if form_type != "B1":
                quarantine_reason = "unsupported_form_type"
            elif not lib.is_null(memo_code):
                quarantine_reason = "memo_row"
            elif attr is None:
                quarantine_reason = "no_cover_sheet"
            elif attr.finance_campaign_id is None:
                quarantine_reason = "no_campaign_match"
            elif attr.stance is None:
                quarantine_reason = "unknown_stance"
            elif txn_date is None:
                quarantine_reason = "unparseable_date"
            elif amount <= 0:
                quarantine_reason = "non_positive_amount"

            if quarantine_reason:
                base["quarantine_reason"] = quarantine_reason
                stats[f"quarantine_{quarantine_reason}"] += 1
            else:
                # Accepted: populate attribution fields + dedupe_key
                base["finance_campaign_id"] = attr.finance_campaign_id
                base["measure_db_id"] = attr.measure_db_id
                base["stance"] = attr.stance
                base["receipt_type"] = "loan"
                base["amount"] = amount
                base["txn_date"] = txn_date.isoformat()
                base["week_start"] = lib.week_start_iso(txn_date)
                base["attribution_source"] = "funding_source"  # lender named directly
                base["dedupe_key"] = (
                    f"loan|{attr.finance_campaign_id}|{attr.stance}|"
                    f"{base['donor_name_canon']}||"
                    f"{base['txn_date']}|{amount:.2f}|"
                    f"{committee_id or ''}"
                )
                stats["accepted"] += 1

            rows_for_insert.append(base)

    if verbose:
        print()
        print(f"=== LOAN_CD scan stats ===")
        for k, v in stats.most_common():
            print(f"  {k:35} {v:>10,}")

    if dry_run:
        if verbose:
            print()
            print("--dry-run: not writing to v3.db")
        return {"stats": dict(stats), "rows_to_insert": len(rows_for_insert)}

    # Write to v3.db
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
            # Clear existing LOAN_CD rows so re-running ingest is idempotent
            cur.execute("DELETE FROM finance_flow_v3 WHERE source_table=?",
                        ("LOAN_CD",))
            deleted = cur.rowcount
            cur.executemany(
                insert_sql,
                [tuple(r[c] for c in lib.FLOW_COLUMNS) for r in rows_for_insert],
            )
            inserted = len(rows_for_insert)
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise

        if verbose:
            print()
            print(f"Wrote to {v3_db.name}: deleted {deleted} prior LOAN_CD rows, "
                  f"inserted {inserted}")
    finally:
        con.close()

    return {"stats": dict(stats),
            "rows_inserted": len(rows_for_insert)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", default=str(lib.DUMP_DIR))
    parser.add_argument("--v2-db", default=str(lib.V2_DB))
    parser.add_argument("--v3-db", default=str(lib.V3_DB))
    parser.add_argument("--dry-run", action="store_true",
                        help="Scan + classify but don't write to v3.db")
    args = parser.parse_args()

    ingest_loans(Path(args.dump_dir), Path(args.v2_db), Path(args.v3_db),
                 dry_run=args.dry_run, verbose=True)


if __name__ == "__main__":
    main()
