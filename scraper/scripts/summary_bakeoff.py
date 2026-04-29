#!/usr/bin/env python3
"""
Summary bakeoff harness.

Pulls a stratified 25-measure sample, generates summaries via multiple
models against the summary spec at plans/summary-spec.md, runs automated
scoring, writes results to JSONL for analysis.

Usage:
    export ANTHROPIC_API_KEY=...    # for Opus 4.7 / Sonnet 4 / Haiku 4.5
    export OPENAI_API_KEY=...       # for GPT-5.5 (optional; skipped if missing)

    python scripts/summary_bakeoff.py
    python scripts/summary_bakeoff.py --seed 42 --models opus,sonnet
    python scripts/summary_bakeoff.py --measure-ids PROP_36,PROP_50

Cost: ~25 measures x 4 models x ~$0.005-0.025 per call ~= $1-2 total at
real-time pricing. No batch API for the bakeoff itself (turnaround latency
matters more than cost at this scale).
"""
import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH
from src.research.sources.historical import get_historical_context
from src.research.sources.finance import get_finance_facts
from src.research.sources.census import get_demographics_for_measure, format_demographics_for_prompt

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SUMMARY_SPEC_PATH = REPO_ROOT / "plans" / "summary-spec.md"
DEFAULT_OUT = Path(__file__).parent.parent / "data" / "summary_bakeoff_results.jsonl"

# Models to compare. Each: (label, model_id, provider).
MODELS = [
    ("opus",   "claude-opus-4-7",          "anthropic"),
    ("sonnet", "claude-sonnet-4-6",        "anthropic"),
    ("haiku",  "claude-haiku-4-5-20251001","anthropic"),
    ("gpt5_5", "gpt-5.5",                  "openai"),
]

# Spec failure-mode constants (mirrors plans/summary-spec.md).
FORBIDDEN_PHRASES = [
    "not yet available", "tbd", "information unavailable",
    "various stakeholders", "broadly impacts", "supports outcomes",
    "various supporters", "various opponents",
    "stakeholders weighed in", "weigh in", "support outcomes",
]
HEDGING_WORDS = [r"\bmay\b", r"\bcould\b", r"\bpotentially\b", r"\bpossibly\b"]
TARGET_WORD_COUNT = (50, 100)
SOFT_TARGET_WORD_COUNT = (60, 80)

# ---------------------------------------------------------------------------
# Prompt template (edit and re-run during iteration)
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """You are governed by the following editorial spec for ballot-measure summaries.
Read it. Follow it. Output that violates the spec will be rejected.

---BEGIN SPEC---
{spec_text}
---END SPEC---

You are writing a summary for this California ballot measure:

Measure ID: {measure_id}
Year: {year}
Jurisdiction: {county}
Title: {title}

Ballot question (if available):
{ballot_question}

Existing description (if any):
{description}

Existing summary text (current baseline; you can ignore or improve on this):
{summary_text}

Outcome:
{outcome}

{substrate_block}

Instructions:
- Output ONLY the summary text. No JSON, no preamble, no headers, no explanation.
- One paragraph, 65-80 words target (hard ceiling 100, hard floor 50). Aim for the upper end of the target to leave buffer.
- Follow every rule in the spec above, especially:
  * Refer to the measure by the actual jurisdictional entity from the ballot question (e.g., "Middle River Community Services District's Measure E"), not the CEDA row label (e.g., "Calaveras Measure E"), when the ballot question provides one.
  * Use exact dollar amounts from the substrate ($44.7M, not $44M).
  * If the measure has a clear historical link in the substrate (a prior measure it reverses, extends, or replaces), lead with that relationship.
- Use the substrate signal where it adds real value; don't pad.

Summary:"""


# ---------------------------------------------------------------------------
# Sample selection
# ---------------------------------------------------------------------------

STRATA_QUERIES = [
    ("statewide_modern", """
        SELECT * FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND county='Statewide'
            AND year BETWEEN 2018 AND 2024
            AND measure_id LIKE 'PROP%'
        ORDER BY id
    """, 5),
    ("statewide_historical", """
        SELECT * FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND county='Statewide'
            AND year BETWEEN 1990 AND 2010
        ORDER BY id
    """, 5),
    ("local_rich", """
        SELECT m.* FROM measures m
        WHERE is_active=1 AND is_duplicate=0
            AND county != 'Statewide'
            AND year >= 2018
            AND category_type IS NOT NULL
            AND ballot_question IS NOT NULL
            AND length(ballot_question) > 60
        ORDER BY id
    """, 5),
    ("local_sparse", """
        SELECT * FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND county != 'Statewide'
            AND year < 2010
            AND (description IS NULL OR length(description) < 30)
            AND (ballot_question IS NULL OR length(ballot_question) < 30)
        ORDER BY id
    """, 5),
    ("close_vote", """
        SELECT * FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND percent_yes BETWEEN 47 AND 53
            AND passed IS NOT NULL
            AND title IS NOT NULL
        ORDER BY id
    """, 3),
    ("pending_2026", """
        SELECT * FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND year = 2026
        ORDER BY id
    """, 2),
]


def select_stratified_sample(conn: sqlite3.Connection, seed: int = 42,
                              scale: int = 1) -> List[Dict]:
    """Return a stratified sample, deterministic by seed.

    Default scale=1 returns the 25-measure sample used in v0.1 bakeoff.
    scale=4 returns ~100 measures. The same seed + scale combination always
    returns the same sample, so the API path and subagent path can share
    the exact same measure set.
    """
    import random
    rng = random.Random(seed)
    sample = []
    for stratum, query, n in STRATA_QUERIES:
        target_n = n * scale
        cur = conn.execute(query)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        if not rows:
            logger.warning("Stratum %s: zero rows, skipping", stratum)
            continue
        chosen = rng.sample(rows, min(target_n, len(rows)))
        for m in chosen:
            m['_stratum'] = stratum
            sample.append(m)
        logger.info("Stratum %s: %d available, picked %d",
                    stratum, len(rows), len(chosen))
    return sample


# ---------------------------------------------------------------------------
# Substrate assembly
# ---------------------------------------------------------------------------

def format_substrate_for_summary(measure: Dict, conn: sqlite3.Connection) -> str:
    """Build a compact substrate block for the summary prompt.

    Briefing prompts use the full historical-context formatter; for summaries
    we want a tighter version that surfaces only what could plausibly fit
    in 70 words of output.
    """
    lines = []

    historical = get_historical_context(measure, conn)

    # Threshold context
    th = historical.get('threshold_context') or {}
    if th:
        line = f"Vote threshold: {th.get('threshold_label', '50%')}."
        if th.get('trap_rate', 0) > 0:
            line += f" Trap rate (won majority but failed under threshold): {th['trap_rate']}%."
        lines.append(line)

    # Concrete similar measures (top 3)
    similar = (historical.get('similar_measures') or [])[:3]
    if similar:
        lines.append("Concrete similar past measures:")
        for s in similar:
            outcome = {1: "passed", 0: "failed"}.get(s.get('passed'), "outcome unknown")
            py = s.get('percent_yes')
            py_str = f" at {py:.1f}% YES" if py is not None else ""
            lines.append(f"  - {s['year']} {s.get('county') or ''} ({s['measure_id']}): {outcome}{py_str}")

    # Same-jurisdiction history (top 2)
    history = (historical.get('same_jurisdiction_history') or [])[:2]
    if history:
        lines.append(f"Same-jurisdiction prior measures of same type ({measure.get('category_type')}):")
        for h in history:
            outcome = {1: "passed", 0: "failed"}.get(h.get('passed'), "outcome unknown")
            py = h.get('percent_yes')
            py_str = f" at {py:.1f}%" if py is not None else ""
            lines.append(f"  - {h['year']} {h['measure_id']}: {outcome}{py_str}")

    # Aggregate context
    topic_stats = historical.get('topic_stats') or {}
    if topic_stats.get('by_type'):
        t = topic_stats['by_type']
        lines.append(
            f"{t['type']} measures historically: n={t['total']}, "
            f"pass rate {t['pass_rate']}%, avg YES {t['avg_yes']}%."
        )

    # Election cycle
    cycle = historical.get('election_cycle') or {}
    if cycle.get('current_cycle_label'):
        lines.append(f"This measure is on a {cycle['current_cycle_label']}.")

    # Author for legislatively-referred
    author = historical.get('author_history') or {}
    if author.get('author'):
        line = f"Author: {author['author']} ({author.get('leg_id', 'leg-referred')})."
        prior = author.get('prior_measures') or []
        if prior:
            outcomes = [{1: "passed", 0: "failed"}.get(p.get('passed'), "?") for p in prior[:3]]
            line += f" Prior measures by same author: {len(prior)} found ({', '.join(outcomes)})."
        lines.append(line)

    # Cross-state precedent
    cross = historical.get('cross_state_history') or {}
    agg = cross.get('aggregate') or {}
    if agg:
        flags = ', '.join(f.replace('is_', '') for f in agg.get('matched_flags') or [])
        lines.append(
            f"Statewide CA precedent on this topic ({flags}): {agg['n']} measures "
            f"({agg['first_year']}-{agg['last_year']}), pass rate {agg['pass_rate']}%."
        )

    # Demographics for per-household translation
    demo = get_demographics_for_measure(measure)
    if demo:
        block = format_demographics_for_prompt(demo)
        if block:
            lines.append("Demographics (use for per-household translation when fiscal figures appear):")
            lines.append(block)

    # Finance for statewide measures
    finance = get_finance_facts(measure)
    if finance:
        lines.append("Campaign finance (CAL-ACCESS, named donors authoritative):")
        for k, v in finance['extracted'].items():
            lines.append(f"  {k}: {v}")

    if not lines:
        return "No substrate available beyond the measure record."
    return "Substrate (use to add specificity, not to pad):\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def load_summary_spec() -> Tuple[str, str, str]:
    if not SUMMARY_SPEC_PATH.exists():
        raise FileNotFoundError(f"Summary spec not found at {SUMMARY_SPEC_PATH}")
    text = SUMMARY_SPEC_PATH.read_text(encoding='utf-8')
    spec_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    spec_version = "unknown"
    if text.startswith('---'):
        try:
            end = text.index('---', 3)
            for line in text[3:end].splitlines():
                if line.strip().startswith('spec_version:'):
                    spec_version = line.split(':', 1)[1].strip()
                    break
        except ValueError:
            pass
    return text, spec_version, spec_hash


def build_outcome_string(measure: Dict) -> str:
    passed = measure.get('passed')
    py = measure.get('percent_yes')
    if passed is None:
        return "Pending or unknown."
    label = "Passed" if passed == 1 else "Failed"
    if py is not None:
        return f"{label} at {py:.1f}% YES."
    return label + "."


def build_prompt(measure: Dict, conn: sqlite3.Connection, spec_text: str) -> str:
    substrate_block = format_substrate_for_summary(measure, conn)
    return PROMPT_TEMPLATE.format(
        spec_text=spec_text,
        measure_id=measure.get('measure_id') or '',
        year=measure.get('year') or '',
        county=measure.get('county') or '',
        title=(measure.get('title') or '')[:200],
        ballot_question=(measure.get('ballot_question') or '(none)')[:600],
        description=(measure.get('description') or '(none)')[:600],
        summary_text=(measure.get('summary_text') or '(none)')[:600],
        outcome=build_outcome_string(measure),
        substrate_block=substrate_block,
    )


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------

def call_anthropic(prompt: str, model_id: str, api_key: str,
                   max_retries: int = 2) -> Dict:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            t0 = time.time()
            resp = client.messages.create(
                model=model_id,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.time() - t0
            return {
                "summary_text": resp.content[0].text.strip(),
                "input_tokens": getattr(resp.usage, 'input_tokens', None),
                "output_tokens": getattr(resp.usage, 'output_tokens', None),
                "latency_sec": round(elapsed, 2),
                "error": None,
            }
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            if "overloaded" in msg or "529" in msg or "rate" in msg:
                wait = 30 * (attempt + 1)
                logger.warning("Anthropic %s: %s -- retry in %ds", model_id, e, wait)
                time.sleep(wait)
                continue
            break
    return {"summary_text": None, "error": str(last_exc)}


def call_openai(prompt: str, model_id: str, api_key: str,
                max_retries: int = 2) -> Dict:
    try:
        from openai import OpenAI
    except ImportError:
        return {"summary_text": None, "error": "openai package not installed"}
    client = OpenAI(api_key=api_key)
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            t0 = time.time()
            resp = client.chat.completions.create(
                model=model_id,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.time() - t0
            return {
                "summary_text": resp.choices[0].message.content.strip(),
                "input_tokens": getattr(resp.usage, 'prompt_tokens', None),
                "output_tokens": getattr(resp.usage, 'completion_tokens', None),
                "latency_sec": round(elapsed, 2),
                "error": None,
            }
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            if "rate" in msg or "overloaded" in msg or "529" in msg:
                wait = 30 * (attempt + 1)
                logger.warning("OpenAI %s: %s -- retry in %ds", model_id, e, wait)
                time.sleep(wait)
                continue
            break
    return {"summary_text": None, "error": str(last_exc)}


# ---------------------------------------------------------------------------
# Automated scoring (mirrors summary-spec.md failure modes)
# ---------------------------------------------------------------------------

def score_summary(text: str, measure: Dict) -> Dict:
    if not text:
        return {"scoreable": False, "error": "empty output"}

    words = text.split()
    word_count = len(words)

    lower = text.lower()
    forbidden_hits = [p for p in FORBIDDEN_PHRASES if p in lower]
    hedging_hits = sum(len(re.findall(p, lower)) for p in HEDGING_WORDS)

    dollar_count = len(re.findall(r"\$[\d,]+(?:\.\d+)?(?:[BMK]|\s?(?:billion|million|thousand))?", text))
    pct_count = len(re.findall(r"\d+(?:\.\d+)?\s*%", text))
    year_count = len(re.findall(r"\b(19|20)\d{2}\b", text))
    numeric_count = dollar_count + pct_count + year_count

    # Rough named-entity proxy: 2+ consecutive Capitalized words, excluding sentence starts
    ne_matches = re.findall(r"(?<!\.\s)(?<!^)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
    ne_count = len(ne_matches)

    title = (measure.get('title') or '').strip().lower()
    title_words = set(re.findall(r"\w+", title)) if title else set()
    summary_words = set(re.findall(r"\w+", lower))
    title_overlap = len(title_words & summary_words) / max(len(title_words), 1) if title_words else 0

    # Skip the title-overlap check when the title is a generic label, not editorial
    # content. Two patterns to skip:
    #   (a) Short titles (<=4 words) — "Proposition 9", "BUTTE Measure D", etc.
    #   (b) CEDA row labels matching `[COUNTY] Measure [LETTER]` form
    # In these cases, naming the measure verbatim doesn't violate the spec's
    # intent ("don't just rephrase the title as the summary").
    title_word_count = len(title.split())
    is_ceda_label = bool(re.match(r"^[a-z\s]+ measure [a-z0-9]+$", title))
    skip_title_overlap_check = title_word_count <= 4 or is_ceda_label

    deterministic_outcome_ok = True
    passed = measure.get('passed')
    if passed == 1 and 'failed' in lower and 'passed' not in lower:
        deterministic_outcome_ok = False
    if passed == 0 and 'passed' in lower and 'failed' not in lower:
        deterministic_outcome_ok = False

    has_outcome_term = ('passed' in lower or 'failed' in lower or
                        'pending' in lower or 'rejected' in lower or
                        'approved' in lower or '%' in text)

    spec_failures = []
    if not (TARGET_WORD_COUNT[0] <= word_count <= TARGET_WORD_COUNT[1]):
        spec_failures.append(f"word_count_out_of_range ({word_count})")
    if forbidden_hits:
        spec_failures.append(f"forbidden_phrases: {forbidden_hits}")
    if title_overlap > 0.85 and not skip_title_overlap_check:
        spec_failures.append(f"title_overlap_high ({title_overlap:.2f})")
    if numeric_count == 0 and ne_count == 0:
        spec_failures.append("zero_specifics (no numbers, no named entities)")
    if not deterministic_outcome_ok:
        spec_failures.append("contradicts_deterministic_outcome")
    if passed is not None and not has_outcome_term:
        spec_failures.append("outcome_term_missing")

    return {
        "scoreable": True,
        "word_count": word_count,
        "in_soft_target": SOFT_TARGET_WORD_COUNT[0] <= word_count <= SOFT_TARGET_WORD_COUNT[1],
        "in_hard_target": TARGET_WORD_COUNT[0] <= word_count <= TARGET_WORD_COUNT[1],
        "forbidden_hits": forbidden_hits,
        "hedging_count": hedging_hits,
        "dollar_count": dollar_count,
        "percent_count": pct_count,
        "year_count": year_count,
        "numeric_count": numeric_count,
        "named_entity_count": ne_count,
        "title_overlap_ratio": round(title_overlap, 3),
        "deterministic_outcome_ok": deterministic_outcome_ok,
        "has_outcome_term": has_outcome_term,
        "spec_failure_flags": spec_failures,
        "passes_spec": len(spec_failures) == 0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=42,
                        help='Sampling seed for deterministic re-runs')
    parser.add_argument('--scale', type=int, default=1,
                        help='Stratification scale factor: 1 = 25 measures, 4 = ~100')
    parser.add_argument('--measure-ids', type=str, default=None,
                        help='Comma-separated measure_ids; overrides stratified sampling')
    parser.add_argument('--models', type=str, default=None,
                        help='Comma-separated model labels (opus,sonnet,haiku,gpt5_5); default = all available')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT,
                        help='Output JSONL path')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print prompts; do not call APIs')
    args = parser.parse_args()

    spec_text, spec_version, spec_hash = load_summary_spec()
    logger.info("Loaded summary spec v%s (hash %s)", spec_version, spec_hash)

    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    openai_key = os.environ.get('OPENAI_API_KEY')

    selected_labels = set(args.models.split(',')) if args.models else None
    active_models = []
    for label, model_id, provider in MODELS:
        if selected_labels and label not in selected_labels:
            continue
        if provider == 'anthropic' and not anthropic_key:
            logger.warning("Skipping %s: ANTHROPIC_API_KEY not set", label)
            continue
        if provider == 'openai' and not openai_key:
            logger.warning("Skipping %s: OPENAI_API_KEY not set", label)
            continue
        active_models.append((label, model_id, provider))

    if not active_models and not args.dry_run:
        logger.error("No models available (set API keys or use --dry-run).")
        return 1
    logger.info("Active models: %s", [m[0] for m in active_models])

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    if args.measure_ids:
        ids = [s.strip() for s in args.measure_ids.split(',')]
        ph = ','.join('?' * len(ids))
        cur = conn.execute(
            f"SELECT * FROM measures WHERE measure_id IN ({ph}) AND is_active=1 AND is_duplicate=0",
            ids,
        )
        sample = [dict(r) for r in cur.fetchall()]
        for m in sample:
            m['_stratum'] = 'manual'
    else:
        sample = select_stratified_sample(conn, seed=args.seed, scale=args.scale)
    logger.info("Sample size: %d", len(sample))

    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Append mode so re-runs don't wipe prior columns. To start fresh,
    # delete data/summary_bakeoff_results.jsonl manually before running.
    with open(args.out, 'a', encoding='utf-8') as fh:
        for i, measure in enumerate(sample, 1):
            prompt = build_prompt(measure, conn, spec_text)
            logger.info("[%d/%d] %s %s %s (%s)", i, len(sample),
                        measure.get('year'), measure.get('county'),
                        measure.get('measure_id'), measure.get('_stratum'))

            if args.dry_run:
                print("\n" + "=" * 80)
                print(f"PROMPT for {measure['measure_id']} ({measure['_stratum']}):")
                print(prompt[:1500] + ("\n... [truncated]" if len(prompt) > 1500 else ""))
                continue

            for label, model_id, provider in active_models:
                t0 = time.time()
                if provider == 'anthropic':
                    result = call_anthropic(prompt, model_id, anthropic_key)
                else:
                    result = call_openai(prompt, model_id, openai_key)

                scoring = score_summary(result.get('summary_text') or '', measure)

                record = {
                    'measure_id': measure.get('measure_id'),
                    'year': measure.get('year'),
                    'county': measure.get('county'),
                    'stratum': measure.get('_stratum'),
                    'category_type': measure.get('category_type'),
                    'passed': measure.get('passed'),
                    'percent_yes': measure.get('percent_yes'),
                    'model_label': label,
                    'model_id': model_id,
                    'model_provider': provider,
                    'spec_version': spec_version,
                    'spec_hash': spec_hash,
                    'input_tokens': result.get('input_tokens'),
                    'output_tokens': result.get('output_tokens'),
                    'latency_sec': result.get('latency_sec'),
                    'summary_text': result.get('summary_text'),
                    'error': result.get('error'),
                    'scoring': scoring,
                    'generated_at': datetime.utcnow().isoformat(),
                }
                fh.write(json.dumps(record, default=str) + '\n')
                fh.flush()

                status = "OK" if not result.get('error') else "ERR"
                spec_pass = "PASS" if scoring.get('passes_spec') else "FAIL"
                logger.info("  %s %s [%s] wc=%s flags=%s",
                            label, status, spec_pass,
                            scoring.get('word_count'),
                            len(scoring.get('spec_failure_flags') or []))

    conn.close()
    logger.info("Wrote results to %s", args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
