"""
Campaign finance source — pulls real proponent/opponent committees and top
donors from the combined v2 (monetary contributions) + v3 (loans + in-kind
+ independent expenditures) databases for the synthesis prompt.

Covers statewide propositions only. The briefing spec requires real names
(not 'Not yet available') and named donors when available; this is the
data path that makes that requirement satisfiable for statewide measures
without scraping anything per-measure.

Uses FinanceDatabase.get_combined_summary + get_combined_top_donors — both
key on measure_db_id and stitch v2 + v3 sources internally.
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
          'source': 'CAL-ACCESS Campaign Finance (combined v2 monetary + v3 non-monetary)',
          'extracted': {
            'support_summary': '...',
            'support_top_donors': '...',
            'oppose_summary': '...',
            'oppose_top_donors': '...',
          }
        }
    """
    # Statewide-only — local measures aren't in the finance databases
    if (measure.get('county') or '').strip().lower() != 'statewide':
        return None

    try:
        from src.finance.operations import FinanceDatabase
    except ImportError as e:
        logger.debug("Finance module unavailable: %s", e)
        return None

    measure_db_id = measure.get('id')
    if measure_db_id is None:
        return None

    db = FinanceDatabase()
    try:
        summary_rows = db.get_combined_summary(int(measure_db_id))
        if not summary_rows:
            return None
        top_donors = db.get_combined_top_donors(int(measure_db_id), limit=10)
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
            total = s.get('total_receipts') or 0
            monetary = s.get('monetary_amount') or 0
            non_monetary = s.get('non_monetary_amount') or 0
            n_comm = s.get('n_committees')
            top5 = s.get('top5_share')
            hhi = s.get('hhi')
            # Lead with the headline total, then break down the
            # monetary vs non-monetary split for transparency.
            line = f"{label} side: ${total:,.0f} total reportable money"
            if monetary > 0 and non_monetary > 0:
                line += (
                    f" (${monetary:,.0f} direct receipts "
                    f"+ ${non_monetary:,.0f} loans/in-kind/IE)."
                )
            else:
                line += "."
            if n_comm:
                line += f" {n_comm} committee(s)/filer(s)."
            if top5 is not None:
                line += f" Top 5 donors = {top5:.0f}% of total."
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
        'source': 'CAL-ACCESS Campaign Finance (combined v2 monetary + v3 non-monetary)',
        'extracted': extracted,
    }
