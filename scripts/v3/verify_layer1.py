"""Layer 1 no-regression verification for the v3 finance expansion.

Per docs/plans/finance-extract-scope-expansion.md "Verification strategy
-> Layer 1": every phase boundary must show that the v2 finance tables
are unchanged from the pre-v3 baseline AND that the v3 monetary slice
matches the v2 monetary table to the penny.

Baseline source: data/CalAccess/v2_pre_v3_baseline.json (sha256 hash
verified at run).

Layer 1 assertions (7 total):
  1. Exact same finance_summary keys (campaign, stance) as baseline
  2. Exact same finance_summary values (to the penny / 4 decimals)
  3. Exact same top-5 donor keys per (campaign, stance) as baseline
  4. Exact same top-5 donor values (donor_type + amount to the penny)
  5. v3 monetary slice equals v2 monetary baseline for all 194 campaigns
  6. Campaign count == baseline's campaign_count (194)
  7. Baseline file self-hash unchanged

In Phase 1 (no data loaded into v3 yet), assertions 1-4 + 6-7 still
hold (we just re-query v2). Assertion 5 trivially passes (zero rows
in v3 means the monetary slice is empty; we skip the cross-check
unless v3 has at least one row).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BASELINE = REPO_ROOT / "data" / "CalAccess" / "v2_pre_v3_baseline.json"
DEFAULT_V2_DB = REPO_ROOT / "scraper" / "data" / "finance" / "finance_statewide_v2.db"
DEFAULT_V3_DB = REPO_ROOT / "scraper" / "data" / "finance" / "finance_statewide_v3.db"

PENNY = 0.005  # rounding tolerance for dollar comparisons
SHARE_EPSILON = 0.0001  # for top5_share / hhi (already rounded to 4 decimals)


class Layer1Result:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, ok, detail))

    def report(self) -> int:
        passed = sum(1 for _, ok, _ in self.checks if ok)
        failed = sum(1 for _, ok, _ in self.checks if not ok)
        print()
        print(f"=== Layer 1 results: {passed}/{passed + failed} passed ===")
        for name, ok, detail in self.checks:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {name}")
            if detail and (not ok or "info:" in detail.lower()):
                for line in detail.splitlines():
                    print(f"         {line}")
        return 0 if failed == 0 else 1


def verify_baseline_hash(baseline_path: Path, result: Layer1Result) -> dict | None:
    if not baseline_path.exists():
        result.record("7. baseline_file_exists", False,
                      f"missing: {baseline_path}")
        return None
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    stored_hash = data.get("_self_hash")
    if not stored_hash:
        result.record("7. baseline_self_hash", False,
                      "baseline has no _self_hash field")
        return None
    # Recompute hash without _self_hash
    payload = dict(data)
    payload.pop("_self_hash", None)
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    actual = hashlib.sha256(canon.encode()).hexdigest()
    ok = (actual == stored_hash)
    result.record("7. baseline_self_hash_unchanged", ok,
                  f"stored={stored_hash[:16]}...\n"
                  f"actual={actual[:16]}..." if not ok else
                  f"info: hash={stored_hash[:16]}...")
    return data if ok else None


def query_v2_summary(v2_db: Path) -> dict[str, dict]:
    """Returns {f'{cid}|{stance}': {fields}} for all finance_summary rows."""
    con = sqlite3.connect(str(v2_db))
    out = {}
    for r in con.execute(
        "SELECT finance_campaign_id, stance, total_receipts, "
        "n_committees, top5_share, hhi "
        "FROM finance_summary ORDER BY finance_campaign_id, stance"
    ):
        cid, stance, total, ncom, t5, hhi = r
        out[f"{cid}|{stance}"] = {
            "total_receipts": round(total, 2),
            "n_committees": ncom,
            "top5_share": round(t5, 4) if t5 is not None else None,
            "hhi": round(hhi, 4) if hhi is not None else None,
        }
    con.close()
    return out


def query_v2_top_donors(v2_db: Path) -> dict[str, list]:
    """Returns {f'{cid}|{stance}': [{donor, type, amount}, ...]} top-5."""
    con = sqlite3.connect(str(v2_db))
    cids = set()
    for r in con.execute("SELECT DISTINCT finance_campaign_id FROM finance_summary"):
        cids.add(r[0])
    out = {}
    for cid in sorted(cids):
        for stance in ("support", "oppose"):
            rows = list(con.execute(
                "SELECT donor_name_canon, donor_type, total_amount "
                "FROM finance_top_donors "
                "WHERE finance_campaign_id=? AND stance=? "
                "ORDER BY total_amount DESC LIMIT 5",
                (cid, stance),
            ))
            if rows:
                out[f"{cid}|{stance}"] = [
                    {"donor": d[0], "type": d[1], "amount": round(d[2], 2)}
                    for d in rows
                ]
    con.close()
    return out


def compare_summary(baseline: dict, current: dict, result: Layer1Result) -> None:
    base_keys = set(baseline.keys())
    cur_keys = set(current.keys())

    only_baseline = base_keys - cur_keys
    only_current = cur_keys - base_keys
    if only_baseline or only_current:
        detail = []
        if only_baseline:
            detail.append(f"missing in v2 now: {len(only_baseline)} keys "
                          f"(e.g. {next(iter(only_baseline))})")
        if only_current:
            detail.append(f"new in v2 now: {len(only_current)} keys "
                          f"(e.g. {next(iter(only_current))})")
        result.record("1. finance_summary_keys_match", False, "\n".join(detail))
        return
    result.record("1. finance_summary_keys_match", True,
                  f"info: {len(base_keys)} (campaign, stance) keys")

    mismatches = []
    for key in sorted(base_keys):
        b = baseline[key]
        c = current[key]
        if abs((b["total_receipts"] or 0) - (c["total_receipts"] or 0)) > PENNY:
            mismatches.append(f"{key} total: {b['total_receipts']} -> "
                              f"{c['total_receipts']}")
            continue
        if b["n_committees"] != c["n_committees"]:
            mismatches.append(f"{key} n_committees: {b['n_committees']} -> "
                              f"{c['n_committees']}")
            continue
        for field in ("top5_share", "hhi"):
            bv = b[field] or 0
            cv = c[field] or 0
            if abs(bv - cv) > SHARE_EPSILON:
                mismatches.append(f"{key} {field}: {bv} -> {cv}")
                break
    if mismatches:
        result.record("2. finance_summary_values_match", False,
                      f"{len(mismatches)} mismatch(es); first 5:\n  "
                      + "\n  ".join(mismatches[:5]))
    else:
        result.record("2. finance_summary_values_match", True,
                      f"info: all {len(base_keys)} rows match to penny / "
                      f"4 decimals")


def compare_top_donors(baseline: dict, current: dict, result: Layer1Result) -> None:
    base_keys = set(baseline.keys())
    cur_keys = set(current.keys())
    only_baseline = base_keys - cur_keys
    only_current = cur_keys - base_keys
    if only_baseline or only_current:
        result.record("3. top_donors_keys_match", False,
                      f"missing now: {len(only_baseline)}, new: "
                      f"{len(only_current)}")
        return
    result.record("3. top_donors_keys_match", True,
                  f"info: {len(base_keys)} (campaign, stance) groupings")

    mismatches = []
    for key in sorted(base_keys):
        b_list = baseline[key]
        c_list = current[key]
        b_donors = [d["donor"] for d in b_list]
        c_donors = [d["donor"] for d in c_list]
        if b_donors != c_donors:
            mismatches.append(f"{key} donor order: {b_donors[:3]} -> "
                              f"{c_donors[:3]}")
            continue
        for b, c in zip(b_list, c_list):
            if b["type"] != c["type"]:
                mismatches.append(f"{key} donor {b['donor']!r} type: "
                                  f"{b['type']} -> {c['type']}")
                break
            if abs(b["amount"] - c["amount"]) > PENNY:
                mismatches.append(f"{key} donor {b['donor']!r} amt: "
                                  f"{b['amount']} -> {c['amount']}")
                break
    if mismatches:
        result.record("4. top_donors_values_match", False,
                      f"{len(mismatches)} mismatch(es); first 5:\n  "
                      + "\n  ".join(mismatches[:5]))
    else:
        result.record("4. top_donors_values_match", True,
                      f"info: all donor lists match to penny")


def check_v3_monetary_slice(baseline_summary: dict, v3_db: Path,
                            result: Layer1Result) -> None:
    if not v3_db.exists():
        result.record("5. v3_monetary_slice_match", True,
                      "info: v3 DB does not exist yet (pre-Phase 2); skipped")
        return
    con = sqlite3.connect(str(v3_db))
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM finance_summary_by_type"
        ).fetchone()
    except sqlite3.OperationalError:
        result.record("5. v3_monetary_slice_match", True,
                      "info: finance_summary_by_type missing; skipped "
                      "(pre-Phase 1 DDL)")
        con.close()
        return
    if row[0] == 0:
        result.record("5. v3_monetary_slice_match", True,
                      "info: finance_summary_by_type is empty; skipped "
                      "(pre-Phase 2 ingest)")
        con.close()
        return
    current = {}
    for r in con.execute(
        "SELECT finance_campaign_id, stance, total_amount, n_committees, "
        "top5_share, hhi "
        "FROM finance_summary_by_type "
        "WHERE receipt_type='monetary_contribution'"
    ):
        cid, stance, total, ncom, t5, hhi = r
        current[f"{cid}|{stance}"] = {
            "total_receipts": round(total, 2),
            "n_committees": ncom,
            "top5_share": round(t5, 4) if t5 is not None else None,
            "hhi": round(hhi, 4) if hhi is not None else None,
        }
    con.close()
    # Now compare against baseline_summary by penny
    mismatches = []
    for key, b in baseline_summary.items():
        c = current.get(key)
        if c is None:
            mismatches.append(f"{key} missing in v3 monetary slice")
            continue
        if abs(b["total_receipts"] - c["total_receipts"]) > PENNY:
            mismatches.append(f"{key} total: v2={b['total_receipts']} "
                              f"v3={c['total_receipts']}")
    if mismatches:
        result.record("5. v3_monetary_slice_match", False,
                      f"{len(mismatches)} mismatch(es); first 5:\n  "
                      + "\n  ".join(mismatches[:5]))
    else:
        result.record("5. v3_monetary_slice_match", True,
                      f"info: all {len(baseline_summary)} monetary rows "
                      f"in v3 match v2 baseline to the penny")


def check_campaign_count(baseline: dict, v2_summary: dict,
                         result: Layer1Result) -> None:
    expected = baseline.get("aggregate_totals", {}).get("campaign_count", -1)
    cids = set(k.split("|")[0] for k in v2_summary.keys())
    actual = len(cids)
    ok = (actual == expected)
    result.record("6. campaign_count_unchanged", ok,
                  f"baseline={expected} actual={actual}"
                  if not ok else f"info: {actual} campaigns")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--v2-db", default=str(DEFAULT_V2_DB))
    parser.add_argument("--v3-db", default=str(DEFAULT_V3_DB))
    args = parser.parse_args()

    result = Layer1Result()
    baseline_path = Path(args.baseline)
    v2_db = Path(args.v2_db)
    v3_db = Path(args.v3_db)

    baseline = verify_baseline_hash(baseline_path, result)
    if baseline is None:
        return result.report()

    current_summary = query_v2_summary(v2_db)
    compare_summary(baseline["finance_summary"], current_summary, result)

    current_donors = query_v2_top_donors(v2_db)
    compare_top_donors(baseline["finance_top_donors_top5"], current_donors,
                       result)

    check_v3_monetary_slice(baseline["finance_summary"], v3_db, result)
    check_campaign_count(baseline, current_summary, result)

    sys.exit(result.report())


if __name__ == "__main__":
    main()
