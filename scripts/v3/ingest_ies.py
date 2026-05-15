"""Phase 4: ingest Independent Expenditures into finance_flow_v3.

Three sources per Codex round-2/3/10 design:

  EXPN_CD FORM_TYPE='F461P5'  - major donor IE schedule
                                (Form 461, Schedule 1)
  EXPN_CD FORM_TYPE='F465P3'  - Form 465 supplemental IE report
                                (Schedule 3)
  S496_CD FORM_TYPE='F496'    - 24-hour IE late filings

Out of primary scope per Codex round-10:
  EXPN_CD FORM_TYPE='E'       - committee Schedule E spending.
                                Cannot be cleanly separated from
                                ordinary committee spending (the
                                spending side of receipts already
                                counted) without a separate
                                diagnostic. Ships as a separate
                                sub-phase later.
  S497_CD                     - cross-check only, not authoritative
                                (late-report duplicate-prone).
  S401_CD                     - slate mailer, out-of-v3.

Codex round-10 design choices integrated:
- Pre-filter EXPN_CD by FORM_TYPE in BOTH amend pass and row pass.
- Filing-grain latest-amend dedup (matches Phase 2 correction).
- Resolver chain: row_fields -> cover_sheet -> filer_name ->
  manual_override -> quarantine. Conditional cover-stance fallback
  when row prop matches cover prop (in resolve_from_row_fields).
- Streaming chunked inserts: 25K rows per executemany within a
  single BEGIN/COMMIT.
- DELETE prior IE rows scoped by source_table + form_type (not all
  EXPN_CD — Schedule E diagnostic rows may coexist later).
- Provenance: source_crosswalk_campaign_id from
  FilingAttribution.source_crosswalk_campaign_id.

Usage:
    python -m scripts.v3.ingest_ies
    python -m scripts.v3.ingest_ies --dry-run
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
    from v3 import resolver as resolver_mod
else:
    from . import lib
    from .attribution import build_filing_attribution_index
    from . import resolver as resolver_mod


# Codex round-10: primary IE form types only. Schedule E ('E')
# excluded from this pass — separate diagnostic / future sub-phase.
ALLOWED_EXPN_FORM_TYPES = {"F461P5", "F465P3"}

# Insert batch size (Codex round-10: 25K is the sweet spot for our
# row dict size).
INSERT_BATCH_SIZE = 25_000


def _build_resolver_for_ingest(v2_db: Path):
    """Same crosswalk + manual_overrides + match_via as the unified
    attribution index, but returned as a resolver so we can call
    resolve_from_row_fields directly on each IE row (the attribution
    index is per-filing, but Phase 4 attribution is per-row)."""
    from v3.attribution import _load_v2_crosswalk, _load_manual_overrides

    crosswalk, match_via_by_cid = _load_v2_crosswalk(v2_db)
    overrides_path = Path(
        "data/CalAccess/manual_attribution_overrides.json"
    )
    overrides = _load_manual_overrides(
        overrides_path if overrides_path.exists() else None
    )
    return resolver_mod.AttributionResolver(
        crosswalk,
        manual_overrides=overrides,
        match_via_by_cid=match_via_by_cid,
    )


def _open_cursor_for_chunked_insert(v3_db: Path):
    con = sqlite3.connect(str(v3_db), isolation_level=None)
    cur = con.cursor()
    cur.execute("BEGIN")
    return con, cur


def _flush_buffer(cur, buf, insert_sql):
    if not buf:
        return 0
    cur.executemany(
        insert_sql,
        [tuple(r[c] for c in lib.FLOW_COLUMNS) for r in buf],
    )
    n = len(buf)
    buf.clear()
    return n


def _empty_row() -> dict:
    return {c: None for c in lib.FLOW_COLUMNS}


# ---------------------------------------------------------------------------
# S496_CD ingest
# ---------------------------------------------------------------------------


def ingest_s496(dump_dir: Path,
                filing_idx: dict,
                cur,
                insert_sql: str,
                dry_run: bool,
                verbose: bool) -> Counter:
    """S496 has no row-level BAL_NUM / SUP_OPP_CD. Attribution flows
    through the filing index (cover-sheet -> filer-name -> manual
    override -> quarantine). Donor identity = the filer (the entity
    making the IE). Payee not present on the row."""
    path = dump_dir / "S496_CD.TSV"
    if not path.exists():
        raise SystemExit(f"Missing source: {path}")

    if verbose:
        print(f"S496_CD pass 1: latest amend per FILING_ID "
              f"({path.stat().st_size / 1e6:.1f}MB)...")

    latest_amend: dict[str, int] = {}
    with path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}
        for row in reader:
            fid = row[cols["FILING_ID"]] if "FILING_ID" in cols else ""
            if not fid:
                continue
            try:
                amend = int(row[cols.get("AMEND_ID", -1)] or 0)
            except (ValueError, IndexError):
                amend = 0
            if amend > latest_amend.get(fid, -1):
                latest_amend[fid] = amend

    if verbose:
        print(f"  Unique FILING_IDs: {len(latest_amend):,}")
        print(f"S496_CD pass 2: build rows...")

    stats: Counter[str] = Counter()
    buf: list[dict] = []
    inserted = 0

    with path.open(encoding="latin-1", newline="") as f:
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
            memo_code = c(row, "MEMO_CODE")
            line = c(row, "LINE_ITEM")
            tran_id = c(row, "TRAN_ID")
            memo_refno = c(row, "MEMO_REFNO")
            date_str = c(row, "EXP_DATE")
            txn_date = lib.parse_calaccess_date(date_str)
            amt_raw = c(row, "AMOUNT")
            if lib.is_null(amt_raw):
                amount: float | None = None
            else:
                try:
                    amount = float(amt_raw)
                except (ValueError, TypeError):
                    amount = None
            expn_dscr = c(row, "EXPN_DSCR")

            attr = filing_idx.get(fid)
            # Donor identity for S496 is the filer (who made the IE)
            donor_name_raw = (attr.cover_filer_name if attr else None) or None
            donor_canon = (
                lib.canonicalize_donor(donor_name_raw) if donor_name_raw
                else None
            )
            txn_date_iso = txn_date.isoformat() if txn_date else None
            week_start = lib.week_start_iso(txn_date) if txn_date else None

            source_fingerprint = (
                f"S496_CD|{form_type}|{fid}|{amend}|{line}|{tran_id}"
            )
            # Codex round-10: economic_fingerprint enriched with
            # payee + post-attribution target for IE flows.
            economic_fingerprint = _economic_fingerprint_ie(
                donor_canon, txn_date_iso, amount,
                payee_name=None,  # S496 has no payee on row
                target_cid=(attr.finance_campaign_id if attr else None),
                target_stance=(attr.stance if attr else None),
            )

            base = _empty_row()
            base.update({
                "amount": amount,
                "txn_date": txn_date_iso,
                "week_start": week_start,
                "receipt_type": "independent_expenditure",
                "source_table": "S496_CD",
                "source_form_type": form_type,
                "filing_id": fid,
                "amend_id": amend,
                "source_line_item": line,
                "source_tran_id": tran_id,
                "source_memo_refno": (
                    memo_refno if not lib.is_null(memo_refno) else None
                ),
                "amount_field_used": "AMOUNT",
                "donor_name_raw": donor_name_raw,
                "donor_name_canon": donor_canon,
                "donor_type": "other",
                "reported_filer": donor_name_raw,
                "memo_code": memo_code if not lib.is_null(memo_code) else None,
                "source_fingerprint": source_fingerprint,
                "economic_fingerprint": economic_fingerprint,
            })
            if attr:
                _apply_cover(base, attr)

            quarantine_reason = None
            if not lib.is_null(memo_code):
                quarantine_reason = "memo_row"
            elif attr is None:
                quarantine_reason = "no_cover_sheet"
            elif attr.finance_campaign_id is None:
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
                    attr.source_crosswalk_campaign_id
                    or attr.finance_campaign_id
                )
                base["measure_db_id"] = attr.measure_db_id
                base["stance"] = attr.stance
                base["attribution_source"] = "filer"
                base["dedupe_key"] = (
                    f"ie|{attr.finance_campaign_id}|{attr.stance}|"
                    f"{donor_canon}||{txn_date_iso}|{amount:.2f}|"
                    f"{attr.cover_filer_id or ''}"
                )
                stats[f"accepted_via_{attr.attribution_method}"] += 1
                stats["accepted"] += 1

            buf.append(base)
            if len(buf) >= INSERT_BATCH_SIZE and not dry_run:
                inserted += _flush_buffer(cur, buf, insert_sql)

    if buf and not dry_run:
        inserted += _flush_buffer(cur, buf, insert_sql)

    stats["inserted_to_db"] = inserted
    return stats


# ---------------------------------------------------------------------------
# EXPN_CD F461P5 / F465P3 ingest
# ---------------------------------------------------------------------------


def ingest_expn_ies(dump_dir: Path,
                    filing_idx: dict,
                    resolver: resolver_mod.AttributionResolver,
                    cur,
                    insert_sql: str,
                    dry_run: bool,
                    verbose: bool) -> Counter:
    """EXPN_CD F461P5 + F465P3 rows. Each row has row_bal_num +
    row_sup_opp_cd usually populated; use those for row-level
    attribution. Fall back to cover/filer when row fields missing.

    Codex round-10: PRE-FILTER by FORM_TYPE in BOTH passes to skip
    the 2.4GB of Schedule E/D/G rows we don't need.
    """
    path = dump_dir / "EXPN_CD.TSV"
    if not path.exists():
        raise SystemExit(f"Missing source: {path}")

    if verbose:
        print()
        print(f"EXPN_CD pass 1: latest amend per FILING_ID "
              f"(pre-filtered to {sorted(ALLOWED_EXPN_FORM_TYPES)}); "
              f"file size {path.stat().st_size / 1e9:.1f}GB...")

    latest_amend: dict[str, int] = {}
    expn_rows_scanned = 0
    expn_rows_kept = 0
    with path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}
        fid_idx = cols.get("FILING_ID")
        amend_idx = cols.get("AMEND_ID")
        form_idx = cols.get("FORM_TYPE")
        for row in reader:
            expn_rows_scanned += 1
            if form_idx is None or form_idx >= len(row):
                continue
            ft = (row[form_idx] or "").strip()
            if ft not in ALLOWED_EXPN_FORM_TYPES:
                continue
            expn_rows_kept += 1
            fid = row[fid_idx] if (fid_idx is not None
                                   and fid_idx < len(row)) else ""
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
        print(f"  Total EXPN_CD rows: {expn_rows_scanned:,}")
        print(f"  Rows in allow-list: {expn_rows_kept:,}")
        print(f"  Unique FILING_IDs:  {len(latest_amend):,}")
        print(f"EXPN_CD pass 2: build IE rows...")

    stats: Counter[str] = Counter()
    buf: list[dict] = []
    inserted = 0

    with path.open(encoding="latin-1", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        cols = {n: i for i, n in enumerate(header)}

        def c(row, name):
            i = cols.get(name)
            return row[i] if i is not None and i < len(row) else ""

        for row in reader:
            form_type = (c(row, "FORM_TYPE") or "").strip()
            if form_type not in ALLOWED_EXPN_FORM_TYPES:
                continue
            stats["scanned_in_scope"] += 1
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

            memo_code = c(row, "MEMO_CODE")
            line = c(row, "LINE_ITEM")
            tran_id = c(row, "TRAN_ID")
            bakref = c(row, "BAKREF_TID")
            memo_refno = c(row, "MEMO_REFNO")
            payee_last = c(row, "PAYEE_NAML")
            payee_first = c(row, "PAYEE_NAMF")
            payee_name = (
                f"{payee_last}, {payee_first}".strip(", ")
                if payee_first and not lib.is_null(payee_first)
                else (payee_last or "")
            ).strip()
            entity_cd = c(row, "ENTITY_CD")
            date_str = c(row, "EXPN_DATE")
            txn_date = lib.parse_calaccess_date(date_str)
            amt_raw = c(row, "AMOUNT")
            if lib.is_null(amt_raw):
                amount: float | None = None
            else:
                try:
                    amount = float(amt_raw)
                except (ValueError, TypeError):
                    amount = None
            row_bal_num = c(row, "BAL_NUM")
            row_bal_name = c(row, "BAL_NAME")
            row_bal_juris = c(row, "BAL_JURIS")
            row_sup_opp_cd = c(row, "SUP_OPP_CD")

            attr = filing_idx.get(fid)
            # Donor identity for EXPN IE rows is the FILER (the major
            # donor / IE committee). The payee is the vendor that got
            # paid.
            donor_name_raw = (attr.cover_filer_name if attr else None) or None
            donor_canon = (
                lib.canonicalize_donor(donor_name_raw) if donor_name_raw
                else None
            )

            txn_date_iso = txn_date.isoformat() if txn_date else None
            week_start = lib.week_start_iso(txn_date) if txn_date else None

            source_fingerprint = (
                f"EXPN_CD|{form_type}|{fid}|{amend}|{line}|{tran_id}"
            )

            base = _empty_row()
            base.update({
                "amount": amount,
                "txn_date": txn_date_iso,
                "week_start": week_start,
                "receipt_type": "independent_expenditure",
                "source_table": "EXPN_CD",
                "source_form_type": form_type,
                "filing_id": fid,
                "amend_id": amend,
                "source_line_item": line,
                "source_tran_id": tran_id,
                "source_bakref_tid": bakref if not lib.is_null(bakref) else None,
                "source_memo_refno": (
                    memo_refno if not lib.is_null(memo_refno) else None
                ),
                "amount_field_used": "AMOUNT",
                "row_bal_num": (
                    row_bal_num if not lib.is_null(row_bal_num) else None
                ),
                "row_bal_name": (
                    row_bal_name if not lib.is_null(row_bal_name) else None
                ),
                "row_bal_juris": (
                    row_bal_juris if not lib.is_null(row_bal_juris) else None
                ),
                "row_sup_opp_cd": (
                    row_sup_opp_cd if not lib.is_null(row_sup_opp_cd)
                    else None
                ),
                "donor_name_raw": donor_name_raw,
                "donor_name_canon": donor_canon,
                "donor_type": (
                    "individual"
                    if (entity_cd or "").strip().upper() == "IND"
                    else "other"
                ),
                "reported_filer": donor_name_raw,
                "payee_name": payee_name or None,
                "memo_code": memo_code if not lib.is_null(memo_code) else None,
                "source_fingerprint": source_fingerprint,
            })
            if attr:
                _apply_cover(base, attr)

            # Codex round-10 resolver chain: row_fields -> cover_sheet
            # -> filer_name -> manual_override -> quarantine.
            quarantine_reason = None
            attribution_method = "failed"
            resolved_cid = None
            resolved_source_cid = None
            resolved_mdb = None
            resolved_stance = None

            if not lib.is_null(memo_code):
                quarantine_reason = "memo_row"
            elif amount is None:
                quarantine_reason = "unparseable_amount"
            elif amount <= 0:
                quarantine_reason = "non_positive_amount"
            elif txn_date is None:
                quarantine_reason = "unparseable_date"

            if not quarantine_reason:
                date_hints = []
                if txn_date is not None:
                    date_hints.append(txn_date)
                if attr:
                    for raw in (attr.cover_elect_date,
                                attr.cover_thru_date,
                                attr.cover_from_date):
                        d = lib.parse_calaccess_date(raw)
                        if d is not None:
                            date_hints.append(d)

                # Codex round-12: multi-prop / non-statewide BAL_NUM
                # or BAL_NAME signals (26/27, 25 & 26, RM/4, etc.)
                # must NOT fall back to cover sheet. Cover may attribute
                # to a different specific prop, which would still be
                # wrong because the row-level signal is genuinely
                # ambiguous.
                row_has_ambig = (
                    resolver_mod.has_multi_prop_signal(
                        row_bal_num if not lib.is_null(row_bal_num) else ""
                    )
                    or resolver_mod.has_multi_prop_signal(
                        row_bal_name if not lib.is_null(row_bal_name) else ""
                    )
                )
                # 1. Row-level fields if a row prop signal is present
                row_prop = (
                    row_bal_num
                    if row_bal_num and not lib.is_null(row_bal_num)
                    else (row_bal_name
                          if row_bal_name and not lib.is_null(row_bal_name)
                          else None)
                )
                r = None
                if row_prop and not row_has_ambig:
                    r = resolver.resolve_from_row_fields(
                        row_bal_num=(row_bal_num
                                     if not lib.is_null(row_bal_num)
                                     else None),
                        row_bal_name=(row_bal_name
                                      if not lib.is_null(row_bal_name)
                                      else None),
                        row_sup_opp_cd=(row_sup_opp_cd
                                        if not lib.is_null(row_sup_opp_cd)
                                        else None),
                        date_hints=date_hints,
                        cover_bal_num=(attr.cover_bal_num if attr else None),
                        cover_sup_opp_cd=(
                            attr.cover_sup_opp_cd if attr else None
                        ),
                    )
                    if r.resolved:
                        attribution_method = r.attribution_method
                        resolved_cid = r.finance_campaign_id
                        resolved_source_cid = (
                            r.source_crosswalk_campaign_id or r.finance_campaign_id
                        )
                        resolved_mdb = r.measure_db_id
                        resolved_stance = r.stance

                # 2. Cover sheet ONLY when no row-level multi-prop
                # signal AND row resolution didn't produce a result
                # for a benign reason (no row info at all, or row
                # info was AG queue / non-statewide / etc. — but NOT
                # because row signal was multi-prop)
                if (resolved_cid is None
                        and not row_has_ambig
                        and attr
                        and attr.finance_campaign_id):
                    attribution_method = attr.attribution_method
                    resolved_cid = attr.finance_campaign_id
                    resolved_source_cid = (
                        attr.source_crosswalk_campaign_id
                        or attr.finance_campaign_id
                    )
                    resolved_mdb = attr.measure_db_id
                    resolved_stance = attr.stance

                # 3. quarantine if still unresolved
                if resolved_cid is None:
                    if row_has_ambig:
                        quarantine_reason = "ambiguous_multi_prop"
                    else:
                        quarantine_reason = (
                            (attr.quarantine_reason if attr else None)
                            or (r.quarantine_reason if r is not None else None)
                            or "no_campaign_match"
                        )
                elif resolved_stance is None:
                    quarantine_reason = "unknown_stance"

            economic_fingerprint = _economic_fingerprint_ie(
                donor_canon, txn_date_iso, amount,
                payee_name=payee_name or None,
                target_cid=resolved_cid,
                target_stance=resolved_stance,
            )
            base["economic_fingerprint"] = economic_fingerprint

            if quarantine_reason:
                base["quarantine_reason"] = quarantine_reason
                base["receipt_type"] = None
                stats[f"quarantine_{quarantine_reason}"] += 1
            else:
                base["finance_campaign_id"] = resolved_cid
                base["source_crosswalk_campaign_id"] = resolved_source_cid
                base["measure_db_id"] = resolved_mdb
                base["stance"] = resolved_stance
                base["attribution_source"] = "filer"
                base["attribution_method"] = attribution_method
                base["dedupe_key"] = (
                    f"ie|{resolved_cid}|{resolved_stance}|"
                    f"{donor_canon}|{payee_name or ''}|"
                    f"{txn_date_iso}|{amount:.2f}|"
                    f"{(attr.cover_filer_id if attr else '') or ''}"
                )
                stats[f"accepted_via_{attribution_method}"] += 1
                stats["accepted"] += 1

            buf.append(base)
            if len(buf) >= INSERT_BATCH_SIZE and not dry_run:
                inserted += _flush_buffer(cur, buf, insert_sql)

    if buf and not dry_run:
        inserted += _flush_buffer(cur, buf, insert_sql)

    stats["inserted_to_db"] = inserted
    return stats


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _apply_cover(base: dict, attr) -> None:
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


def _economic_fingerprint_ie(donor_canon: str | None,
                             txn_date_iso: str | None,
                             amount: float | None,
                             payee_name: str | None,
                             target_cid: str | None,
                             target_stance: str | None) -> str:
    """Codex round-10: stronger fingerprint for IE flows. Donor+date+
    amount alone are too weak — same donor can have multiple payees,
    multiple props. Adds payee_name + target campaign+stance."""
    return (
        f"{(donor_canon or '')}|{(payee_name or '')}|"
        f"{txn_date_iso or ''}|"
        f"{(amount if amount is not None else ''):}|"
        f"{(target_cid or '')}|{(target_stance or '')}|ie"
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def ingest_ies(dump_dir: Path, v2_db: Path, v3_db: Path,
               manual_overrides_path: Path | None = None,
               dry_run: bool = False, verbose: bool = True) -> dict:
    filing_idx = build_filing_attribution_index(
        dump_dir, v2_db,
        manual_overrides_path=manual_overrides_path,
        verbose=verbose,
    )
    resolver = _build_resolver_for_ingest(v2_db)

    placeholders = ",".join("?" for _ in lib.FLOW_COLUMNS)
    columns = ",".join(lib.FLOW_COLUMNS)
    insert_sql = (
        f"INSERT INTO finance_flow_v3 ({columns}) VALUES ({placeholders})"
    )

    if dry_run:
        con, cur = None, None
    else:
        con, cur = _open_cursor_for_chunked_insert(v3_db)

    all_stats: dict[str, Counter] = {}

    try:
        if not dry_run:
            # Codex round-10: scoped DELETE — keep any future Schedule E
            # diagnostic rows intact.
            cur.execute(
                "DELETE FROM finance_flow_v3 "
                "WHERE source_table='S496_CD'"
            )
            for ft in ALLOWED_EXPN_FORM_TYPES:
                cur.execute(
                    "DELETE FROM finance_flow_v3 "
                    "WHERE source_table='EXPN_CD' AND source_form_type=?",
                    (ft,),
                )

        all_stats["s496"] = ingest_s496(
            dump_dir, filing_idx, cur, insert_sql, dry_run, verbose
        )
        all_stats["expn"] = ingest_expn_ies(
            dump_dir, filing_idx, resolver, cur, insert_sql,
            dry_run, verbose,
        )

        if not dry_run:
            cur.execute("COMMIT")
    except Exception:
        if cur is not None:
            cur.execute("ROLLBACK")
        raise
    finally:
        if con is not None:
            con.close()

    if verbose:
        print()
        for src, stats in all_stats.items():
            print(f"=== {src.upper()} stats ===")
            for k, v in stats.most_common():
                print(f"  {k:55} {v:>10,}")

    return {k: dict(v) for k, v in all_stats.items()}


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
    ingest_ies(Path(args.dump_dir), Path(args.v2_db), Path(args.v3_db),
               manual_overrides_path=overrides,
               dry_run=args.dry_run, verbose=True)


if __name__ == "__main__":
    main()
