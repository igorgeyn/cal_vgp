"""
Historical context source — uses the CalBallot database to find
similar past measures and compute relevant statistics.

No external fetching needed. This is the "secret weapon" source
that no other research tool has.
"""
import sqlite3
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


def get_historical_context(measure: Dict, conn: sqlite3.Connection,
                           top_k: int = 20) -> Dict:
    """
    Build historical context for a measure from the CalBallot database.

    Returns a dict with:
        - similar_measures: list of most similar past measures, with content
        - topic_stats: pass rates and margins for this topic/type
        - county_stats: how this county/statewide votes on similar measures
        - threshold_context: what threshold applies and trap rate
        - temporal_trend: how voting on this topic has changed over time
    """
    context = {}

    # 1. Find semantically similar measures via embeddings, with content
    context['similar_measures'] = _find_similar_measures(measure, conn, top_k)

    # 2. Topic/type statistics
    context['topic_stats'] = _get_topic_stats(measure, conn)

    # 3. Threshold context
    context['threshold_context'] = _get_threshold_context(measure, conn)

    # 4. Temporal trend
    context['temporal_trend'] = _get_temporal_trend(measure, conn)

    # 5. Same-jurisdiction history: prior measures of same type in same county
    context['same_jurisdiction_history'] = _get_same_jurisdiction_history(measure, conn)

    # 6. Same-ballot companions: other measures voters saw on the same ballot
    context['same_ballot_companions'] = _get_same_ballot_companions(measure, conn)

    # 7. Cross-state CA precedent on this topic (statewide history 1911-2018)
    context['cross_state_history'] = _get_cross_state_topic_history(measure, conn)

    # 8. CPI deflator table — covers the years referenced by other context fields,
    #    so the synthesis step can compare historical fiscal figures in real terms.
    context['cpi_table'] = _build_cpi_table_for_context(context)

    # 9. Census/ACS demographics for per-household fiscal translation
    from src.research.sources.census import get_demographics_for_measure
    context['demographics'] = get_demographics_for_measure(measure)

    # 10. Election-cycle context: presidential / midterm / off-year / special
    context['election_cycle'] = _get_election_cycle_context(measure, conn)

    # 11. Author / sponsor track record (legislatively-referred measures only)
    context['author_history'] = _get_author_history_context(measure, conn)

    return context


# Pattern: 'SCA 1 (Newman)', 'ACA 13 (Ward)', 'SB 42 (Umberg)', 'AB 440 ...'
# Author appears in parens after the leg-id. Anchored to alphanumeric measure
# prefix to avoid catching parens in unrelated titles.
import re
AUTHOR_PATTERN = re.compile(
    r'\b((?:SCA|ACA|SB|AB|HR|SR|HCR|SCR)\s*\d+[A-Za-z]?)\s*\(([^)]+)\)',
    re.IGNORECASE,
)


def _parse_author(measure: Dict):
    """Extract (leg_id, author_name) from legislatively-referred measure
    titles. Returns (None, None) for initiatives, propositions, or anything
    else that doesn't fit the pattern.
    """
    candidates = [
        measure.get('measure_id') or '',
        measure.get('title') or '',
        measure.get('generated_title') or '',
        measure.get('original_title') or '',
    ]
    for s in candidates:
        m = AUTHOR_PATTERN.search(s)
        if m:
            leg_id = m.group(1).upper().replace('  ', ' ').strip()
            author = m.group(2).strip()
            # Reject obviously not-a-name strings (commas, "et al" lists,
            # generic titles like "Res. Ch. 176").
            if any(t in author.lower() for t in ('res.', 'ch.', 'stats.')):
                continue
            if len(author) < 2 or len(author) > 60:
                continue
            return leg_id, author
    return None, None


def _get_author_history_context(measure: Dict, conn: sqlite3.Connection,
                                 limit: int = 8) -> Dict:
    """For legislatively-referred measures, find other measures by the same
    author. Pure-DB; no external lookups. Surfaces accountability and prior
    pattern: 'Sen. Newman previously authored SCA 11 (passed 56%) and SB 24
    (signed)'.
    """
    leg_id, author = _parse_author(measure)
    if not author:
        return {}

    # Loose match on author name in title fields. Use FTS later if performance
    # becomes an issue; current corpus is small enough for LIKE.
    self_id = measure.get('measure_id')
    self_year = measure.get('year') or 9999
    name_pattern = f"%({author})%"

    cursor = conn.execute("""
        SELECT measure_id, year, title, generated_title, percent_yes, passed
        FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND year < ?
            AND (measure_id IS NOT ? OR ? IS NULL)
            AND (
                title LIKE ?
                OR generated_title LIKE ?
                OR original_title LIKE ?
                OR measure_id LIKE ?
            )
        ORDER BY year DESC
        LIMIT ?
    """, (self_year, self_id, self_id, name_pattern, name_pattern,
          name_pattern, name_pattern, limit * 3))

    cols = [d[0] for d in cursor.description]
    history = []
    seen = set()
    for row in cursor.fetchall():
        rec = dict(zip(cols, row))
        # Re-verify with the parser to avoid false positives from descriptions
        # that just happen to mention the surname
        check = {'measure_id': rec.get('measure_id'),
                 'title': rec.get('title'),
                 'generated_title': rec.get('generated_title'),
                 'original_title': None}
        their_leg, their_author = _parse_author(check)
        if their_author and their_author.lower() != author.lower():
            continue
        if their_leg in seen:
            continue
        seen.add(their_leg)

        py = _normalize_percent_yes(rec.get('percent_yes'))
        title = rec.get('generated_title') or rec.get('title') or ''
        history.append({
            'leg_id': their_leg or rec.get('measure_id'),
            'year': rec.get('year'),
            'title': title[:120],
            'percent_yes': round(py, 1) if py is not None else None,
            'passed': rec.get('passed'),
        })
        if len(history) >= limit:
            break

    return {
        'leg_id': leg_id,
        'author': author,
        'prior_measures': history,
    }


def classify_election_cycle(year: Optional[int],
                            election_type: Optional[str] = None) -> Optional[str]:
    """Map a measure's (year, election_type) to a cycle label.

    With election_type known: returns a combined label like
    'presidential_general', 'midterm_primary', 'off_year_general'. These are
    more useful than year alone because primary and general electorates
    differ substantially within the same year (primary turnout is much
    lower and skews more partisan/engaged).

    With election_type missing: falls back to the year-only label
    ('presidential', 'midterm', 'off_year').

    Specials always return 'special' regardless of year.
    """
    if year is None:
        return None
    et = (election_type or '').strip().lower()

    if et == 'special':
        return 'special'

    if year % 4 == 0:
        year_cycle = 'presidential'
    elif year % 2 == 0:
        year_cycle = 'midterm'
    else:
        year_cycle = 'off_year'

    if et in ('primary', 'general'):
        return f'{year_cycle}_{et}'
    # Type unknown — return year-only label
    return year_cycle


CYCLE_LABELS = {
    # Combined labels (preferred when election_type is known)
    'presidential_general': 'presidential general election',
    'presidential_primary': 'presidential primary',
    'midterm_general': 'midterm general election',
    'midterm_primary': 'midterm primary',
    'off_year_general': 'off-year general (odd-year, non-federal)',
    'off_year_primary': 'off-year primary',
    # Fallback labels (when election_type is unknown)
    'presidential': 'presidential year (type unknown)',
    'midterm': 'midterm year (type unknown)',
    'off_year': 'off-year (type unknown)',
    # Always
    'special': 'special election',
}


def _get_election_cycle_context(measure: Dict, conn: sqlite3.Connection) -> Dict:
    """Cycle classification for the current measure, plus pass-rate aggregates
    for the same category_type bucketed by cycle.

    Why this matters: off-cycle and special elections have very different
    electorates than general elections — pass rates can swing 15+ points for
    the same measure type. The LLM needs this context to reason about whether
    historical aggregates apply to the current measure's election environment.
    """
    year = measure.get('year')
    cur_cycle = classify_election_cycle(year, measure.get('election_type'))
    if not cur_cycle:
        return {}

    out = {
        'current_cycle': cur_cycle,
        'current_cycle_label': CYCLE_LABELS.get(cur_cycle, cur_cycle),
    }

    # Bucketed historical pass rates within same category_type
    cat_type = measure.get('category_type')
    if not cat_type:
        return out

    # Pull all matching historical measures' year + outcome; bucket in Python
    # to avoid pushing the cycle classification into SQL.
    cursor = conn.execute("""
        SELECT year, election_type, passed,
               CASE WHEN percent_yes > 0 AND percent_yes <= 1 THEN percent_yes * 100
                    WHEN percent_yes BETWEEN 0 AND 100 THEN percent_yes
               END AS py
        FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND category_type = ?
            AND passed IS NOT NULL
            AND year IS NOT NULL
    """, (cat_type,))

    buckets: Dict[str, Dict] = {}
    for y, et, passed, py in cursor.fetchall():
        cycle = classify_election_cycle(y, et)
        if not cycle:
            continue
        b = buckets.setdefault(cycle, {'n': 0, 'passed': 0, 'sum_yes': 0.0, 'n_yes': 0})
        b['n'] += 1
        if passed == 1:
            b['passed'] += 1
        if py is not None:
            b['sum_yes'] += py
            b['n_yes'] += 1

    by_cycle = []
    for cycle, b in buckets.items():
        if b['n'] < 5:  # too few to report
            continue
        by_cycle.append({
            'cycle': cycle,
            'cycle_label': CYCLE_LABELS.get(cycle, cycle),
            'n': b['n'],
            'pass_rate': round(100 * b['passed'] / b['n'], 1),
            'avg_yes': round(b['sum_yes'] / b['n_yes'], 1) if b['n_yes'] else None,
        })
    # Sort with current cycle first, then by sample size
    by_cycle.sort(key=lambda x: (x['cycle'] != cur_cycle, -x['n']))
    out['by_cycle'] = by_cycle

    return out


# Keyword -> historical topic flag mapping. Used to detect which flags apply
# to a current measure based on its title/description/category. Conservative —
# only triggers on clearly-on-topic words. NOTE: historical 'is_marijuana' flag
# in the source CSV uses 'drug' broadly (covers tobacco/cigarette tax measures
# too — see Prop 29). Don't map generic 'drug' or 'cigarette' here, only
# explicit cannabis/marijuana terms, since false-positives propagate to LLM.
TOPIC_KEYWORDS = {
    'is_tax': ['tax', 'sales tax', 'parcel tax', 'property tax', 'utility tax',
               'transfer tax', 'business tax', 'transient occupancy', 'fee',
               'revenue', 'levy'],
    'is_education': ['school', 'education', 'student', 'teacher', 'classroom',
                     'university', 'college', 'community college', 'k-12'],
    'is_criminal': ['crime', 'criminal', 'police', 'sheriff', 'prosecut',
                    'sentenc', 'parole', 'incarcerat', 'jail', 'prison',
                    'felony'],
    'is_health': ['hospital', 'medical', 'health', 'medicaid', 'medi-cal',
                  'mental health', 'public health'],
    'is_environment': ['environment', 'climate', 'pollut', 'wildlife',
                       'conservation', 'wildfire', 'water quality',
                       'air quality', 'emissions'],
    'is_elections': ['election', 'voter', 'voting', 'ballot', 'campaign finance',
                     'redistrict', 'recall'],
    'is_marijuana': ['marijuana', 'cannabis'],
    'is_gambling': ['gambling', 'casino', 'card room', 'lottery',
                    'horse racing'],
    'is_abortion': ['abortion', 'reproductive rights'],
    'is_marriage': ['same-sex marriage', 'civil union', 'domestic partner'],
}


def _detect_topic_flags(measure: Dict) -> List[str]:
    """Detect which historical topic flags apply to the current measure
    based on keyword presence in title, ballot question, description, and
    category fields. Returns a list of flag column names.
    """
    text = ' '.join(filter(None, [
        str(measure.get('title') or ''),
        str(measure.get('ballot_question') or ''),
        str(measure.get('description') or ''),
        str(measure.get('summary_text') or ''),
        str(measure.get('category_type') or ''),
        str(measure.get('category_topic') or ''),
    ])).lower()

    flags = []
    for flag, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            flags.append(flag)
    return flags


def _get_cross_state_topic_history(measure: Dict, conn: sqlite3.Connection,
                                   limit: int = 6) -> Dict:
    """Statewide CA historical measures matching this measure's topic(s).

    Pulls from ca_historical_measures (1911-2018 NCSL/Ballotpedia). Returns
    most recent matching measures plus aggregate pass-rate context.
    """
    flags = _detect_topic_flags(measure)
    if not flags:
        return {}

    flag_clause = ' OR '.join(f"{f} = 1" for f in flags)

    # Aggregate stats for matched topics
    cursor = conn.execute(f"""
        SELECT COUNT(*) AS n,
               SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS passed,
               AVG(CASE WHEN pct_yes BETWEEN 0 AND 100 THEN pct_yes END) AS avg_yes,
               MIN(year) AS first_year, MAX(year) AS last_year
        FROM ca_historical_measures
        WHERE ({flag_clause}) AND passed IS NOT NULL
    """)
    row = cursor.fetchone()
    if not row or row[0] == 0:
        return {}

    n, n_passed, avg_yes, first_y, last_y = row
    aggregate = {
        'n': n,
        'passed': n_passed,
        'pass_rate': round(100 * n_passed / n, 1) if n else None,
        'avg_yes': round(avg_yes, 1) if avg_yes else None,
        'first_year': first_y,
        'last_year': last_y,
        'matched_flags': flags,
    }

    # Recent matching measures (richer detail)
    cursor = conn.execute(f"""
        SELECT year, ballot_name, description, pct_yes, passed,
               measure_type, is_close, is_very_close
        FROM ca_historical_measures
        WHERE {flag_clause}
        ORDER BY year DESC
        LIMIT ?
    """, (limit,))

    cols = [d[0] for d in cursor.description]
    recent = []
    for r in cursor.fetchall():
        rec = dict(zip(cols, r))
        recent.append({
            'year': rec['year'],
            'name': rec['ballot_name'],
            'description': (rec.get('description') or '')[:120],
            'pct_yes': round(rec['pct_yes'], 1) if rec.get('pct_yes') is not None else None,
            'passed': rec.get('passed'),
            'measure_type': rec.get('measure_type'),
            'is_close': bool(rec.get('is_close')),
            'is_very_close': bool(rec.get('is_very_close')),
        })

    return {'aggregate': aggregate, 'recent': recent}


def _build_cpi_table_for_context(context: Dict) -> str:
    """Collect the years referenced by similar_measures + jurisdiction history
    and format a compact CPI table for the synthesis prompt."""
    from src.research.sources.cpi import cpi_table_for_prompt
    years = set()
    for s in context.get('similar_measures') or []:
        if s.get('year'):
            years.add(s['year'])
    for h in context.get('same_jurisdiction_history') or []:
        if h.get('year'):
            years.add(h['year'])
    return cpi_table_for_prompt(sorted(years))


def _find_similar_measures(measure: Dict, conn: sqlite3.Connection,
                           top_k: int = 20, return_k: int = 10) -> List[Dict]:
    """Find semantically similar past measures using embeddings, then enrich
    each with title/ballot_question/outcome from the DB.

    Per the briefing spec: similar_measures must be concrete past measures
    with content and outcomes, not just ids+scores.
    """
    emb_path = DATA_DIR / "embeddings.npz"
    meta_path = DATA_DIR / "embedding_metadata.json"

    if not emb_path.exists() or not meta_path.exists():
        logger.warning("Embeddings not available for similarity search")
        return []

    try:
        import json
        embeddings = np.load(str(emb_path))['embeddings']
        with open(meta_path) as f:
            meta = json.load(f)
        emb_ids = meta.get('measure_ids', [])

        # Build text for this measure
        text = ' '.join(filter(None, [
            str(measure.get('title', '')),
            str(measure.get('summary_text', '')),
            str(measure.get('ballot_question', '')),
            str(measure.get('description', '')),
        ])).strip()

        if len(text) < 10:
            return []

        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        query_emb = model.encode([text])[0]

        # Cosine similarity
        norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_emb)
        norms[norms == 0] = 1e-10
        sims = embeddings @ query_emb / norms

        top_indices = np.argsort(sims)[-top_k:][::-1]

        # Collect candidate ids in rank order
        candidates: List[Dict] = []
        for idx in top_indices:
            if sims[idx] < 0.3:
                break
            if idx < len(emb_ids):
                candidates.append({
                    'measure_id': emb_ids[idx],
                    'similarity': round(float(sims[idx]), 3),
                })

        if not candidates:
            return []

        # Don't include the same measure as a "similar" hit
        self_id = measure.get('measure_id')
        candidates = [c for c in candidates if c['measure_id'] != self_id]

        # Enrich with DB content
        enriched = _enrich_similar_measures(candidates[:return_k * 2], conn)

        # Cap at return_k after enrichment (some candidates may not resolve)
        return enriched[:return_k]

    except ImportError:
        logger.warning("sentence-transformers not available")
        return []
    except Exception as e:
        logger.warning(f"Error in similarity search: {e}")
        return []


def _normalize_percent_yes(pct):
    """Normalize percent_yes to 0-100 scale.

    DB has mixed scales: most rows store 0-100, but ~1,679 rows (CEDA + NCSL)
    store 0-1 fractions. We treat 0 < pct <= 1 as a fraction and rescale.
    Real measures with literal 1% YES are vanishingly rare, so the false-
    positive cost is low compared to the cost of misreading a 0.55 fraction
    as "0.55%" in LLM prompts.
    """
    if pct is None:
        return None
    if 0 < pct <= 1:
        return pct * 100
    return pct


def _enrich_similar_measures(candidates: List[Dict],
                             conn: sqlite3.Connection) -> List[Dict]:
    """Look up content + outcome for each candidate similar measure.

    Preserves rank order from the candidate list. Drops candidates whose
    measure_id doesn't resolve to a row.
    """
    if not candidates:
        return []

    ids = [c['measure_id'] for c in candidates]
    placeholders = ','.join('?' * len(ids))
    query = f"""
        SELECT measure_id, year, county, title, ballot_question,
               percent_yes, passed, category_type, category_topic
        FROM measures
        WHERE measure_id IN ({placeholders})
            AND is_active = 1 AND is_duplicate = 0
    """
    cursor = conn.execute(query, ids)
    columns = [d[0] for d in cursor.description]
    by_id: Dict[str, Dict] = {}
    for row in cursor.fetchall():
        rec = dict(zip(columns, row))
        # Same measure_id can repeat across (year, source); keep the first hit
        by_id.setdefault(rec['measure_id'], rec)

    enriched: List[Dict] = []
    for cand in candidates:
        rec = by_id.get(cand['measure_id'])
        if not rec:
            continue
        py = _normalize_percent_yes(rec.get('percent_yes'))
        is_close = (py is not None and abs(py - 50) < 5)
        enriched.append({
            'measure_id': cand['measure_id'],
            'similarity': cand['similarity'],
            'year': rec.get('year'),
            'county': rec.get('county'),
            'title': rec.get('title'),
            'ballot_question': rec.get('ballot_question'),
            'percent_yes': round(py, 1) if py is not None else None,
            'passed': rec.get('passed'),
            'category_type': rec.get('category_type'),
            'category_topic': rec.get('category_topic'),
            'is_close': is_close,
        })
    return enriched


def _get_topic_stats(measure: Dict, conn: sqlite3.Connection) -> Dict:
    """Get pass rates and margins for measures with similar topic/type."""
    cat_type = measure.get('category_type')
    cat_topic = measure.get('category_topic')

    stats = {}

    if cat_type:
        cursor = conn.execute("""
            SELECT COUNT(*) as n,
                SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END) as passed,
                AVG(CASE
                    WHEN percent_yes > 0 AND percent_yes <= 1 THEN percent_yes * 100
                    WHEN percent_yes BETWEEN 0 AND 100 THEN percent_yes
                END) as avg_yes
            FROM measures
            WHERE is_active=1 AND is_duplicate=0 AND passed IS NOT NULL
                AND category_type = ?
        """, (cat_type,))
        row = cursor.fetchone()
        if row and row[0] > 0:
            stats['by_type'] = {
                'type': cat_type,
                'total': row[0],
                'passed': row[1],
                'pass_rate': round(100 * row[1] / row[0], 1),
                'avg_yes': round(row[2], 1) if row[2] else None,
            }

    if cat_topic:
        cursor = conn.execute("""
            SELECT COUNT(*) as n,
                SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END) as passed,
                AVG(CASE
                    WHEN percent_yes > 0 AND percent_yes <= 1 THEN percent_yes * 100
                    WHEN percent_yes BETWEEN 0 AND 100 THEN percent_yes
                END) as avg_yes
            FROM measures
            WHERE is_active=1 AND is_duplicate=0 AND passed IS NOT NULL
                AND category_topic = ?
        """, (cat_topic,))
        row = cursor.fetchone()
        if row and row[0] > 0:
            stats['by_topic'] = {
                'topic': cat_topic,
                'total': row[0],
                'passed': row[1],
                'pass_rate': round(100 * row[1] / row[0], 1),
                'avg_yes': round(row[2], 1) if row[2] else None,
            }

    # Threshold-bucketed pass rates within this category_type
    if cat_type:
        stats['by_threshold'] = _get_topic_stats_by_threshold(cat_type, conn)

    return stats


def _get_topic_stats_by_threshold(cat_type: str, conn: sqlite3.Connection) -> List[Dict]:
    """Split this category_type's pass rates by threshold class.

    Some category_types (notably GO Bond) span thresholds based on topic.
    This splits the population into 50% / 55% / 66.67% buckets so the LLM
    can say 'GO bonds for education at 55% pass 88%; non-education at
    66.67% pass 41%' rather than mushing them.
    """
    cursor = conn.execute("""
        SELECT category_topic, passed, percent_yes
        FROM measures
        WHERE is_active=1 AND is_duplicate=0 AND passed IS NOT NULL
            AND category_type = ?
    """, (cat_type,))

    buckets: Dict[float, Dict] = {}
    for cat_topic, passed, py in cursor.fetchall():
        threshold = _classify_threshold(cat_type, cat_topic)
        b = buckets.setdefault(threshold, {'total': 0, 'passed': 0, 'sum_yes': 0.0, 'n_yes': 0})
        b['total'] += 1
        if passed == 1:
            b['passed'] += 1
        py_norm = _normalize_percent_yes(py)
        if py_norm is not None and 0 <= py_norm <= 100:
            b['sum_yes'] += py_norm
            b['n_yes'] += 1

    out = []
    for threshold, b in sorted(buckets.items()):
        if b['total'] < 5:  # too few to report
            continue
        out.append({
            'threshold': threshold,
            'threshold_label': f"{threshold:.0f}%" if threshold == 50 else f"{threshold}%",
            'total': b['total'],
            'passed': b['passed'],
            'pass_rate': round(100 * b['passed'] / b['total'], 1),
            'avg_yes': round(b['sum_yes'] / b['n_yes'], 1) if b['n_yes'] else None,
        })
    return out


# Words/phrases in the ballot question that indicate a general-purpose tax
# (revenue to general fund). Per CA Prop 218, these need only a simple
# majority (50%) — not the 66.67% supermajority that special-purpose taxes
# require. Both Opus and Sonnet flagged this issue independently in the
# bakeoff: our category_type-only classifier was returning 66.67% for these.
GENERAL_FUND_PATTERNS = [
    'general fund',
    'general government',
    'general municipal',
    'general local',
    'general purposes',
    'general city services',
    'general county services',
    'general government use',
    'discretionary',
]


def _classify_threshold(category_type: Optional[str],
                        category_topic: Optional[str] = None,
                        ballot_question: Optional[str] = None) -> float:
    """Return the vote threshold (50.0 / 55.0 / 66.67) for a measure type.

    Shared by threshold context and threshold-bucketed topic stats so both
    use the same rule. When ballot_question is provided and indicates a
    general-purpose tax, downgrade the default 66.67% to 50.0% per Prop 218.
    """
    cat_type = (category_type or '').lower()
    if cat_type in ('ordinance', 'charter amendment', 'advisory', 'recall', 'gann limit'):
        return 50.0
    if cat_type in ('sales tax', 'utility tax', 'business tax', 'transient occupancy tax',
                    'miscellaneous tax', 'property tax'):
        # Default for these categories is 66.67% (special-purpose tax). But
        # if the ballot question says the revenue goes to the general fund,
        # it's a general-purpose tax and only needs 50%.
        if ballot_question:
            bq_lower = ballot_question.lower()
            if any(p in bq_lower for p in GENERAL_FUND_PATTERNS):
                return 50.0
        return 66.67
    if cat_type in ('go bond',):
        return 55.0 if 'education' in str(category_topic or '').lower() else 66.67
    return 50.0


def _get_threshold_context(measure: Dict, conn: sqlite3.Connection) -> Dict:
    """Determine what threshold applies and how similar measures fare."""
    threshold = _classify_threshold(
        measure.get('category_type'),
        measure.get('category_topic'),
        measure.get('ballot_question'),
    )

    # Trap rate for this threshold
    cursor = conn.execute("""
        SELECT COUNT(*) as total,
            SUM(CASE WHEN percent_yes > 50 AND passed = 0 THEN 1 ELSE 0 END) as trapped
        FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND percent_yes BETWEEN 0 AND 100
            AND passed IS NOT NULL
            AND category_type = ?
    """, (measure.get('category_type', ''),))
    row = cursor.fetchone()
    trap_rate = round(100 * row[1] / row[0], 1) if row and row[0] > 0 else 0

    return {
        'threshold': threshold,
        'threshold_label': f"{threshold}%" if threshold == 50 else f"{threshold}% supermajority",
        'trap_rate': trap_rate,
        'trap_count': row[1] if row else 0,
    }


def _get_same_jurisdiction_history(measure: Dict, conn: sqlite3.Connection,
                                   limit: int = 10) -> List[Dict]:
    """Past measures in the same jurisdiction with the same category_type.

    Returns most recent first. Empty list when county or category_type missing.
    """
    county = measure.get('county')
    cat_type = measure.get('category_type')
    self_id = measure.get('measure_id')
    if not county or not cat_type:
        return []

    cursor = conn.execute("""
        SELECT measure_id, year, title, percent_yes, passed, category_topic
        FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND county = ? AND category_type = ?
            AND (measure_id IS NOT ? OR ? IS NULL)
            AND year < ?
        ORDER BY year DESC, id DESC
        LIMIT ?
    """, (county, cat_type, self_id, self_id, measure.get('year', 9999), limit))

    cols = [d[0] for d in cursor.description]
    history = []
    for row in cursor.fetchall():
        rec = dict(zip(cols, row))
        py = _normalize_percent_yes(rec.get('percent_yes'))
        history.append({
            'measure_id': rec['measure_id'],
            'year': rec['year'],
            'title': rec.get('title'),
            'percent_yes': round(py, 1) if py is not None else None,
            'passed': rec.get('passed'),
            'category_topic': rec.get('category_topic'),
        })
    return history


def _get_same_ballot_companions(measure: Dict, conn: sqlite3.Connection,
                                limit: int = 10) -> List[Dict]:
    """Other measures on the same ballot (same year + county), excluding self.

    For statewide measures this is the rest of the statewide ballot; for
    locals it's the other measures the same voter saw at the polls.
    """
    year = measure.get('year')
    county = measure.get('county')
    self_id = measure.get('measure_id')
    if not year or not county:
        return []

    cursor = conn.execute("""
        SELECT measure_id, title, category_type, category_topic,
               percent_yes, passed
        FROM measures
        WHERE is_active=1 AND is_duplicate=0
            AND year = ? AND county = ?
            AND (measure_id IS NOT ? OR ? IS NULL)
        ORDER BY measure_id
        LIMIT ?
    """, (year, county, self_id, self_id, limit))

    cols = [d[0] for d in cursor.description]
    companions = []
    for row in cursor.fetchall():
        rec = dict(zip(cols, row))
        py = _normalize_percent_yes(rec.get('percent_yes'))
        companions.append({
            'measure_id': rec['measure_id'],
            'title': rec.get('title'),
            'category_type': rec.get('category_type'),
            'category_topic': rec.get('category_topic'),
            'percent_yes': round(py, 1) if py is not None else None,
            'passed': rec.get('passed'),
        })
    return companions


def _get_temporal_trend(measure: Dict, conn: sqlite3.Connection) -> List[Dict]:
    """Get pass rate trend by decade for this measure's type."""
    cat_type = measure.get('category_type')
    if not cat_type:
        return []

    cursor = conn.execute("""
        SELECT decade,
            COUNT(*) as n,
            SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END) as passed,
            AVG(CASE
                    WHEN percent_yes > 0 AND percent_yes <= 1 THEN percent_yes * 100
                    WHEN percent_yes BETWEEN 0 AND 100 THEN percent_yes
                END) as avg_yes
        FROM measures
        WHERE is_active=1 AND is_duplicate=0 AND passed IS NOT NULL
            AND category_type = ? AND decade IS NOT NULL
        GROUP BY decade
        ORDER BY decade
    """, (cat_type,))

    trend = []
    for row in cursor.fetchall():
        if row[1] >= 3:  # Minimum sample
            trend.append({
                'decade': row[0],
                'n': row[1],
                'pass_rate': round(100 * row[2] / row[1], 1),
                'avg_yes': round(row[3], 1) if row[3] else None,
            })

    return trend
