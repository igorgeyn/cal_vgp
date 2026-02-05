#!/usr/bin/env python3
"""
Comprehensive inspection of CAL-ACCESS ballot measure receipts data.

Reads: scraper/data/finance/calaccess_raw/ballot_measure_receipts.csv
Outputs: structured text report to stdout
"""

import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime, date
from pathlib import Path
import statistics

CSV_PATH = Path(__file__).parent.parent / "data" / "finance" / "calaccess_raw" / "ballot_measure_receipts.csv"

def parse_date(s):
    """Parse CAL-ACCESS date format: 'M/D/YYYY 12:00:00 AM' or 'M/D/YYYY'."""
    if not s or not s.strip():
        return None
    s = s.strip().split(" ")[0]  # drop time portion
    try:
        return datetime.strptime(s, "%m/%d/%Y").date()
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

def parse_amount(s):
    if not s or not s.strip():
        return None
    try:
        return float(s.strip())
    except ValueError:
        return None

def section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def main():
    print(f"CAL-ACCESS Ballot Measure Receipts — Inspection Report")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Source: {CSV_PATH}")

    # ── Load data ──
    rows = []
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        for row in reader:
            rows.append(row)

    N = len(rows)
    print(f"Total rows: {N:,}")
    print(f"Columns ({len(columns)}): {', '.join(columns)}")

    # ══════════════════════════════════════════════════════════════════════
    section("1. SCHEMA & COMPLETENESS")
    # ══════════════════════════════════════════════════════════════════════

    print(f"{'Column':<25} {'Non-null':>10} {'Non-empty':>10} {'% filled':>8}  Sample values")
    print("-" * 95)
    for col in columns:
        vals = [r[col] for r in rows]
        non_null = sum(1 for v in vals if v is not None)
        non_empty = sum(1 for v in vals if v and v.strip())
        pct = 100 * non_empty / N if N else 0
        # sample: up to 3 unique non-empty values
        unique_sample = []
        seen = set()
        for v in vals:
            if v and v.strip() and v.strip() not in seen and len(unique_sample) < 3:
                unique_sample.append(v.strip()[:40])
                seen.add(v.strip())
        print(f"{col:<25} {non_null:>10,} {non_empty:>10,} {pct:>7.1f}%  {'; '.join(unique_sample)}")

    # ══════════════════════════════════════════════════════════════════════
    section("2. DATE QUALITY")
    # ══════════════════════════════════════════════════════════════════════

    dates = []
    bad_dates = []
    empty_dates = 0
    today = date.today()
    future_dates = []

    for r in rows:
        raw = r.get("date", "")
        if not raw or not raw.strip():
            empty_dates += 1
            continue
        d = parse_date(raw)
        if d:
            dates.append(d)
            if d > today:
                future_dates.append((d, r))
        else:
            bad_dates.append(raw.strip())

    print(f"Parseable dates:  {len(dates):>10,}  ({100*len(dates)/N:.1f}%)")
    print(f"Empty dates:      {empty_dates:>10,}  ({100*empty_dates/N:.1f}%)")
    print(f"Unparseable:      {len(bad_dates):>10,}  ({100*len(bad_dates)/N:.1f}%)")
    if bad_dates:
        print(f"  Sample bad dates: {bad_dates[:5]}")
    if dates:
        print(f"Earliest: {min(dates)}")
        print(f"Latest:   {max(dates)}")
    print(f"Future dates (>{today}): {len(future_dates)}")
    if future_dates:
        for d, r in future_dates[:5]:
            print(f"  {d} | Prop {r['prop_num']} | {r['committee_name'][:40]} | ${r['amount']}")

    # Decade distribution
    decade_counts = Counter()
    for d in dates:
        decade_counts[f"{d.year // 10 * 10}s"] += 1
    print("\nDate distribution by decade:")
    for dec in sorted(decade_counts):
        print(f"  {dec}: {decade_counts[dec]:>10,}")

    # ══════════════════════════════════════════════════════════════════════
    section("3. AMOUNT QUALITY")
    # ══════════════════════════════════════════════════════════════════════

    amounts = []
    bad_amounts = []
    empty_amounts = 0

    for r in rows:
        raw = r.get("amount", "")
        if not raw or not raw.strip():
            empty_amounts += 1
            continue
        a = parse_amount(raw)
        if a is not None:
            amounts.append(a)
        else:
            bad_amounts.append(raw.strip())

    print(f"Parseable amounts: {len(amounts):>10,}  ({100*len(amounts)/N:.1f}%)")
    print(f"Empty amounts:     {empty_amounts:>10,}")
    print(f"Unparseable:       {len(bad_amounts):>10,}")
    if bad_amounts:
        print(f"  Sample: {bad_amounts[:5]}")

    neg = [a for a in amounts if a < 0]
    zero = [a for a in amounts if a == 0]
    pos = [a for a in amounts if a > 0]
    print(f"\nNegative: {len(neg):>10,}  total: ${sum(neg):>15,.2f}")
    print(f"Zero:     {len(zero):>10,}")
    print(f"Positive: {len(pos):>10,}  total: ${sum(pos):>15,.2f}")

    # Outliers
    over_1m = [(a, i) for i, a in enumerate(amounts) if abs(a) > 1_000_000]
    over_10m = [(a, i) for i, a in enumerate(amounts) if abs(a) > 10_000_000]
    print(f"\n|amount| > $1M:  {len(over_1m):,}")
    print(f"|amount| > $10M: {len(over_10m):,}")
    if over_10m:
        print("  Top 10 single receipts by |amount|:")
        # Need to re-scan with row context
        big = []
        for r in rows:
            a = parse_amount(r.get("amount", ""))
            if a is not None and abs(a) > 10_000_000:
                big.append((abs(a), a, r))
        big.sort(key=lambda x: x[0], reverse=True)
        for _, a, r in big[:10]:
            print(f"    ${a:>15,.0f} | Prop {r['prop_num']} | {r['stance']} | {r['donor_last'][:30]}, {r['donor_first'][:15]} | {r['committee_name'][:35]}")

    # Buckets
    buckets = {"$0-100": 0, "$100-1K": 0, "$1K-10K": 0, "$10K-100K": 0, "$100K-1M": 0, "$1M+": 0}
    bucket_totals = {"$0-100": 0, "$100-1K": 0, "$1K-10K": 0, "$10K-100K": 0, "$100K-1M": 0, "$1M+": 0}
    for a in amounts:
        aa = abs(a)
        if aa <= 100:
            k = "$0-100"
        elif aa <= 1000:
            k = "$100-1K"
        elif aa <= 10000:
            k = "$1K-10K"
        elif aa <= 100000:
            k = "$10K-100K"
        elif aa <= 1000000:
            k = "$100K-1M"
        else:
            k = "$1M+"
        buckets[k] += 1
        bucket_totals[k] += a

    print("\nContribution size distribution:")
    print(f"  {'Bucket':<15} {'Count':>10} {'% Count':>8} {'Total $':>18} {'% Total':>8}")
    total_amt = sum(amounts)
    for k in ["$0-100", "$100-1K", "$1K-10K", "$10K-100K", "$100K-1M", "$1M+"]:
        pct_n = 100 * buckets[k] / len(amounts) if amounts else 0
        pct_t = 100 * bucket_totals[k] / total_amt if total_amt else 0
        print(f"  {k:<15} {buckets[k]:>10,} {pct_n:>7.1f}% {bucket_totals[k]:>18,.0f} {pct_t:>7.1f}%")

    # ══════════════════════════════════════════════════════════════════════
    section("4. PROPOSITION COVERAGE")
    # ══════════════════════════════════════════════════════════════════════

    prop_data = defaultdict(lambda: {
        "n": 0, "total": 0, "support_total": 0, "oppose_total": 0,
        "support_n": 0, "oppose_n": 0, "dates": []
    })
    for r in rows:
        p = r["prop_num"]
        a = parse_amount(r.get("amount", "")) or 0
        d = parse_date(r.get("date", ""))
        prop_data[p]["n"] += 1
        prop_data[p]["total"] += a
        if r["stance"] == "support":
            prop_data[p]["support_total"] += a
            prop_data[p]["support_n"] += 1
        elif r["stance"] == "oppose":
            prop_data[p]["oppose_total"] += a
            prop_data[p]["oppose_n"] += 1
        if d:
            prop_data[p]["dates"].append(d)

    print(f"Distinct propositions: {len(prop_data)}")
    counts = [v["n"] for v in prop_data.values()]
    print(f"Receipts per prop — min: {min(counts):,}, median: {statistics.median(counts):,.0f}, max: {max(counts):,}")

    # Top 20 by total $
    print("\nTop 20 propositions by total $:")
    print(f"  {'Prop':<8} {'Total $':>15} {'Support $':>15} {'Oppose $':>15} {'Rcpts':>8} {'Date range':<25}")
    print("  " + "-" * 90)
    sorted_props = sorted(prop_data.items(), key=lambda x: x[1]["total"], reverse=True)
    for p, v in sorted_props[:20]:
        dr = ""
        if v["dates"]:
            dr = f"{min(v['dates'])} → {max(v['dates'])}"
        print(f"  {p:<8} {v['total']:>15,.0f} {v['support_total']:>15,.0f} {v['oppose_total']:>15,.0f} {v['n']:>8,} {dr:<25}")

    # Props with only one side
    support_only = [p for p, v in prop_data.items() if v["support_n"] > 0 and v["oppose_n"] == 0]
    oppose_only = [p for p, v in prop_data.items() if v["oppose_n"] > 0 and v["support_n"] == 0]
    neither = [p for p, v in prop_data.items() if v["support_n"] == 0 and v["oppose_n"] == 0]
    print(f"\nProps with ONLY support data: {len(support_only)}")
    if support_only:
        print(f"  {', '.join(sorted(support_only, key=lambda x: prop_data[x]['total'], reverse=True)[:20])}")
    print(f"Props with ONLY oppose data: {len(oppose_only)}")
    if oppose_only:
        print(f"  {', '.join(sorted(oppose_only, key=lambda x: prop_data[x]['total'], reverse=True)[:20])}")
    print(f"Props with neither: {len(neither)}")

    # ══════════════════════════════════════════════════════════════════════
    section("5. DONOR ANALYSIS")
    # ══════════════════════════════════════════════════════════════════════

    # Entity type breakdown
    entity_counts = Counter()
    entity_totals = defaultdict(float)
    for r in rows:
        ec = r.get("entity_cd", "").strip() or "(empty)"
        entity_counts[ec] += 1
        a = parse_amount(r.get("amount", "")) or 0
        entity_totals[ec] += a

    print("Entity type breakdown:")
    print(f"  {'Type':<10} {'Count':>10} {'% Count':>8} {'Total $':>18} {'% Total':>8}")
    print("  " + "-" * 60)
    for ec, cnt in entity_counts.most_common():
        pct_n = 100 * cnt / N
        pct_t = 100 * entity_totals[ec] / total_amt if total_amt else 0
        print(f"  {ec:<10} {cnt:>10,} {pct_n:>7.1f}% {entity_totals[ec]:>18,.0f} {pct_t:>7.1f}%")

    # Top 20 donors by aggregate $
    donor_agg = defaultdict(float)
    for r in rows:
        name = r.get("donor_last", "").strip()
        if name:
            donor_agg[name] += parse_amount(r.get("amount", "")) or 0

    print("\nTop 20 donors by aggregate $ (by last name):")
    for name, total in sorted(donor_agg.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  ${total:>15,.0f}  {name[:60]}")

    # Employer/occupation fill rate by entity type
    print("\nEmployer/occupation fill rate by entity type:")
    entity_emp = defaultdict(lambda: {"total": 0, "has_emp": 0, "has_occ": 0})
    for r in rows:
        ec = r.get("entity_cd", "").strip() or "(empty)"
        entity_emp[ec]["total"] += 1
        if r.get("donor_employer", "").strip():
            entity_emp[ec]["has_emp"] += 1
        if r.get("donor_occupation", "").strip():
            entity_emp[ec]["has_occ"] += 1
    print(f"  {'Type':<10} {'Total':>10} {'Has employer':>12} {'%':>6} {'Has occupation':>14} {'%':>6}")
    for ec in sorted(entity_emp, key=lambda x: entity_emp[x]["total"], reverse=True):
        d = entity_emp[ec]
        pe = 100 * d["has_emp"] / d["total"] if d["total"] else 0
        po = 100 * d["has_occ"] / d["total"] if d["total"] else 0
        print(f"  {ec:<10} {d['total']:>10,} {d['has_emp']:>12,} {pe:>5.1f}% {d['has_occ']:>14,} {po:>5.1f}%")

    # Geographic: top states, top CA cities
    state_totals = defaultdict(float)
    ca_city_totals = defaultdict(float)
    for r in rows:
        st = r.get("donor_state", "").strip().upper()
        if st:
            state_totals[st] += parse_amount(r.get("amount", "")) or 0
        if st == "CA":
            city = r.get("donor_city", "").strip().upper()
            if city:
                ca_city_totals[city] += parse_amount(r.get("amount", "")) or 0

    print("\nTop 10 states by total $:")
    for st, total in sorted(state_totals.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {st:<5} ${total:>15,.0f}")

    print("\nTop 10 CA cities by total $:")
    for city, total in sorted(ca_city_totals.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {city:<25} ${total:>15,.0f}")

    # ══════════════════════════════════════════════════════════════════════
    section("6. COMMITTEE ANALYSIS")
    # ══════════════════════════════════════════════════════════════════════

    committees = set()
    cmte_props = defaultdict(set)  # committee -> set of props
    prop_cmtes_support = defaultdict(set)
    prop_cmtes_oppose = defaultdict(set)

    for r in rows:
        cname = r.get("committee_name", "").strip()
        if cname:
            committees.add(cname)
            cmte_props[cname].add(r["prop_num"])
            if r["stance"] == "support":
                prop_cmtes_support[r["prop_num"]].add(cname)
            elif r["stance"] == "oppose":
                prop_cmtes_oppose[r["prop_num"]].add(cname)

    print(f"Total unique committees: {len(committees):,}")
    cmtes_per_prop = [len(prop_cmtes_support.get(p, set()) | prop_cmtes_oppose.get(p, set())) for p in prop_data]
    print(f"Committees per prop — min: {min(cmtes_per_prop)}, median: {statistics.median(cmtes_per_prop):.0f}, max: {max(cmtes_per_prop)}")

    # Multi-prop committees
    multi = {c: ps for c, ps in cmte_props.items() if len(ps) > 1}
    print(f"\nCommittees appearing on multiple props: {len(multi)}")
    if multi:
        for c, ps in sorted(multi.items(), key=lambda x: len(x[1]), reverse=True)[:15]:
            print(f"  {c[:55]:<55} → props: {', '.join(sorted(ps))}")

    # Support vs oppose committee counts per prop (top 20 by total)
    print("\nSupport vs oppose committees (top 20 props by $):")
    print(f"  {'Prop':<8} {'Support cmtes':>14} {'Oppose cmtes':>14}")
    for p, v in sorted_props[:20]:
        ns = len(prop_cmtes_support.get(p, set()))
        no = len(prop_cmtes_oppose.get(p, set()))
        print(f"  {p:<8} {ns:>14} {no:>14}")

    # ══════════════════════════════════════════════════════════════════════
    section("7. DUPLICATE / ANOMALY DETECTION")
    # ══════════════════════════════════════════════════════════════════════

    # Exact duplicates
    row_tuples = Counter()
    for r in rows:
        t = tuple(r[c] for c in columns)
        row_tuples[t] += 1
    exact_dups = sum(v - 1 for v in row_tuples.values() if v > 1)
    dup_groups = sum(1 for v in row_tuples.values() if v > 1)
    print(f"Exact duplicate rows: {exact_dups:,} (in {dup_groups:,} groups)")

    # Near-duplicates: same donor_last + committee + amount + date
    near_key = Counter()
    for r in rows:
        k = (r.get("donor_last", ""), r.get("committee_name", ""), r.get("amount", ""), r.get("date", ""))
        near_key[k] += 1
    near_dups = sum(v - 1 for v in near_key.values() if v > 1)
    near_groups = sum(1 for v in near_key.values() if v > 1)
    print(f"Near-duplicate rows (donor+cmte+amt+date): {near_dups:,} (in {near_groups:,} groups)")
    if near_groups:
        print("  Top 10 near-dup groups:")
        for k, cnt in near_key.most_common(10):
            print(f"    x{cnt}: {k[0][:25]} | {k[1][:30]} | ${k[2]} | {k[3][:20]}")

    # Zero amounts
    zero_count = sum(1 for r in rows if parse_amount(r.get("amount", "")) == 0)
    print(f"\nZero-amount receipts: {zero_count:,}")

    # Stance anomalies
    stance_counts = Counter(r.get("stance", "") for r in rows)
    print(f"\nStance value distribution:")
    for s, c in stance_counts.most_common():
        print(f"  '{s}': {c:,}")

    # Form type distribution
    form_counts = Counter(r.get("form_type", "").strip() for r in rows)
    print(f"\nForm type distribution:")
    for ft, c in form_counts.most_common():
        print(f"  '{ft}': {c:,}")

    print(f"\n{'='*80}")
    print("  END OF REPORT")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
