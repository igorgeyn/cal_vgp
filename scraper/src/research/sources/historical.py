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
        - similar_measures: list of most similar past measures
        - topic_stats: pass rates and margins for this topic/type
        - county_stats: how this county/statewide votes on similar measures
        - threshold_context: what threshold applies and trap rate
        - temporal_trend: how voting on this topic has changed over time
    """
    context = {}

    # 1. Find semantically similar measures via embeddings
    context['similar_measures'] = _find_similar_measures(measure, top_k)

    # 2. Topic/type statistics
    context['topic_stats'] = _get_topic_stats(measure, conn)

    # 3. Threshold context
    context['threshold_context'] = _get_threshold_context(measure, conn)

    # 4. Temporal trend
    context['temporal_trend'] = _get_temporal_trend(measure, conn)

    return context


def _find_similar_measures(measure: Dict, top_k: int = 20) -> List[Dict]:
    """Find semantically similar past measures using embeddings."""
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

        results = []
        for idx in top_indices:
            if sims[idx] < 0.3:
                break
            if idx < len(emb_ids):
                results.append({
                    'measure_id': emb_ids[idx],
                    'similarity': round(float(sims[idx]), 3),
                })

        return results

    except ImportError:
        logger.warning("sentence-transformers not available")
        return []
    except Exception as e:
        logger.warning(f"Error in similarity search: {e}")
        return []


def _get_topic_stats(measure: Dict, conn: sqlite3.Connection) -> Dict:
    """Get pass rates and margins for measures with similar topic/type."""
    cat_type = measure.get('category_type')
    cat_topic = measure.get('category_topic')

    stats = {}

    if cat_type:
        cursor = conn.execute("""
            SELECT COUNT(*) as n,
                SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END) as passed,
                AVG(CASE WHEN percent_yes BETWEEN 0 AND 100 THEN percent_yes END) as avg_yes
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
                AVG(CASE WHEN percent_yes BETWEEN 0 AND 100 THEN percent_yes END) as avg_yes
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

    return stats


def _get_threshold_context(measure: Dict, conn: sqlite3.Connection) -> Dict:
    """Determine what threshold applies and how similar measures fare."""
    cat_type = (measure.get('category_type') or '').lower()

    # Determine threshold
    if cat_type in ('ordinance', 'charter amendment', 'advisory', 'recall', 'gann limit'):
        threshold = 50.0
    elif cat_type in ('sales tax', 'utility tax', 'business tax', 'transient occupancy tax',
                      'miscellaneous tax', 'property tax'):
        threshold = 66.67
    elif cat_type in ('go bond',):
        threshold = 55.0 if 'education' in str(measure.get('category_topic', '')).lower() else 66.67
    else:
        threshold = 50.0

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


def _get_temporal_trend(measure: Dict, conn: sqlite3.Connection) -> List[Dict]:
    """Get pass rate trend by decade for this measure's type."""
    cat_type = measure.get('category_type')
    if not cat_type:
        return []

    cursor = conn.execute("""
        SELECT decade,
            COUNT(*) as n,
            SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END) as passed,
            AVG(CASE WHEN percent_yes BETWEEN 0 AND 100 THEN percent_yes END) as avg_yes
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
