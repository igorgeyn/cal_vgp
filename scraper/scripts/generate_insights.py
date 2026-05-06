#!/usr/bin/env python3
"""
Precompute compact data for the CalBallot Insights view.

The public site already embeds the full measure list for browsing. This script
keeps the analysis section small and stable by storing only aggregate series,
rankings, and method notes needed for editorial dashboards.
"""
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH, DATA_DIR
from src.finance.schema import FINANCE_DB_PATH
from src.utils.category_type_mapping import get_display_category_type
from src.utils.regions import CA_REGIONS, get_region_for_county
from src.utils.topic_mapping import get_display_topic


OUTPUT_PATH = DATA_DIR / "insights.json"

CA_COUNTY_FIPS = {
    "Alameda": "06001",
    "Alpine": "06003",
    "Amador": "06005",
    "Butte": "06007",
    "Calaveras": "06009",
    "Colusa": "06011",
    "Contra Costa": "06013",
    "Del Norte": "06015",
    "El Dorado": "06017",
    "Fresno": "06019",
    "Glenn": "06021",
    "Humboldt": "06023",
    "Imperial": "06025",
    "Inyo": "06027",
    "Kern": "06029",
    "Kings": "06031",
    "Lake": "06033",
    "Lassen": "06035",
    "Los Angeles": "06037",
    "Madera": "06039",
    "Marin": "06041",
    "Mariposa": "06043",
    "Mendocino": "06045",
    "Merced": "06047",
    "Modoc": "06049",
    "Mono": "06051",
    "Monterey": "06053",
    "Napa": "06055",
    "Nevada": "06057",
    "Orange": "06059",
    "Placer": "06061",
    "Plumas": "06063",
    "Riverside": "06065",
    "Sacramento": "06067",
    "San Benito": "06069",
    "San Bernardino": "06071",
    "San Diego": "06073",
    "San Francisco": "06075",
    "San Joaquin": "06077",
    "San Luis Obispo": "06079",
    "San Mateo": "06081",
    "Santa Barbara": "06083",
    "Santa Clara": "06085",
    "Santa Cruz": "06087",
    "Shasta": "06089",
    "Sierra": "06091",
    "Siskiyou": "06093",
    "Solano": "06095",
    "Sonoma": "06097",
    "Stanislaus": "06099",
    "Sutter": "06101",
    "Tehama": "06103",
    "Trinity": "06105",
    "Tulare": "06107",
    "Tuolumne": "06109",
    "Ventura": "06111",
    "Yolo": "06113",
    "Yuba": "06115",
}

FISCAL_TYPES = {
    "Bond",
    "Business Tax",
    "Gann Limit",
    "Miscellaneous Tax",
    "Property Tax",
    "Sales Tax",
    "Transient Occupancy Tax",
    "Utility Tax",
}

THRESHOLD_VALUES = {
    "50%": 50.0,
    "55%": 55.0,
    "66.67%": 66.67,
}


def normalize_county(county):
    if not county:
        return "Statewide"
    county = str(county).strip().title()
    return {
        "San Bernadino": "San Bernardino",
        "Toulumne": "Tuolumne",
    }.get(county, county)


def normalize_percent(value):
    if value is None:
        return None
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return None
    if 0 < pct <= 1:
        pct *= 100
    if pct < 0 or pct > 100:
        return None
    return pct


def derive_threshold(row):
    raw = row.get("vote_threshold")
    if raw:
        return str(raw)
    code = str(row.get("pass_fail") or "")
    if code.endswith("F"):
        return "55%"
    if code.endswith("T"):
        return "66.67%"
    if row.get("passed") in (0, 1) or row.get("percent_yes") is not None:
        return "50%"
    return "Unknown"


def pct(numerator, denominator, digits=1):
    if not denominator:
        return None
    return round(100 * numerator / denominator, digits)


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def linear_regression(points):
    clean = [(float(x), float(y)) for x, y in points if x is not None and y is not None]
    n = len(clean)
    if n < 3:
        return None
    xs = [p[0] for p in clean]
    ys = [p[1] for p in clean]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    sxx = sum((x - x_mean) ** 2 for x in xs)
    if not sxx:
        return None
    sxy = sum((x - x_mean) * (y - y_mean) for x, y in clean)
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    fitted = [intercept + slope * x for x in xs]
    sst = sum((y - y_mean) ** 2 for y in ys)
    sse = sum((y - yhat) ** 2 for y, yhat in zip(ys, fitted))
    r2 = 1 - sse / sst if sst else None
    return {
        "n": n,
        "slope": round(slope, 3),
        "intercept": round(intercept, 3),
        "r2": round(r2, 3) if r2 is not None else None,
    }


def odds_ratio(a, b, c, d):
    """Return odds ratio and 95% CI for a/b versus c/d using a 0.5 correction."""
    aa, bb, cc, dd = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    estimate = (aa / bb) / (cc / dd)
    se = math.sqrt((1 / aa) + (1 / bb) + (1 / cc) + (1 / dd))
    lo = math.exp(math.log(estimate) - 1.96 * se)
    hi = math.exp(math.log(estimate) + 1.96 * se)
    return {
        "odds_ratio": round(estimate, 2),
        "ci_low": round(lo, 2),
        "ci_high": round(hi, 2),
    }


def election_cycle(year):
    if year is None:
        return "Unknown"
    year = int(year)
    if year % 4 == 0:
        return "Presidential year"
    if year % 4 == 2:
        return "Midterm year"
    return "Odd year"


def threshold_value(label):
    if not label:
        return None
    return THRESHOLD_VALUES.get(str(label))


def measure_excerpt(measure):
    return {
        "id": measure["id"],
        "measure_id": measure.get("measure_id"),
        "year": measure.get("year"),
        "county": measure.get("county"),
        "title": measure.get("title"),
        "percent_yes": round(measure["percent_yes"], 2) if measure.get("percent_yes") is not None else None,
        "passed": measure.get("passed"),
        "threshold": measure.get("threshold"),
    }


def load_measures(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, measure_id, measure_letter, year, county, title,
               ballot_question, summary_text, yes_votes, no_votes,
               total_votes, percent_yes, passed, pass_fail, vote_threshold,
               category_type, category_topic, topic_primary, data_source
        FROM active_measures
        WHERE is_active = 1 AND is_duplicate = 0
        """
    ).fetchall()
    conn.close()

    measures = []
    for row in rows:
        item = dict(row)
        item["county"] = normalize_county(item.get("county"))
        item["percent_yes"] = normalize_percent(item.get("percent_yes"))
        item["display_topic"] = get_display_topic(
            item.get("topic_primary") or item.get("category_topic")
        )
        item["display_category_type"] = get_display_category_type(
            item.get("category_type")
        )
        item["threshold"] = derive_threshold(item)
        item["decade"] = (int(item["year"]) // 10) * 10 if item.get("year") else None
        measures.append(item)
    return measures


def summarize_overview(measures):
    active = len(measures)
    decided = [m for m in measures if m.get("passed") in (0, 1)]
    vote_data = [m for m in measures if m.get("yes_votes") is not None and m.get("no_votes") is not None]
    summaries = [m for m in measures if m.get("summary_text")]
    counties = sorted({m["county"] for m in measures if m["county"] != "Statewide"})
    years = [int(m["year"]) for m in measures if m.get("year")]
    passed = sum(1 for m in decided if m["passed"] == 1)
    local = sum(1 for m in measures if m["county"] != "Statewide")
    statewide = active - local

    return {
        "active_measures": active,
        "decided_measures": len(decided),
        "vote_data_measures": len(vote_data),
        "summary_measures": len(summaries),
        "pass_rate": pct(passed, len(decided)),
        "passed": passed,
        "failed": len(decided) - passed,
        "local_measures": local,
        "statewide_measures": statewide,
        "local_share": pct(local, active),
        "county_count": len(counties),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_time_series(measures):
    by_year = defaultdict(lambda: {
        "year": None,
        "total": 0,
        "passed": 0,
        "failed": 0,
        "decided": 0,
        "local": 0,
        "statewide": 0,
        "fiscal": 0,
        "yes_values": [],
    })
    for m in measures:
        year = m.get("year")
        if year is None:
            continue
        bucket = by_year[int(year)]
        bucket["year"] = int(year)
        bucket["total"] += 1
        if m.get("county") == "Statewide":
            bucket["statewide"] += 1
        else:
            bucket["local"] += 1
        if m.get("display_category_type") in FISCAL_TYPES:
            bucket["fiscal"] += 1
        if m.get("passed") in (0, 1):
            bucket["decided"] += 1
            if m["passed"] == 1:
                bucket["passed"] += 1
            else:
                bucket["failed"] += 1
        if m.get("percent_yes") is not None:
            bucket["yes_values"].append(m["percent_yes"])

    result = []
    for year in sorted(by_year):
        item = by_year[year]
        item["pass_rate"] = pct(item["passed"], item["decided"])
        item["local_share"] = pct(item["local"], item["total"])
        item["fiscal_share"] = pct(item["fiscal"], item["total"])
        yes_values = item.pop("yes_values")
        item["avg_yes"] = round(mean(yes_values), 1) if yes_values else None
        result.append(item)
    return result


def build_topic_stats(measures):
    buckets = defaultdict(lambda: {"topic": None, "total": 0, "decided": 0, "passed": 0})
    for m in measures:
        topic = m.get("display_topic") or "Other"
        bucket = buckets[topic]
        bucket["topic"] = topic
        bucket["total"] += 1
        if m.get("passed") in (0, 1):
            bucket["decided"] += 1
            bucket["passed"] += 1 if m["passed"] == 1 else 0

    result = []
    for item in buckets.values():
        item["pass_rate"] = pct(item["passed"], item["decided"])
        result.append(item)
    return sorted(result, key=lambda x: x["total"], reverse=True)


def build_topic_decade_matrix(measures):
    matrix = defaultdict(lambda: defaultdict(int))
    for m in measures:
        if not m.get("decade"):
            continue
        matrix[str(m["decade"])][m.get("display_topic") or "Other"] += 1
    return [
        {"decade": decade, "topics": dict(sorted(topics.items()))}
        for decade, topics in sorted(matrix.items(), key=lambda x: int(x[0]))
    ]


def build_decade_series(measures):
    buckets = defaultdict(lambda: {
        "decade": None,
        "total": 0,
        "local": 0,
        "statewide": 0,
        "fiscal": 0,
        "decided": 0,
        "passed": 0,
    })
    for m in measures:
        if not m.get("decade"):
            continue
        bucket = buckets[int(m["decade"])]
        bucket["decade"] = int(m["decade"])
        bucket["total"] += 1
        if m.get("county") == "Statewide":
            bucket["statewide"] += 1
        else:
            bucket["local"] += 1
        if m.get("display_category_type") in FISCAL_TYPES:
            bucket["fiscal"] += 1
        if m.get("passed") in (0, 1):
            bucket["decided"] += 1
            bucket["passed"] += 1 if m["passed"] == 1 else 0

    result = []
    for decade in sorted(buckets):
        item = buckets[decade]
        item["pass_rate"] = pct(item["passed"], item["decided"])
        item["local_share"] = pct(item["local"], item["total"])
        item["fiscal_share"] = pct(item["fiscal"], item["total"])
        result.append(item)
    return result


def build_election_cycle_stats(measures):
    order = {"Presidential year": 0, "Midterm year": 1, "Odd year": 2}
    buckets = defaultdict(lambda: {
        "cycle": None,
        "total": 0,
        "local": 0,
        "statewide": 0,
        "decided": 0,
        "passed": 0,
        "years": set(),
    })
    for m in measures:
        cycle = election_cycle(m.get("year"))
        bucket = buckets[cycle]
        bucket["cycle"] = cycle
        bucket["total"] += 1
        if m.get("year") is not None:
            bucket["years"].add(int(m["year"]))
        if m.get("county") == "Statewide":
            bucket["statewide"] += 1
        else:
            bucket["local"] += 1
        if m.get("passed") in (0, 1):
            bucket["decided"] += 1
            bucket["passed"] += 1 if m["passed"] == 1 else 0

    result = []
    for item in buckets.values():
        year_count = len(item["years"])
        item["year_count"] = year_count
        item["avg_measures_per_year"] = round(item["total"] / year_count, 1) if year_count else None
        item["pass_rate"] = pct(item["passed"], item["decided"])
        item["local_share"] = pct(item["local"], item["total"])
        item.pop("years")
        result.append(item)
    return sorted(result, key=lambda x: order.get(x["cycle"], 9))


def build_trend_insights(time_series, decade_series, election_cycle_stats):
    complete_recent_decades = [row for row in decade_series if row["decade"] < 2020 and row["total"] > 0]
    busiest_decade = max(complete_recent_decades, key=lambda x: x["total"]) if complete_recent_decades else None
    busiest_years = sorted(time_series, key=lambda x: x["total"], reverse=True)[:8]
    total_trend = linear_regression((row["year"], row["total"]) for row in time_series)
    pass_trend = linear_regression(
        (row["year"], row["pass_rate"]) for row in time_series if row.get("decided", 0) >= 10
    )
    recent_rows = [row for row in time_series if row["year"] >= 2000 and row.get("decided", 0) >= 10]
    recent_pass_trend = linear_regression((row["year"], row["pass_rate"]) for row in recent_rows)

    return {
        "busiest_decade": busiest_decade,
        "busiest_years": busiest_years,
        "annual_volume_trend": total_trend,
        "annual_pass_rate_trend": pass_trend,
        "recent_pass_rate_trend": recent_pass_trend,
        "election_cycle_stats": election_cycle_stats,
        "note": "Trend lines are descriptive OLS fits over available records, not causal or coverage-adjusted estimates.",
    }


def build_topic_trends(measures, topic_stats):
    top_topics = [
        row["topic"] for row in topic_stats
        if row.get("topic") and row["topic"] != "Other"
    ][:6]
    by_decade = defaultdict(lambda: {"decade": None, "total": 0, "topics": defaultdict(int)})
    for m in measures:
        if not m.get("decade"):
            continue
        topic = m.get("display_topic") or "Other"
        bucket = by_decade[int(m["decade"])]
        bucket["decade"] = int(m["decade"])
        bucket["total"] += 1
        if topic in top_topics:
            bucket["topics"][topic] += 1

    decade_rows = []
    for decade in sorted(by_decade):
        bucket = by_decade[decade]
        shares = {
            topic: pct(bucket["topics"].get(topic, 0), bucket["total"])
            for topic in top_topics
        }
        decade_rows.append({"decade": decade, "total": bucket["total"], "shares": shares})

    slopes = []
    for topic in top_topics:
        points = [(row["decade"], row["shares"].get(topic)) for row in decade_rows if row["total"] >= 100]
        fit = linear_regression(points)
        if fit:
            slopes.append({"topic": topic, **fit})

    return {
        "tracked_topics": top_topics,
        "decade_shares": decade_rows,
        "share_trends": sorted(slopes, key=lambda x: abs(x["slope"]), reverse=True),
        "note": "Topic trends exclude Other because sparse local topic text makes it a coverage artifact.",
    }


def build_topic_insights(measures, topic_stats, topic_decade_matrix):
    """
    Surfaces the chart-adjacent topic findings used by the Topics panel:
      - era_anchors: 4 era cards (1910s, 1980s, 2010s, 2020s) with the top 2
        topic shares each, computed against the classified-only denominator
        (matches the on-page chart's renormalization).
      - pass_rate_rankings: high/low topic pass rates, with min n=75 to
        suppress small classified buckets.
    """
    # Era anchors
    era_decades = [1910, 1980, 2010, 2020]
    matrix_lookup = {str(row["decade"]): row.get("topics") or {} for row in topic_decade_matrix}
    era_anchors = []
    for decade in era_decades:
        counts = matrix_lookup.get(str(decade), {})
        classified = {t: n for t, n in counts.items() if t != "Other" and (n or 0) > 0}
        total = sum(classified.values())
        if total == 0:
            era_anchors.append({"decade": decade, "classified_n": 0, "top": []})
            continue
        sorted_topics = sorted(classified.items(), key=lambda x: -x[1])[:2]
        top = [
            {"topic": t, "count": n, "share": round(100 * n / total, 1)}
            for t, n in sorted_topics
        ]
        era_anchors.append({"decade": decade, "classified_n": total, "top": top})

    # Pass rate rankings (n>=75 decided)
    MIN_DECIDED = 75
    eligible = [
        t for t in topic_stats
        if t.get("topic")
        and t["topic"] != "Other"
        and (t.get("decided") or 0) >= MIN_DECIDED
    ]
    by_rate_desc = sorted(eligible, key=lambda x: -(x.get("pass_rate") or 0))
    high = by_rate_desc[:3]
    low = sorted(eligible, key=lambda x: x.get("pass_rate") or 0)[:4]

    return {
        "era_anchors": era_anchors,
        "pass_rate_rankings": {
            "min_decided": MIN_DECIDED,
            "high": [{"topic": t["topic"], "pass_rate": t.get("pass_rate"), "decided": t.get("decided")} for t in high],
            "low": [{"topic": t["topic"], "pass_rate": t.get("pass_rate"), "decided": t.get("decided")} for t in low],
        },
        "note": "Era anchors and pass-rate rankings use the topic-classified subset (Other is excluded). Local CEDA records are better analyzed by measure type.",
    }


def build_type_trends(measures):
    by_decade = defaultdict(lambda: {"decade": None, "total": 0, "fiscal": 0, "bond": 0, "tax": 0})
    tax_types = FISCAL_TYPES - {"Bond", "Gann Limit"}
    for m in measures:
        if not m.get("decade"):
            continue
        measure_type = m.get("display_category_type")
        bucket = by_decade[int(m["decade"])]
        bucket["decade"] = int(m["decade"])
        bucket["total"] += 1
        if measure_type in FISCAL_TYPES:
            bucket["fiscal"] += 1
        if measure_type == "Bond":
            bucket["bond"] += 1
        if measure_type in tax_types:
            bucket["tax"] += 1

    result = []
    for decade in sorted(by_decade):
        item = by_decade[decade]
        item["fiscal_share"] = pct(item["fiscal"], item["total"])
        item["bond_share"] = pct(item["bond"], item["total"])
        item["tax_share"] = pct(item["tax"], item["total"])
        result.append(item)
    return result


def build_statistical_comparisons(measures):
    decided = [m for m in measures if m.get("passed") in (0, 1)]

    def pass_fail(rows):
        passed = sum(1 for row in rows if row["passed"] == 1)
        failed = sum(1 for row in rows if row["passed"] == 0)
        return passed, failed

    simple = [m for m in decided if m.get("threshold") == "50%"]
    fiscal = [m for m in decided if m.get("display_category_type") in FISCAL_TYPES]
    non_fiscal = [m for m in decided if m.get("display_category_type") not in FISCAL_TYPES]
    fiscal_passed, fiscal_failed = pass_fail(fiscal)
    non_fiscal_passed, non_fiscal_failed = pass_fail(non_fiscal)

    threshold_rows = []
    simple_passed, simple_failed = pass_fail(simple)
    for label in ["55%", "66.67%"]:
        rows = [m for m in decided if m.get("threshold") == label]
        passed, failed = pass_fail(rows)
        comparison = odds_ratio(passed, failed, simple_passed, simple_failed) if rows and simple else None
        threshold_rows.append({
            "threshold": label,
            "decided": len(rows),
            "pass_rate": pct(passed, len(rows)),
            "reference": "50%",
            **(comparison or {}),
        })

    fiscal_comparison = odds_ratio(fiscal_passed, fiscal_failed, non_fiscal_passed, non_fiscal_failed)
    return {
        "threshold_vs_simple_majority": threshold_rows,
        "fiscal_vs_non_fiscal": {
            "fiscal_decided": len(fiscal),
            "fiscal_pass_rate": pct(fiscal_passed, len(fiscal)),
            "non_fiscal_decided": len(non_fiscal),
            "non_fiscal_pass_rate": pct(non_fiscal_passed, len(non_fiscal)),
            **fiscal_comparison,
        },
        "note": "Odds ratios are descriptive associations from decided records and do not control for jurisdiction, year, topic, turnout, or selection into threshold rules.",
    }


def build_threshold_stats(measures):
    buckets = defaultdict(lambda: {"threshold": None, "total": 0, "passed": 0, "majority_failed": 0})
    for m in measures:
        if m.get("passed") not in (0, 1):
            continue
        threshold = m.get("threshold") or "Unknown"
        bucket = buckets[threshold]
        bucket["threshold"] = threshold
        bucket["total"] += 1
        bucket["passed"] += 1 if m["passed"] == 1 else 0
        legal_threshold = threshold_value(threshold)
        if (
            m.get("percent_yes") is not None
            and legal_threshold is not None
            and legal_threshold > 50
            and 50 < m["percent_yes"] < legal_threshold
            and m["passed"] == 0
        ):
            bucket["majority_failed"] += 1

    order = {"50%": 0, "55%": 1, "66.67%": 2, "Unknown": 3}
    result = []
    for item in buckets.values():
        item["pass_rate"] = pct(item["passed"], item["total"])
        result.append(item)
    return sorted(result, key=lambda x: order.get(x["threshold"], 9))


def build_margin_stats(measures):
    with_pct = [m for m in measures if m.get("percent_yes") is not None and m.get("passed") in (0, 1)]
    bins = [
        ("under_1", 0, 1),
        ("under_3", 0, 3),
        ("under_5", 0, 5),
        ("under_10", 0, 10),
    ]
    counts = {}
    for key, lo, hi in bins:
        counts[key] = sum(1 for m in with_pct if lo <= abs(m["percent_yes"] - 50) < hi)

    closest = sorted(with_pct, key=lambda m: abs(m["percent_yes"] - 50))[:12]
    return {
        "measures_with_percent": len(with_pct),
        "close_counts": counts,
        "closest_measures": [
            {
                "id": m["id"],
                "year": m["year"],
                "county": m["county"],
                "title": m.get("title"),
                "measure_id": m.get("measure_id"),
                "percent_yes": round(m["percent_yes"], 2),
                "passed": m.get("passed"),
                "margin_from_50": round(abs(m["percent_yes"] - 50), 2),
            }
            for m in closest
        ],
    }


def build_county_stats(measures):
    buckets = defaultdict(lambda: {"county": None, "total": 0, "decided": 0, "passed": 0, "yes_values": []})
    for m in measures:
        county = m.get("county")
        if not county or county == "Statewide":
            continue
        bucket = buckets[county]
        bucket["county"] = county
        bucket["total"] += 1
        if m.get("passed") in (0, 1):
            bucket["decided"] += 1
            bucket["passed"] += 1 if m["passed"] == 1 else 0
        if m.get("percent_yes") is not None:
            bucket["yes_values"].append(m["percent_yes"])

    result = []
    for county, item in buckets.items():
        values = item.pop("yes_values")
        item["fips"] = CA_COUNTY_FIPS.get(county)
        item["region"] = get_region_for_county(county) or "Other"
        item["pass_rate"] = pct(item["passed"], item["decided"])
        item["avg_yes"] = round(sum(values) / len(values), 1) if values else None
        result.append(item)
    return sorted(result, key=lambda x: x["total"], reverse=True)


def build_region_stats(county_stats):
    regions = defaultdict(lambda: {"region": None, "total": 0, "decided": 0, "passed": 0, "counties": 0})
    for county in county_stats:
        region = county.get("region") or "Other"
        bucket = regions[region]
        bucket["region"] = region
        bucket["total"] += county["total"]
        bucket["decided"] += county["decided"]
        bucket["passed"] += county["passed"]
        bucket["counties"] += 1

    result = []
    for item in regions.values():
        item["pass_rate"] = pct(item["passed"], item["decided"])
        result.append(item)
    return sorted(result, key=lambda x: x["total"], reverse=True)


def build_category_type_stats(measures):
    buckets = defaultdict(lambda: {"category_type": None, "total": 0, "decided": 0, "passed": 0})
    for m in measures:
        category = m.get("display_category_type") or "Other"
        bucket = buckets[category]
        bucket["category_type"] = category
        bucket["total"] += 1
        if m.get("passed") in (0, 1):
            bucket["decided"] += 1
            bucket["passed"] += 1 if m["passed"] == 1 else 0
    result = []
    for item in buckets.values():
        item["pass_rate"] = pct(item["passed"], item["decided"])
        result.append(item)
    return sorted(result, key=lambda x: x["total"], reverse=True)


def build_type_insights(measures, category_type_stats, overview):
    """
    Powers the Measure Types panel below the two charts. Four narrative
    modules (Codex-recommended): modern-year anatomy, fiscal instrument
    profiles (with one-line typical-use copy), type x threshold profiles,
    and a recall callout. Plus a revised pass-rate ranking that excludes
    the Other / unclassified bucket.
    """
    MODERN_START = 1990
    modern_year_max = max(
        (int(m["year"]) for m in measures if m.get("year") and str(m["year"]).isdigit()),
        default=2026,
    )
    year_count = max(modern_year_max - MODERN_START + 1, 1)

    # Module 1: modern-year anatomy (records since 1990, divided by year count).
    modern = [m for m in measures if m.get("year") and int(m["year"]) >= MODERN_START]
    modern_by_type = defaultdict(int)
    for m in modern:
        ct = m.get("display_category_type")
        if ct and ct != "Other":
            modern_by_type[ct] += 1
    modern_instruments = sorted(
        [
            {
                "category_type": ct,
                "total_since_modern": total,
                "per_year_avg": round(total / year_count, 1),
            }
            for ct, total in modern_by_type.items()
        ],
        key=lambda x: -x["per_year_avg"],
    )[:6]

    # Module 2: fiscal instrument profiles (mini-table with typical use copy).
    INSTRUMENT_USE = {
        "Bond": "Borrowing for capital projects (schools, transit, infrastructure).",
        "Sales Tax": "Local sales-tax surcharges for transit, public safety, or general fund.",
        "Property Tax": "Parcel and property taxes, often for schools or special districts.",
        "Business Tax": "Payroll, gross-receipts, or industry-specific business taxes.",
        "Utility Tax": "Local levies on telecom, electricity, gas, or cable service.",
        "Transient Occupancy Tax": "Hotel and short-term rental taxes.",
    }
    fiscal_profiles = []
    for ct in ["Bond", "Sales Tax", "Property Tax", "Business Tax", "Utility Tax", "Transient Occupancy Tax"]:
        row = next((r for r in category_type_stats if r.get("category_type") == ct), None)
        if not row or (row.get("decided") or 0) < 50:
            continue
        fiscal_profiles.append({
            "category_type": ct,
            "total": row.get("total"),
            "decided": row.get("decided"),
            "pass_rate": row.get("pass_rate"),
            "typical_use": INSTRUMENT_USE.get(ct, ""),
        })

    # Module 3: type x threshold profiles for the most consequential fiscal instruments.
    TARGET_TYPES = ["Bond", "Property Tax", "Sales Tax"]
    type_threshold_profiles = []
    for ct in TARGET_TYPES:
        type_decided = [
            m for m in measures
            if m.get("display_category_type") == ct and m.get("passed") in (0, 1)
        ]
        if len(type_decided) < 50:
            continue
        threshold_count = defaultdict(int)
        majority_failed = 0
        for m in type_decided:
            t = m.get("threshold") or "Unknown"
            threshold_count[t] += 1
            legal = threshold_value(t)
            if (
                m.get("passed") == 0
                and m.get("percent_yes") is not None
                and m["percent_yes"] > 50
                and legal is not None
                and legal > 50
            ):
                majority_failed += 1
        total = len(type_decided)
        passed = sum(1 for m in type_decided if m["passed"] == 1)
        type_threshold_profiles.append({
            "category_type": ct,
            "decided": total,
            "pass_rate": pct(passed, total),
            "threshold_mix": {k: pct(v, total) for k, v in threshold_count.items()},
            "majority_failed": majority_failed,
        })

    # Module 4: recall profile.
    recalls = [m for m in measures if m.get("display_category_type") == "Recall"]
    decided_recalls = [m for m in recalls if m.get("passed") in (0, 1)]
    recall_passed = sum(1 for m in decided_recalls if m["passed"] == 1)
    recall_counties = {
        m.get("county") for m in recalls
        if m.get("county") and m["county"] != "Statewide"
    }
    year_counts = defaultdict(int)
    for m in recalls:
        if m.get("year") and str(m["year"]).isdigit():
            year_counts[int(m["year"])] += 1
    recall_avg = (sum(year_counts.values()) / len(year_counts)) if year_counts else 0
    spike_years = sorted(
        [
            {"year": y, "count": c}
            for y, c in year_counts.items()
            if c >= max(recall_avg * 2.5, 5)
        ],
        key=lambda x: -x["count"],
    )[:3]
    recall_profile = {
        "total": len(recalls),
        "decided": len(decided_recalls),
        "pass_rate": pct(recall_passed, len(decided_recalls)),
        "county_count": len(recall_counties),
        "spike_years": spike_years,
    }

    # Revised pass-rate rankings: exclude Other; n>=100 decided.
    eligible = [
        row for row in category_type_stats
        if (row.get("decided") or 0) >= 100
        and row.get("pass_rate") is not None
        and row.get("category_type") != "Other"
    ]

    return {
        "modern_year_anatomy": {
            "modern_start": MODERN_START,
            "modern_end": modern_year_max,
            "years_covered": year_count,
            "instruments": modern_instruments,
        },
        "fiscal_instrument_profiles": fiscal_profiles,
        "type_threshold_profiles": type_threshold_profiles,
        "recall_profile": recall_profile,
        "highest_pass_rate_types": sorted(eligible, key=lambda x: x["pass_rate"], reverse=True)[:3],
        "lowest_pass_rate_types": sorted(eligible, key=lambda x: x["pass_rate"])[:3],
        "minimum_decided_records": 100,
        "note": "Modern-year anatomy uses records since 1990, where local category_type is consistently populated. Threshold profiles connect to the Rules panel for the deep dive.",
    }


def build_threshold_insights(measures, threshold_stats):
    majority_failures = [
        m for m in measures
        if m.get("passed") == 0
        and m.get("percent_yes") is not None
        and m["percent_yes"] > 50
        and threshold_value(m.get("threshold")) is not None
        and threshold_value(m.get("threshold")) > 50
        and m["percent_yes"] < threshold_value(m.get("threshold"))
    ]
    legal_threshold_records = [
        m for m in measures
        if m.get("passed") in (0, 1)
        and m.get("percent_yes") is not None
        and threshold_value(m.get("threshold")) is not None
    ]
    closest_to_legal = sorted(
        legal_threshold_records,
        key=lambda m: abs(m["percent_yes"] - threshold_value(m.get("threshold"))),
    )[:10]

    # Hero subline: share of higher-threshold contests that ended in majority-backed failure.
    higher_threshold_decided = sum(
        row.get("total") or 0 for row in threshold_stats
        if row.get("threshold") in ("55%", "66.67%")
    )
    failure_share = pct(len(majority_failures), higher_threshold_decided)

    # Plain-English replacement for the odds-ratio block: percentage-point gaps vs simple-majority.
    by_label = {row.get("threshold"): row for row in threshold_stats}
    base_rate = (by_label.get("50%") or {}).get("pass_rate")
    threshold_pp_diffs = []
    for label in ("55%", "66.67%"):
        row = by_label.get(label) or {}
        rate = row.get("pass_rate")
        if base_rate is not None and rate is not None:
            threshold_pp_diffs.append({
                "threshold": label,
                "pass_rate": rate,
                "pp_vs_simple_majority": round(rate - base_rate, 1),
            })

    # Curated landmark near-misses for the Rules panel. We sort highest_yes_failures by yes %
    # descending and keep records that have a clean display_category_type so the cards aren't
    # forced to fall back on 150-word ballot questions.
    landmark_pool = sorted(
        majority_failures,
        key=lambda m: m.get("percent_yes") or 0,
        reverse=True,
    )
    seen_keys = set()
    landmark_near_misses = []
    for m in landmark_pool:
        ct = (m.get("display_category_type") or "").strip()
        if not ct or ct == "Other":
            continue
        # Avoid two cards from the same county+type+year cluster (visual diversity).
        key = (m.get("county"), ct, m.get("year"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        topic = (m.get("display_topic") or "").strip()
        landmark_near_misses.append({
            "id": m.get("id"),
            "measure_id": m.get("measure_id"),
            "year": m.get("year"),
            "county": m.get("county"),
            "category_type": ct,
            "topic": topic if topic and topic != "Other" else None,
            "percent_yes": round(m["percent_yes"], 2),
            "threshold": m.get("threshold"),
            "title": m.get("title"),
        })
        if len(landmark_near_misses) >= 4:
            break

    return {
        "majority_failure_count": len(majority_failures),
        "majority_failure_share_higher_thresholds": failure_share,
        "higher_threshold_decided": higher_threshold_decided,
        "threshold_pp_diffs": threshold_pp_diffs,
        "highest_yes_failures": [
            measure_excerpt(m) for m in sorted(majority_failures, key=lambda m: m["percent_yes"], reverse=True)[:8]
        ],
        "landmark_near_misses": landmark_near_misses,
        "closest_to_legal_threshold": [
            {
                **measure_excerpt(m),
                "legal_margin": round(m["percent_yes"] - threshold_value(m.get("threshold")), 2),
            }
            for m in closest_to_legal
        ],
        "by_threshold": threshold_stats,
    }


def build_geography_insights(county_stats, region_stats):
    county_eligible = [
        row for row in county_stats
        if row.get("decided", 0) >= 50 and row.get("pass_rate") is not None
    ]
    region_eligible = [
        row for row in region_stats
        if row.get("decided", 0) >= 50 and row.get("pass_rate") is not None
    ]
    highest_county = max(county_eligible, key=lambda x: x["pass_rate"]) if county_eligible else None
    lowest_county = min(county_eligible, key=lambda x: x["pass_rate"]) if county_eligible else None
    highest_region = max(region_eligible, key=lambda x: x["pass_rate"]) if region_eligible else None
    lowest_region = min(region_eligible, key=lambda x: x["pass_rate"]) if region_eligible else None

    return {
        "minimum_county_decided_records": 50,
        "highest_pass_rate_counties": sorted(county_eligible, key=lambda x: x["pass_rate"], reverse=True)[:5],
        "lowest_pass_rate_counties": sorted(county_eligible, key=lambda x: x["pass_rate"])[:5],
        "highest_pass_rate_regions": sorted(region_eligible, key=lambda x: x["pass_rate"], reverse=True)[:5],
        "lowest_pass_rate_regions": sorted(region_eligible, key=lambda x: x["pass_rate"])[:5],
        "county_pass_rate_gap": round(highest_county["pass_rate"] - lowest_county["pass_rate"], 1)
        if highest_county and lowest_county else None,
        "region_pass_rate_gap": round(highest_region["pass_rate"] - lowest_region["pass_rate"], 1)
        if highest_region and lowest_region else None,
    }


def build_close_call_insights(measures, margin_stats):
    with_pct = [
        m for m in measures
        if m.get("percent_yes") is not None and m.get("passed") in (0, 1)
    ]
    closest_passes = sorted(
        [m for m in with_pct if m.get("passed") == 1],
        key=lambda m: abs(m["percent_yes"] - 50),
    )[:8]
    closest_failures = sorted(
        [m for m in with_pct if m.get("passed") == 0],
        key=lambda m: abs(m["percent_yes"] - 50),
    )[:8]
    threshold_close = [
        m for m in with_pct
        if threshold_value(m.get("threshold")) is not None
    ]

    return {
        "counts": margin_stats.get("close_counts", {}),
        "closest_passes": [measure_excerpt(m) for m in closest_passes],
        "closest_failures": [measure_excerpt(m) for m in closest_failures],
        "closest_to_legal_threshold": [
            {
                **measure_excerpt(m),
                "legal_margin": round(m["percent_yes"] - threshold_value(m.get("threshold")), 2),
            }
            for m in sorted(
                threshold_close,
                key=lambda m: abs(m["percent_yes"] - threshold_value(m.get("threshold"))),
            )[:10]
        ],
    }


def build_finance_insights(measures_by_db_id):
    """Build cross-campaign finance aggregates from the v2 finance DB.

    Each campaign is a (prop_num, election_year) pair; measure metadata is
    looked up by `measure_db_id` (FK in finance_campaign). The bare measure_id
    is no longer used as a key — bypassing the v1 cross-cycle contamination.
    """
    if not FINANCE_DB_PATH.exists():
        return {"available": False, "reason": "finance_statewide_v2.db not found"}

    conn = sqlite3.connect(str(FINANCE_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT s.finance_campaign_id, s.stance, s.total_receipts,
               s.n_committees, s.top5_share, s.hhi,
               c.election_year, c.measure_db_id, c.measure_id
        FROM finance_summary s
        JOIN finance_campaign c USING (finance_campaign_id)
        WHERE c.status = 'matched'
        """
    ).fetchall()
    conn.close()

    by_campaign = defaultdict(lambda: {"meta": None, "sides": {}})
    for row in rows:
        rec = dict(row)
        cid = rec["finance_campaign_id"]
        if by_campaign[cid]["meta"] is None:
            by_campaign[cid]["meta"] = {
                "finance_campaign_id": cid,
                "election_year": rec.get("election_year"),
                "measure_db_id": rec.get("measure_db_id"),
                "measure_id": rec.get("measure_id"),
            }
        by_campaign[cid]["sides"][rec["stance"]] = rec

    def clean_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    campaigns_out = []
    better_funded_known = 0
    better_funded_won = 0
    support_total = 0
    oppose_total = 0

    for cid, payload in by_campaign.items():
        meta = payload["meta"] or {}
        sides = payload["sides"]
        support = float((sides.get("support") or {}).get("total_receipts") or 0)
        oppose = float((sides.get("oppose") or {}).get("total_receipts") or 0)
        support_total += support
        oppose_total += oppose

        linked = measures_by_db_id.get(meta.get("measure_db_id")) if meta.get("measure_db_id") is not None else None
        passed = linked.get("passed") if linked else None

        better_side = None
        better_won = None
        if support or oppose:
            better_side = "support" if support >= oppose else "oppose"
            if passed in (0, 1):
                better_funded_known += 1
                better_won = (better_side == "support" and passed == 1) or (better_side == "oppose" and passed == 0)
                better_funded_won += 1 if better_won else 0

        smaller_side = min(support, oppose)
        larger_side = max(support, oppose)
        funding_ratio = larger_side / smaller_side if smaller_side > 0 else None

        campaigns_out.append({
            "finance_campaign_id": cid,
            "measure_id": meta.get("measure_id"),
            "election_year": meta.get("election_year"),
            "year": meta.get("election_year"),  # alias for back-compat with consumers
            "title": linked.get("title") if linked else (meta.get("measure_id") or cid),
            "passed": passed,
            "support_receipts": round(support, 2),
            "oppose_receipts": round(oppose, 2),
            "total_receipts": round(support + oppose, 2),
            "better_funded_side": better_side,
            "better_funded_won": better_won,
            "funding_ratio": round(funding_ratio, 1) if funding_ratio is not None else None,
            "support_top5_share": clean_float((sides.get("support") or {}).get("top5_share")),
            "oppose_top5_share": clean_float((sides.get("oppose") or {}).get("top5_share")),
        })

    better_funded_losses = [
        row for row in campaigns_out
        if row.get("better_funded_won") is False and row.get("total_receipts", 0) > 0
    ]
    lopsided = [
        row for row in campaigns_out
        if row.get("funding_ratio") is not None and row.get("total_receipts", 0) > 0
    ]

    annual_receipts, top_donors_overall, repeat_donors, marquee_fights = _build_finance_supplements(
        campaigns_out, measures_by_db_id
    )

    return {
        "available": True,
        "measure_count": len(by_campaign),
        "support_receipts": round(support_total, 2),
        "oppose_receipts": round(oppose_total, 2),
        "total_receipts": round(support_total + oppose_total, 2),
        "better_funded_known": better_funded_known,
        "better_funded_won": better_funded_won,
        "better_funded_win_rate": pct(better_funded_won, better_funded_known),
        "top_measures": sorted(campaigns_out, key=lambda x: x["total_receipts"], reverse=True)[:12],
        "better_funded_losses": sorted(better_funded_losses, key=lambda x: x["total_receipts"], reverse=True)[:8],
        "largest_imbalances": sorted(lopsided, key=lambda x: x["funding_ratio"], reverse=True)[:8],
        "annual_receipts": annual_receipts,
        "top_donors_overall": top_donors_overall,
        "repeat_donors": repeat_donors,
        "marquee_fights": marquee_fights,
    }


# Curated marquee fights: three case studies spanning industries, outcomes, and
# funding-ratio shapes. Hand-picked rather than auto-derived so the panel can
# carry a coherent narrative across very different campaign archetypes.
MARQUEE_FIGHT_IDS = [
    {
        "finance_campaign_id": "PROP_22_2020",
        "headline": "App-based gig work vs labor",
        "takeaway": "Uber, Lyft, DoorDash, and Instacart pooled into a single $81M Yes committee — five-to-one over the labor coalition opposing them. The measure passed.",
    },
    {
        "finance_campaign_id": "PROP_27_2022",
        "headline": "Online sports betting vs tribal gaming",
        "takeaway": "The largest two-sided fight in the data ($181M). FanDuel and DraftKings spent $105M for; tribal coalitions led by San Manuel spent $76M against. Voters rejected it 17-83.",
    },
    {
        "finance_campaign_id": "PROP_8_2018",
        "headline": "Dialysis profit caps vs the dialysis industry",
        "takeaway": "DaVita and Fresenius spent $97M to defeat a SEIU-backed $24M effort to cap dialysis-clinic revenue. The industry side outspent the labor coalition about four-to-one — and won.",
    },
]


def _build_finance_supplements(campaigns_out, measures_by_db_id):
    """Build the four post-rebuild supplemental fields the panel redesign needs:

    1. annual_receipts — total receipts grouped by election year (bar chart)
    2. top_donors_overall — top 15 donors aggregated across matched campaigns
    3. repeat_donors — donors active in 3+ campaigns (filtered to ≥$1M to keep narrative)
    4. marquee_fights — 3 hand-picked case studies with both-sides donor breakdowns
    """
    if not FINANCE_DB_PATH.exists():
        return [], [], [], []

    conn = sqlite3.connect(str(FINANCE_DB_PATH))
    conn.row_factory = sqlite3.Row

    # 1. Annual receipts by election year (already keyed on c.election_year, so
    #    cross-cycle contamination is gone post-v2).
    annual = conn.execute(
        """
        SELECT c.election_year AS year,
               SUM(s.total_receipts) AS total,
               COUNT(DISTINCT c.finance_campaign_id) AS n_campaigns
        FROM finance_summary s
        JOIN finance_campaign c USING (finance_campaign_id)
        WHERE c.status = 'matched'
        GROUP BY c.election_year
        ORDER BY c.election_year
        """
    ).fetchall()
    annual_receipts = [
        {
            "year": int(r["year"]),
            "total_receipts": round(float(r["total"]), 2),
            "n_campaigns": int(r["n_campaigns"]),
        }
        for r in annual
        if r["year"] is not None
    ]

    # 2. Top donors overall — aggregate across all matched campaigns
    top_donors_rows = conn.execute(
        """
        SELECT donor_name_canon AS name,
               SUM(total_amount) AS total,
               COUNT(DISTINCT finance_campaign_id) AS n_campaigns
        FROM finance_top_donors
        GROUP BY donor_name_canon
        ORDER BY total DESC
        LIMIT 15
        """
    ).fetchall()
    top_donors_overall = [
        {
            "name": r["name"],
            "total_amount": round(float(r["total"]), 2),
            "n_campaigns": int(r["n_campaigns"]),
        }
        for r in top_donors_rows
    ]

    # 3. Repeat donors — donors active in 3+ campaigns AND ≥$1M aggregate.
    #    The dollar floor keeps the list narrative-relevant (otherwise it fills
    #    with $0.4M actors who happen to chip into many committees).
    repeat_rows = conn.execute(
        """
        SELECT donor_name_canon AS name,
               SUM(total_amount) AS total,
               COUNT(DISTINCT finance_campaign_id) AS n_campaigns
        FROM finance_top_donors
        GROUP BY donor_name_canon
        HAVING n_campaigns >= 3 AND total >= 1000000
        ORDER BY n_campaigns DESC, total DESC
        LIMIT 12
        """
    ).fetchall()
    repeat_donors = [
        {
            "name": r["name"],
            "total_amount": round(float(r["total"]), 2),
            "n_campaigns": int(r["n_campaigns"]),
        }
        for r in repeat_rows
    ]

    # 4. Marquee fights — three curated case studies. Pull per-side summary +
    #    top 5 donors per stance for each. If a curated id isn't in the DB
    #    (rebuild changed coverage), warn loudly — a 2-card "Three fights"
    #    section is an obvious broken state, so we want maintainers to notice.
    by_cid = {row["finance_campaign_id"]: row for row in campaigns_out}
    marquee_fights = []
    for spec in MARQUEE_FIGHT_IDS:
        cid = spec["finance_campaign_id"]
        if cid not in by_cid:
            print(
                f"WARNING: marquee fight {cid!r} not present in finance v2 DB; "
                f"section will render with fewer than {len(MARQUEE_FIGHT_IDS)} cards. "
                "Update MARQUEE_FIGHT_IDS in build_finance_insights.",
                file=sys.stderr,
            )
            continue
        camp = by_cid[cid]
        donor_rows = conn.execute(
            """
            SELECT stance, donor_name_canon, total_amount
            FROM (
                SELECT stance, donor_name_canon, total_amount,
                       ROW_NUMBER() OVER (PARTITION BY stance ORDER BY total_amount DESC, donor_name_canon) AS rn
                FROM finance_top_donors
                WHERE finance_campaign_id = ?
            )
            WHERE rn <= 5
            ORDER BY stance, total_amount DESC
            """,
            (cid,),
        ).fetchall()
        donors_by_stance = defaultdict(list)
        for d in donor_rows:
            donors_by_stance[d["stance"]].append({
                "name": d["donor_name_canon"],
                "total_amount": round(float(d["total_amount"]), 2),
            })
        marquee_fights.append({
            "finance_campaign_id": cid,
            "measure_id": camp.get("measure_id"),
            "election_year": camp.get("election_year"),
            "title": camp.get("title"),
            "headline": spec["headline"],
            "takeaway": spec["takeaway"],
            "passed": camp.get("passed"),
            "support_receipts": camp.get("support_receipts"),
            "oppose_receipts": camp.get("oppose_receipts"),
            "total_receipts": camp.get("total_receipts"),
            "support_top5_share": camp.get("support_top5_share"),
            "oppose_top5_share": camp.get("oppose_top5_share"),
            "support_top_donors": donors_by_stance.get("support", []),
            "oppose_top_donors": donors_by_stance.get("oppose", []),
        })

    conn.close()
    return annual_receipts, top_donors_overall, repeat_donors, marquee_fights


def build_featured_findings(
    overview, topic_stats, category_type_stats, threshold_stats, margin_stats, county_stats, finance
):
    local_share = overview.get("local_share")
    fiscal_count = sum(item["total"] for item in category_type_stats if item["category_type"] in FISCAL_TYPES)
    fiscal_share = pct(fiscal_count, overview["active_measures"])
    majority_failed = sum(item["majority_failed"] for item in threshold_stats)
    close_under_5 = margin_stats["close_counts"].get("under_5", 0)
    top_county = county_stats[0] if county_stats else {"county": "Unknown", "total": 0}

    findings = [
        {
            "id": "local-democracy-is-fiscal",
            "title": "The ballot is mostly local, and much of it is fiscal.",
            "deck": f"{local_share}% of active records are local measures, and {fiscal_share}% fall into tax, bond, or spending-limit measure types.",
            "metric": f"{local_share}%",
            "metric_label": "local measures",
            "confidence": "High",
            "method": "Active, non-duplicate records grouped by county and consolidated measure type.",
            "caveat": "Measure type is more reliable than topic for CEDA-heavy local records.",
        },
        {
            "id": "yes-wins-often",
            "title": "Voters approve more measures than they reject.",
            "deck": f"Among decided measures, {overview['pass_rate']}% passed statewide and locally combined.",
            "metric": f"{overview['pass_rate']}%",
            "metric_label": "pass rate",
            "confidence": "High",
            "method": "Decided active records where passed is coded 0 or 1.",
            "caveat": "This is descriptive, not a forecast for future measures.",
        },
        {
            "id": "thresholds-change-outcomes",
            "title": "Threshold rules create a class of majority-backed failures.",
            "deck": f"{majority_failed:,} decided measures received more than 50% yes but did not pass, usually because a higher threshold applied.",
            "metric": f"{majority_failed:,}",
            "metric_label": "majority-backed failures",
            "confidence": "Medium",
            "method": "Decided records with percent_yes above 50 and passed coded false.",
            "caveat": "A small number of threshold encodings are known to need manual verification.",
        },
        {
            "id": "close-calls",
            "title": "Hundreds of measures are decided near the knife-edge.",
            "deck": f"{close_under_5:,} measures landed within five percentage points of 50% yes.",
            "metric": f"{close_under_5:,}",
            "metric_label": "within 5 points",
            "confidence": "High",
            "method": "Records with valid percent_yes and decided outcomes.",
            "caveat": "Margin is measured around 50%, not around each measure's legal passage threshold.",
        },
        {
            "id": "geography-is-uneven",
            "title": "Measure activity is concentrated in the largest civic ecosystems.",
            "deck": f"{top_county['county']} has the most local measures in the database, with {top_county['total']:,} active records.",
            "metric": f"{top_county['total']:,}",
            "metric_label": f"{top_county['county']} measures",
            "confidence": "High",
            "method": "Active local records grouped by normalized county name.",
            "caveat": "Raw counts are not population-adjusted.",
        },
    ]

    if finance.get("available"):
        findings.append(
            {
                "id": "finance-lopsided",
                "title": "Statewide proposition campaigns are often big-money contests.",
                "deck": f"The finance database links {finance['measure_count']} statewide proposition IDs and {format_dollars(finance['total_receipts'])} in receipts.",
                "metric": format_dollars(finance["total_receipts"]),
                "metric_label": "linked receipts",
                "confidence": "Medium",
                "method": "CalAccess-derived statewide proposition finance summaries.",
                "caveat": "Finance coverage is statewide-only and limited to matched proposition committees.",
            }
        )

    return findings


def format_dollars(amount):
    amount = float(amount or 0)
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    return f"${amount:,.0f}"


def build_insights(db_path=DB_PATH):
    measures = load_measures(db_path)
    # Two indexes: by string measure_id (for legacy consumers) and by integer
    # db_id (for the v2 finance join, which keys on measure_db_id).
    measures_by_measure_id = {}
    measures_by_db_id = {}
    for measure in measures:
        mid = measure.get("measure_id")
        if mid and mid not in measures_by_measure_id:
            measures_by_measure_id[mid] = measure
        db_id = measure.get("id")
        if db_id is not None:
            measures_by_db_id[db_id] = measure

    overview = summarize_overview(measures)
    topic_stats = build_topic_stats(measures)
    topic_decade_matrix = build_topic_decade_matrix(measures)
    category_type_stats = build_category_type_stats(measures)
    threshold_stats = build_threshold_stats(measures)
    margin_stats = build_margin_stats(measures)
    county_stats = build_county_stats(measures)
    region_stats = build_region_stats(county_stats)
    time_series = build_time_series(measures)
    decade_series = build_decade_series(measures)
    election_cycle_stats = build_election_cycle_stats(measures)
    finance = build_finance_insights(measures_by_db_id)

    return {
        "version": 1,
        "overview": overview,
        "featured_findings": build_featured_findings(
            overview, topic_stats, category_type_stats, threshold_stats, margin_stats, county_stats, finance
        ),
        "time_series": time_series,
        "decade_series": decade_series,
        "election_cycle_stats": election_cycle_stats,
        "trend_insights": build_trend_insights(time_series, decade_series, election_cycle_stats),
        "topic_stats": topic_stats,
        "topic_decade_matrix": topic_decade_matrix,
        "topic_trends": build_topic_trends(measures, topic_stats),
        "topic_insights": build_topic_insights(measures, topic_stats, topic_decade_matrix),
        "category_type_stats": category_type_stats,
        "type_trends": build_type_trends(measures),
        "type_insights": build_type_insights(measures, category_type_stats, overview),
        "statistical_comparisons": build_statistical_comparisons(measures),
        "threshold_stats": threshold_stats,
        "threshold_insights": build_threshold_insights(measures, threshold_stats),
        "margin_stats": margin_stats,
        "close_call_insights": build_close_call_insights(measures, margin_stats),
        "county_stats": county_stats,
        "region_stats": region_stats,
        "geography_insights": build_geography_insights(county_stats, region_stats),
        "finance": finance,
        "methodology": {
            "scope": "Active, non-duplicate measures in scraper/data/ballot_measures.db.",
            "sources": sorted(Counter(m.get("data_source") or "Unknown" for m in measures).items(), key=lambda x: x[1], reverse=True),
            "notes": [
                "CEDA dominates local measure coverage and is strongest for outcomes, categories, and vote totals.",
                "Campaign finance analysis uses the year-scoped statewide proposition finance database (rebuilt 2026-05-04, keyed by finance_campaign_id) and is not available for local measures.",
                "Pending-measure analogs are intentionally excluded from this MVP to avoid prediction framing.",
            ],
        },
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate compact Insights data")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output JSON path")
    parser.add_argument("--db", default=str(DB_PATH), help="Main SQLite database path")
    args = parser.parse_args()

    payload = build_insights(Path(args.db))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Generated insights: {output}")
    print(f"Featured findings: {len(payload['featured_findings'])}")
    print(f"County rows: {len(payload['county_stats'])}")


if __name__ == "__main__":
    main()
