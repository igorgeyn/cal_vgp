"""Schedule C diagnostic v2: with the resolver chain enabled.

Compares cover-sheet-only attribution (Phase 0 baseline) vs. the
full resolver chain (cover_sheet -> filer_name_explicit ->
manual_override). Shows bucket movements, so we can quantify what
the resolver actually recovers before locking Phase 3 ingest design.

Codex round-9: also produces a categorized table separating
filer_name_no_prop into known_unattributed_vehicles (curated
registry hits) vs. heuristically-identified candidate / party /
recall committees vs. truly unclassified.

Writes data/CalAccess/schedule_c_diagnostic_v2.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
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


# Codex round-9: classifiers for the unattributed bucket so the
# diagnostic can separate genuinely-OOS political activity from
# unresolved ballot-adjacent activity. Heuristic-only — for high-
# confidence cases, curate in known_unattributed_vehicles.json.

_CANDIDATE_REGEX = re.compile(
    r"\b(for\s+(assembly|senate|congress|governor|mayor|sheriff|"
    r"attorney\s+general|treasurer|controller|state\s+senate|"
    r"lieutenant\s+governor|secretary\s+of\s+state|supervisor))\b",
    re.IGNORECASE,
)
_PARTY_KEYWORDS = re.compile(
    r"\b(democratic\s+(state\s+)?central\s+committee|"
    r"california\s+democratic\s+party|"
    r"california\s+republican\s+party|"
    r"republican\s+state\s+central\s+committee)\b",
    re.IGNORECASE,
)
_RECALL_KEYWORDS = re.compile(
    r"\b(recall(\s+(governor|gavin|newsom|the))?|patriot\s+coalition|"
    r"stop\s+the\s+(republican\s+)?recall)\b",
    re.IGNORECASE,
)


def classify_unattributed(filer_name: str,
                          filer_id: str,
                          unattributed_registry: dict) -> str:
    """Heuristic + curated-registry classifier for filer_name_no_prop
    rows. Returns one of:
        curated_unresolved | recall_committee | candidate_committee |
        party_committee | unclassified
    """
    # Curated registry hits win (explicit > heuristic)
    if filer_id and filer_id in unattributed_registry:
        return "curated_unresolved"
    normalized = " ".join((filer_name or "").split()).lower()
    if normalized in unattributed_registry:
        return "curated_unresolved"
    name = filer_name or ""
    if _RECALL_KEYWORDS.search(name):
        return "recall_committee"
    if _PARTY_KEYWORDS.search(name):
        return "party_committee"
    if _CANDIDATE_REGEX.search(name):
        return "candidate_committee"
    return "unclassified"


def _load_unattributed_registry(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Strip _schema and other _-prefixed keys
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def diagnose(dump_dir: Path, v2_db: Path,
             manual_overrides_path: Path | None = None,
             unattributed_registry_path: Path | None = None,
             *, verbose: bool = True) -> dict:
    idx = build_filing_attribution_index(
        dump_dir, v2_db,
        manual_overrides_path=manual_overrides_path,
        verbose=verbose,
    )
    unattributed_registry = _load_unattributed_registry(
        unattributed_registry_path
    )
    if verbose and unattributed_registry:
        print(f"Loaded {len(unattributed_registry)} curated unattributed "
              "vehicle entries.")

    rcpt_path = dump_dir / "RCPT_CD.TSV"
    if not rcpt_path.exists():
        raise SystemExit(f"Missing source: {rcpt_path}")

    # Pass 1: latest amend per FILING_ID for RCPT_CD
    if verbose:
        print()
        print(f"Pass 1: latest-amend dedup over RCPT_CD "
              f"({rcpt_path.stat().st_size / 1e9:.1f}GB)...")
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

    if verbose:
        print(f"  Unique FILING_IDs in RCPT_CD: {len(latest_amend):,}")
        print()
        print(f"Pass 2: classify Schedule C rows by attribution method...")

    by_method: Counter[str] = Counter()
    dollars_by_method: Counter[str] = Counter()
    quarantine_dollars: Counter[str] = Counter()
    top_filers_by_method: dict[str, Counter[str]] = defaultdict(Counter)
    top_filers_quarantine: dict[str, Counter[str]] = defaultdict(Counter)
    # Categorized split of the filer_name_no_prop bucket per Codex
    # round-9: separates genuinely OOS political activity from
    # unresolved ballot-adjacent.
    no_prop_categories: Counter[str] = Counter()
    no_prop_dollars: Counter[str] = Counter()

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

            att = idx.get(fid)
            if att is None:
                method = "no_cover_sheet"
                filer_label = "(no cover sheet)"
            elif att.finance_campaign_id and att.stance:
                method = att.attribution_method
                filer_label = att.cover_filer_name or "(no filer name)"
            else:
                method = f"failed/{att.quarantine_reason or 'unknown'}"
                filer_label = att.cover_filer_name or "(no filer name)"

            by_method[method] += 1
            dollars_by_method[method] += amount
            if method.startswith("failed/") or method == "no_cover_sheet":
                quarantine_dollars[method] += amount
                top_filers_quarantine[method][filer_label] += amount
                # Subclassify filer_name_no_prop into curated /
                # heuristic OOS categories
                if method == "failed/filer_name_no_prop":
                    filer_id = att.cover_filer_id if att else ""
                    category = classify_unattributed(
                        filer_label, filer_id, unattributed_registry
                    )
                    no_prop_categories[category] += 1
                    no_prop_dollars[category] += amount
            else:
                top_filers_by_method[method][filer_label] += amount

    return {
        "by_method": dict(by_method),
        "dollars_by_method": dict(dollars_by_method),
        "top_filers_by_method": {
            k: v.most_common(25) for k, v in top_filers_by_method.items()
        },
        "top_filers_quarantine": {
            k: v.most_common(25) for k, v in top_filers_quarantine.items()
        },
        "no_prop_categories": dict(no_prop_categories),
        "no_prop_dollars": dict(no_prop_dollars),
    }


def render_report(stats: dict, report_path: Path, verbose: bool = True) -> None:
    accepted_methods = {"cover_sheet", "filer_name_explicit",
                         "manual_override"}
    accepted_dollars = sum(
        v for k, v in stats["dollars_by_method"].items()
        if k in accepted_methods
    )

    lines = ["# Schedule C diagnostic v2 (resolver chain enabled)", ""]
    lines.append(f"Run 2026-05-13. Resolver chain: cover_sheet -> "
                 f"filer_name_explicit -> manual_override.")
    lines.append("")
    lines.append("## Bucket totals — by attribution method")
    lines.append("")
    lines.append("| Method | Rows | Dollars |")
    lines.append("|---|---|---|")
    for method in sorted(stats["by_method"].keys(),
                          key=lambda k: stats["dollars_by_method"].get(k, 0),
                          reverse=True):
        rows = stats["by_method"][method]
        dollars = stats["dollars_by_method"].get(method, 0.0)
        lines.append(f"| `{method}` | {rows:,} | ${dollars:,.2f} |")
    lines.append("")
    lines.append(f"**Total accepted (cover_sheet + filer_name_explicit + "
                 f"manual_override): ${accepted_dollars:,.2f}**")
    lines.append("")

    # Codex round-9: categorized honest-attribution table for the
    # filer_name_no_prop residual
    if stats.get("no_prop_categories"):
        lines.append("## filer_name_no_prop subcategorization "
                     "(Codex round-9)")
        lines.append("")
        lines.append("| Category | Rows | Dollars |")
        lines.append("|---|---|---|")
        order = [
            "curated_unresolved", "recall_committee",
            "party_committee", "candidate_committee", "unclassified",
        ]
        for cat in order:
            rows = stats["no_prop_categories"].get(cat, 0)
            dollars = stats["no_prop_dollars"].get(cat, 0.0)
            if rows or dollars:
                lines.append(f"| `{cat}` | {rows:,} | ${dollars:,.2f} |")
        lines.append("")
        lines.append("- `curated_unresolved`: matched the curated "
                     "known_unattributed_vehicles.json registry "
                     "(ballot-adjacent but not safely attributable)")
        lines.append("- `recall_committee`, `party_committee`, "
                     "`candidate_committee`: heuristic keyword match — "
                     "out-of-scope for v3 measure attribution")
        lines.append("- `unclassified`: remaining no-prop activity — "
                     "where to look first for additional curation")
        lines.append("")

    # Compare against v1 baseline
    lines.append("## Comparison vs v1 diagnostic (cover_sheet only)")
    lines.append("")
    lines.append("v1 baseline buckets (data/CalAccess/schedule_c_diagnostic.md):")
    lines.append("- accepted: $242.6M")
    lines.append("- no_cover_sheet: $434.7M")
    lines.append("- bad_prop_or_year: $208.5M")
    lines.append("- no_campaign_match: $8.2M")
    lines.append("- unknown_stance: $0.6M")
    lines.append("")

    lines.append("## Top filers per attribution method (top 25 each)")
    lines.append("")
    for method in ["cover_sheet", "filer_name_explicit", "manual_override"]:
        rows = stats["top_filers_by_method"].get(method, [])
        if not rows:
            continue
        lines.append(f"### `{method}`")
        lines.append("")
        lines.append("| Filer | Dollars |")
        lines.append("|---|---|")
        for filer, amt in rows:
            f_disp = (filer or "(empty)")[:80].replace("|", "\\|")
            lines.append(f"| {f_disp} | ${amt:,.2f} |")
        lines.append("")

    lines.append("## Top quarantined filers per reason (top 25 each)")
    lines.append("")
    for method in sorted(stats["top_filers_quarantine"].keys()):
        rows = stats["top_filers_quarantine"].get(method, [])
        if not rows:
            continue
        lines.append(f"### `{method}`")
        lines.append("")
        lines.append("| Filer | Dollars |")
        lines.append("|---|---|")
        for filer, amt in rows:
            f_disp = (filer or "(empty)")[:80].replace("|", "\\|")
            lines.append(f"| {f_disp} | ${amt:,.2f} |")
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    if verbose:
        print(f"Report written to {report_path}")
        print()
        print(f"=== Headline ===")
        print(f"  Accepted via resolver chain: ${accepted_dollars:,.2f}")
        print(f"  (v1 cover-sheet only baseline: $242,550,215.67)")
        print(f"  Delta: ${accepted_dollars - 242_550_215.67:+,.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-dir", default=str(lib.DUMP_DIR))
    parser.add_argument("--v2-db", default=str(lib.V2_DB))
    parser.add_argument("--manual-overrides",
                        default=str(Path("data/CalAccess/"
                                         "manual_attribution_overrides.json")))
    parser.add_argument("--unattributed-registry",
                        default=str(Path("data/CalAccess/"
                                         "known_unattributed_vehicles.json")))
    parser.add_argument(
        "--report",
        default=str(Path("data/CalAccess/schedule_c_diagnostic_v2.md")),
    )
    args = parser.parse_args()

    overrides = (Path(args.manual_overrides)
                 if args.manual_overrides and Path(args.manual_overrides).exists()
                 else None)
    registry = (Path(args.unattributed_registry)
                if args.unattributed_registry
                and Path(args.unattributed_registry).exists()
                else None)
    stats = diagnose(Path(args.dump_dir), Path(args.v2_db),
                     manual_overrides_path=overrides,
                     unattributed_registry_path=registry,
                     verbose=True)
    render_report(stats, Path(args.report), verbose=True)


if __name__ == "__main__":
    main()
