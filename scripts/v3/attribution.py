"""Unified filing-attribution index for v3 finance ingest.

Reads ALL CVR_CAMPAIGN_DISCLOSURE_CD cover sheets (not just the
ballot-measure-tagged subset) and runs the AttributionResolver chain
over each. The chain in order: cover_sheet -> filer_name_explicit
-> manual_override. Whatever doesn't resolve carries the appropriate
quarantine_reason from the resolver.

Output: FILING_ID -> FilingAttribution dict. Consumed by Phase 2+
ingest scripts in place of the simpler `load_cover_attributions`
function that lives inside ingest_loans.py.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from v3 import lib, resolver
else:
    from . import lib, resolver


@dataclass
class FilingAttribution:
    """Resolved attribution for a single FILING_ID."""

    filing_id: str

    # Cover-sheet metadata (raw strings, as found in CVR)
    cover_form_type: str = ""
    cover_filer_id: str = ""
    cover_filer_name: str = ""
    cover_committee_id: str = ""
    cover_bal_num: str = ""
    cover_bal_name: str = ""
    cover_bal_juris: str = ""
    cover_sup_opp_cd: str = ""
    cover_elect_date: str = ""
    cover_from_date: str = ""
    cover_thru_date: str = ""

    # Parsed prop_num and election_year (if cover-sheet path could
    # populate them)
    parsed_prop_num: Optional[str] = None
    parsed_election_year: Optional[int] = None

    # Resolved attribution (set by the chain)
    finance_campaign_id: Optional[str] = None
    measure_db_id: Optional[int] = None
    stance: Optional[str] = None
    attribution_method: str = "failed"
    quarantine_reason: Optional[str] = None
    debug: list[str] = field(default_factory=list)


def _load_v2_crosswalk(v2_db: Path) -> dict[tuple[str, int],
                                            tuple[str, int]]:
    crosswalk: dict[tuple[str, int], tuple[str, int]] = {}
    with sqlite3.connect(str(v2_db)) as v2:
        for r in v2.execute(
            "SELECT prop_num, election_year, finance_campaign_id, "
            "       measure_db_id "
            "FROM finance_campaign WHERE status = 'matched'"
        ):
            prop_num, year, cid, mdb = r
            if year and mdb is not None:
                crosswalk[(prop_num, int(year))] = (cid, int(mdb))
    return crosswalk


def _load_manual_overrides(path: Optional[Path]) -> dict:
    """Load manual overrides from a JSON file. Format:

        {
          "filer_name_lower_normalized": [
            ["finance_campaign_id", "stance"],
            ...
          ],
          "filer_id_string": [
            ["finance_campaign_id", "stance"]
          ]
        }
    """
    if not path or not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict = {}
    for key, entries in raw.items():
        out[key] = [tuple(e) for e in entries]
    return out


def _collect_date_hints(att: FilingAttribution) -> list[date]:
    hints = []
    for raw in (att.cover_elect_date, att.cover_thru_date,
                att.cover_from_date):
        d = lib.parse_calaccess_date(raw)
        if d is not None:
            hints.append(d)
    return hints


def build_filing_attribution_index(
    dump_dir: Path,
    v2_db: Path,
    manual_overrides_path: Optional[Path] = None,
    *,
    verbose: bool = True,
) -> dict[str, FilingAttribution]:
    crosswalk = _load_v2_crosswalk(v2_db)
    if verbose:
        print(f"v2 crosswalk: {len(crosswalk):,} (prop_num, year) entries")

    manual_overrides = _load_manual_overrides(manual_overrides_path)
    if manual_overrides and verbose:
        print(f"Manual overrides loaded: {len(manual_overrides)}")

    R = resolver.AttributionResolver(crosswalk, manual_overrides)

    cvr_path = dump_dir / "CVR_CAMPAIGN_DISCLOSURE_CD.TSV"
    if not cvr_path.exists():
        raise SystemExit(f"Missing source: {cvr_path}")

    # Pass 1: latest amend per FILING_ID across ALL filings
    if verbose:
        print(f"Pass 1: scanning CVR for latest-amend ALL filings...")
    latest: dict[str, dict] = {}
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
            prior = latest.get(fid)
            if prior is None or amend > prior["amend_id"]:
                latest[fid] = {
                    "amend_id": amend,
                    "cover_form_type": c(row, "FORM_TYPE"),
                    "cover_filer_id": c(row, "FILER_ID"),
                    "cover_filer_name": c(row, "FILER_NAML"),
                    "cover_committee_id": c(row, "CMTTE_ID"),
                    "cover_bal_num": c(row, "BAL_NUM"),
                    "cover_bal_name": c(row, "BAL_NAME"),
                    "cover_bal_juris": c(row, "BAL_JURIS"),
                    "cover_sup_opp_cd": c(row, "SUP_OPP_CD"),
                    "cover_elect_date": c(row, "ELECT_DATE"),
                    "cover_from_date": c(row, "FROM_DATE"),
                    "cover_thru_date": c(row, "THRU_DATE"),
                }
    if verbose:
        print(f"  Unique FILING_IDs in CVR: {len(latest):,}")
        print()
        print(f"Pass 2: applying resolver chain...")

    # Pass 2: apply resolver to each filing
    out: dict[str, FilingAttribution] = {}
    method_counts: dict[str, int] = {}
    for fid, info in latest.items():
        att = FilingAttribution(filing_id=fid, **{k: v for k, v in info.items()
                                                   if k != "amend_id"})
        elect = lib.parse_calaccess_date(info["cover_elect_date"])
        att.parsed_election_year = elect.year if elect else None
        att.parsed_prop_num = lib.extract_prop_num(
            info["cover_bal_name"], info["cover_bal_num"]
        )

        date_hints = _collect_date_hints(att)

        # 1. Cover sheet
        r = R.resolve_from_cover_sheet(
            att.parsed_prop_num,
            att.parsed_election_year,
            info["cover_sup_opp_cd"],
        )
        if r.resolved:
            _apply_result(att, r)
            method_counts[r.attribution_method] = method_counts.get(
                r.attribution_method, 0
            ) + 1
            out[fid] = att
            continue

        # Cover sheet failed (or returned unknown_stance). Record the
        # debug + reason but try filer name next; if filer name also
        # fails, the cover-sheet quarantine_reason will be the final.
        cover_quarantine = r.quarantine_reason
        cover_debug = r.debug

        # 2. Filer-name fallback
        r2 = R.resolve_from_filer_name(
            info["cover_filer_name"], date_hints
        )
        if r2.resolved:
            _apply_result(att, r2)
            method_counts[r2.attribution_method] = method_counts.get(
                r2.attribution_method, 0
            ) + 1
            out[fid] = att
            continue

        # 3. Manual override fallback
        r3 = R.resolve_from_manual_override(
            info["cover_filer_id"], info["cover_filer_name"]
        )
        if r3.resolved:
            _apply_result(att, r3)
            method_counts[r3.attribution_method] = method_counts.get(
                r3.attribution_method, 0
            ) + 1
            out[fid] = att
            continue

        # All three failed. Prefer the most-specific failure reason:
        # filer_name's diagnosis is more specific than cover_sheet's
        # bad_prop_or_year, unless cover sheet had a real failure
        # (no_campaign_match means we DID find a prop but the year
        # didn't crosswalk; that's stronger evidence)
        best_r = _pick_best_failure(r, r2, r3)
        att.attribution_method = "failed"
        att.quarantine_reason = best_r.quarantine_reason
        att.debug = cover_debug + r2.debug + r3.debug
        method_counts[f"failed/{best_r.quarantine_reason}"] = (
            method_counts.get(f"failed/{best_r.quarantine_reason}", 0) + 1
        )
        out[fid] = att

    if verbose:
        print()
        print(f"=== Resolver chain results ===")
        for method, count in sorted(method_counts.items(),
                                     key=lambda kv: kv[1], reverse=True):
            print(f"  {method:50} {count:>8,}")
    return out


def _apply_result(att: FilingAttribution,
                  r: resolver.AttributionResult) -> None:
    att.finance_campaign_id = r.finance_campaign_id
    att.measure_db_id = r.measure_db_id
    att.stance = r.stance
    att.attribution_method = r.attribution_method
    att.quarantine_reason = r.quarantine_reason


def _pick_best_failure(*results: resolver.AttributionResult
                       ) -> resolver.AttributionResult:
    """Pick the most informative failure for diagnostic purposes."""
    priority = {
        "no_campaign_match": 10,
        "ambiguous_year": 9,
        "ambiguous_multi_prop": 8,
        "unknown_stance": 7,
        "filer_name_no_prop": 5,
        "bad_prop_or_year": 3,
        None: 0,
    }
    return max(results, key=lambda r: priority.get(r.quarantine_reason, 1))


# ---------------------------------------------------------------------------
# CLI entry point: produce a CSV report of attribution outcomes
# ---------------------------------------------------------------------------


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", default=str(lib.DUMP_DIR))
    parser.add_argument("--v2-db", default=str(lib.V2_DB))
    parser.add_argument("--manual-overrides", default=None,
                        help="Optional path to manual-override JSON")
    parser.add_argument("--out", default=str(
        Path("data/CalAccess/filing_attribution_index.csv")
    ))
    args = parser.parse_args()

    overrides_path = (Path(args.manual_overrides)
                      if args.manual_overrides else None)
    idx = build_filing_attribution_index(
        Path(args.dump_dir), Path(args.v2_db),
        manual_overrides_path=overrides_path,
        verbose=True,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "filing_id", "cover_form_type", "cover_filer_name",
        "cover_bal_num", "cover_bal_name", "cover_elect_date",
        "parsed_prop_num", "parsed_election_year",
        "finance_campaign_id", "stance", "attribution_method",
        "quarantine_reason",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for fid in sorted(idx):
            att = idx[fid]
            w.writerow([getattr(att, k, "") or "" for k in fields])
    print(f"Index written to {out_path}: {len(idx):,} filings")


if __name__ == "__main__":
    main()
