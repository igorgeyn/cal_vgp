"""
Campaign finance source — pulls real proponent/opponent committees and top
donors from finance_statewide_v2.db (CAL-ACCESS data, year-scoped by
finance_campaign_id) for the synthesis prompt.

Covers statewide propositions only. The briefing spec requires real names
(not 'Not yet available') and named donors when available; this is the
data path that makes that requirement satisfiable for statewide measures
without scraping anything per-measure. Resolution from a measure record to
the right finance campaign is handled by `get_campaign_for_measure()` in
`src.finance.operations`, which prefers measure_db_id (always unambiguous)
over (measure_id, year).
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def get_finance_facts(measure: Dict) -> Optional[Dict]:
    """Return a synthesis-ready facts dict for a measure if CAL-ACCESS data
    exists, otherwise None.

    The returned shape matches the existing 'facts' entry contract so it can
    be appended to the facts list in research_agent.py without changing the
    synthesis prompt:

        {
          'source': 'CAL-ACCESS Campaign Finance',
          'extracted': {
            'support_summary': '...',
            'support_top_donors': '...',
            'oppose_summary': '...',
            'oppose_top_donors': '...',
          }
        }
    """
    # Statewide-only — local measures aren't in finance_statewide_v2.db
    if (measure.get('county') or '').strip().lower() != 'statewide':
        return None

    try:
        from src.finance.operations import FinanceDatabase, get_campaign_for_measure
    except ImportError as e:
        logger.debug("Finance module unavailable: %s", e)
        return None

    db = FinanceDatabase()
    try:
        # v2 lookup: resolve the finance_campaign_id from the measure record
        # (uses measure.id when available, falls back to measure_id+year).
        campaign_id = get_campaign_for_measure(db, measure)
        if not campaign_id:
            return None

        summary_rows = db.get_finance_summary(campaign_id)
        if not summary_rows:
            return None

        top_donors = db.get_top_donors(campaign_id, limit=10)
    finally:
        db.close()

    # Index summary + donors by stance
    summary_by_stance = {row['stance']: row for row in summary_rows}
    donors_by_stance = {'support': [], 'oppose': []}
    for d in top_donors:
        donors_by_stance.setdefault(d['stance'], []).append(d)

    extracted = {}

    for stance, label, key_prefix in (
        ('support', 'Yes / Support', 'support'),
        ('oppose', 'No / Oppose', 'oppose'),
    ):
        s = summary_by_stance.get(stance)
        if s:
            total = s['total_receipts'] or 0
            n_comm = s['n_committees'] or 0
            top5 = s.get('top5_share')
            hhi = s.get('hhi')
            line = (
                f"{label} side: {n_comm} committee(s), "
                f"${total:,.0f} total receipts."
            )
            if top5 is not None:
                line += f" Top 5 donors = {top5:.0f}% of receipts."
            if hhi is not None:
                # HHI ranges 0-10000. >2500 is highly concentrated.
                concentration = (
                    "highly concentrated" if hhi > 2500
                    else "moderately concentrated" if hhi > 1500
                    else "diffuse"
                )
                line += f" Donor concentration: {concentration} (HHI {hhi:.0f})."
            extracted[f'{key_prefix}_summary'] = line

        donors = donors_by_stance.get(stance, [])
        if donors:
            donor_lines = []
            for i, d in enumerate(donors[:5], 1):
                name = d.get('donor_name_canon') or 'unnamed'
                amount = d.get('total_amount') or 0
                dtype = d.get('donor_type') or ''
                sector = d.get('donor_sector') or ''
                meta = '/'.join(filter(None, [dtype, sector]))
                meta_str = f" ({meta})" if meta else ''
                donor_lines.append(f"{i}) {name}{meta_str}: ${amount:,.0f}")
            extracted[f'{key_prefix}_top_donors'] = '; '.join(donor_lines)

    if not extracted:
        return None

    return {
        'source': 'CAL-ACCESS Campaign Finance',
        'extracted': extracted,
    }
