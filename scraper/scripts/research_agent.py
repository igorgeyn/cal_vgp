#!/usr/bin/env python3
"""
CalBallot Research Agent — builds comprehensive briefings for ballot measures.

For each pending/upcoming measure, the agent:
1. Gathers historical context from the CalBallot database
2. (standard+) Fetches official source documents
3. (standard+) Extracts structured facts via LLM
4. Synthesizes everything into a structured briefing
5. Writes results to DB + generates standalone markdown report

Usage:
    python scripts/research_agent.py --year 2026 --budget minimal
    python scripts/research_agent.py --measure-id ACA_13 --budget standard
    python scripts/research_agent.py --year 2026 --budget standard --resume
    python scripts/research_agent.py --year 2026 --dry-run
"""
import sys
import sqlite3
import json
import argparse
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH, DATA_DIR
from src.research.sources.historical import get_historical_context
from src.research.sources.finance import get_finance_facts
from src.research.extractors.llm import LLMExtractor
from src.research.output.markdown import save_report
from src.research.spec import load_briefing_spec

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CHECKPOINT_PATH = DATA_DIR / "research_checkpoint.json"


def get_pending_measures(conn: sqlite3.Connection, year: int = None,
                         measure_id: str = None) -> List[Dict]:
    """Get measures needing research."""
    query = """
        SELECT id, year, county, measure_id, measure_letter,
               title, ballot_question, description, summary_text,
               category_type, category_topic,
               passed, percent_yes, data_source,
               source_url, pdf_url,
               research_status
        FROM measures
        WHERE is_active = 1 AND is_duplicate = 0
    """
    params = []

    if measure_id:
        query += " AND measure_id LIKE ?"
        params.append(f"%{measure_id}%")
    elif year:
        query += " AND year >= ?"
        params.append(year)
    else:
        query += " AND year >= 2025"

    query += " ORDER BY year DESC, id"

    cursor = conn.execute(query, params)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def research_measure_minimal(measure: Dict, conn: sqlite3.Connection,
                              extractor: LLMExtractor) -> Dict:
    """Minimal research: historical context + synthesis from existing data only."""
    logger.info(f"  Researching (minimal): {measure['title'][:50]}...")

    # Get historical context from our database
    historical = get_historical_context(measure, conn)

    # Collect what we already have
    facts = []
    if measure.get('summary_text'):
        facts.append({
            'source': 'CalBallot existing summary',
            'extracted': {'what_it_does': measure['summary_text']}
        })
    if measure.get('ballot_question'):
        facts.append({
            'source': 'Official ballot question',
            'extracted': {'what_it_does': measure['ballot_question'][:500]}
        })
    if measure.get('description'):
        facts.append({
            'source': 'Measure description',
            'extracted': {'what_it_does': measure['description'][:1000]}
        })

    # Real campaign finance for statewide measures (CAL-ACCESS)
    finance_fact = get_finance_facts(measure)
    if finance_fact:
        facts.append(finance_fact)

    # Synthesize
    briefing = extractor.synthesize_briefing(measure, facts, historical)

    sources = [{'name': 'CalBallot Database', 'url': 'https://cal-vgp.igorgeyn.com'}]
    if finance_fact:
        sources.append({'name': 'CAL-ACCESS Campaign Finance', 'url': 'https://cal-access.sos.ca.gov/'})

    return {
        'briefing': briefing,
        'sources': sources,
        'historical': historical,
        'depth': 'minimal',
    }


def research_measure_standard(measure: Dict, conn: sqlite3.Connection,
                               extractor: LLMExtractor) -> Dict:
    """Standard research: fetch official sources + extract + synthesize."""
    logger.info(f"  Researching (standard): {measure['title'][:50]}...")

    # Start with historical context
    historical = get_historical_context(measure, conn)

    facts = []
    sources_consulted = [{'name': 'CalBallot Database', 'url': 'https://cal-vgp.igorgeyn.com'}]

    # Existing data
    if measure.get('summary_text'):
        facts.append({
            'source': 'CalBallot existing summary',
            'extracted': {'what_it_does': measure['summary_text']}
        })

    # Real campaign finance for statewide measures (CAL-ACCESS)
    finance_fact = get_finance_facts(measure)
    if finance_fact:
        facts.append(finance_fact)
        sources_consulted.append({'name': 'CAL-ACCESS Campaign Finance', 'url': 'https://cal-access.sos.ca.gov/'})

    # Fetch official sources
    from src.utils.external_links import generate_external_links
    links = generate_external_links(measure)

    import requests

    for link in links:
        if link.get('confidence') != 'high':
            continue

        url = link.get('url', '')
        source_name = link.get('source', 'Unknown')

        try:
            logger.info(f"    Fetching {source_name}...")
            resp = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; CalBallot-Research/1.0)'
            })
            if resp.status_code != 200:
                logger.warning(f"    {source_name}: HTTP {resp.status_code}")
                continue

            # Extract text from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.content, 'html.parser')
            # Remove scripts, styles
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            text = soup.get_text(' ', strip=True)[:6000]

            if len(text) < 100:
                continue

            # Extract structured facts via LLM
            extracted = extractor.extract_from_document(
                text, source_name, measure.get('title', '')
            )

            if extracted:
                facts.append({'source': source_name, 'extracted': extracted})
                sources_consulted.append({'name': source_name, 'url': url})

            time.sleep(1)  # Rate limit between fetches

        except Exception as e:
            logger.warning(f"    Error fetching {source_name}: {e}")

    # Synthesize
    briefing = extractor.synthesize_briefing(measure, facts, historical)

    return {
        'briefing': briefing,
        'sources': sources_consulted,
        'historical': historical,
        'depth': 'standard',
    }


def write_results(db, measure_id: int, result: Dict,
                  spec_version: str = "missing", spec_hash: str = "missing") -> None:
    """Write research results to the database via update_measure() (respects field protection).

    research_sources is persisted as a structured JSON object:
        {"sources": [...], "spec_version": "0.1", "spec_hash": "abc..."}
    so stale briefings can be identified by spec hash.
    """
    from src.database.operations import Database

    briefing = result.get('briefing', {})
    briefing_text = briefing.get('briefing_summary', '')

    # Check for failure indicators
    is_failed = (not briefing_text or
                 'failed' in briefing_text.lower()[:50] or
                 'error' in briefing_text.lower()[:50] or
                 len(briefing_text) < 20)

    sources_payload = {
        'sources': [s.get('name', str(s)) for s in result.get('sources', [])],
        'spec_version': spec_version,
        'spec_hash': spec_hash,
    }

    updates = {
        'briefing_text': briefing_text if not is_failed else None,
        'fiscal_impact': briefing.get('fiscal_impact'),
        'pro_arguments': json.dumps(briefing.get('pro_arguments', [])),
        'con_arguments': json.dumps(briefing.get('con_arguments', [])),
        'proponents': json.dumps(briefing.get('proponents', [])),
        'opponents': json.dumps(briefing.get('opponents', [])),
        'research_status': 'failed' if is_failed else 'complete',
        'research_depth': result.get('depth', 'minimal'),
        'research_updated_at': datetime.now().isoformat(),
        'research_sources': json.dumps(sources_payload),
    }

    # Strip None values so update_measure() protection works
    updates = {k: v for k, v in updates.items() if v is not None and v != ''}

    db.update_measure(measure_id, updates)


def save_checkpoint(processed_ids: set, stats: Dict):
    checkpoint = {
        "processed_ids": list(processed_ids),
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    }
    with open(CHECKPOINT_PATH, 'w') as f:
        json.dump(checkpoint, f)


def load_checkpoint() -> Optional[Dict]:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, 'r') as f:
            return json.load(f)
    return None


def main():
    parser = argparse.ArgumentParser(description="CalBallot Research Agent")
    parser.add_argument("--year", type=int, default=2026, help="Research measures from this year onward")
    parser.add_argument("--measure-id", type=str, help="Research a specific measure")
    parser.add_argument("--budget", choices=["minimal", "standard", "deep"], default="standard",
                        help="Research depth (controls API cost)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be researched")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514",
                        help="LLM model to use")
    parser.add_argument("--spec-path", type=str, default=None,
                        help="Path to the governing briefing spec (default: plans/briefing-spec.md). "
                             "Overrides BRIEFING_SPEC_PATH env var.")
    args = parser.parse_args()

    from src.database.operations import Database

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    db = Database(DB_PATH)
    db.connect()

    measures = get_pending_measures(conn, year=args.year, measure_id=args.measure_id)
    logger.info(f"Found {len(measures)} measures to research")

    if args.dry_run:
        print(f"\nWould research {len(measures)} measures at '{args.budget}' depth:")
        for m in measures:
            status = m.get('research_status', 'none')
            print(f"  {m['year']} {m['county']:10s} {str(m['measure_id']):25s} research={status} | {str(m['title'])[:50]}")
        return

    # Resume support
    processed_ids = set()
    if args.resume:
        cp = load_checkpoint()
        if cp:
            processed_ids = set(cp.get("processed_ids", []))
            logger.info(f"Resuming: {len(processed_ids)} already done")

    measures = [m for m in measures if m['id'] not in processed_ids]
    logger.info(f"Will research {len(measures)} measures")

    # Load the governing briefing spec
    from pathlib import Path as _Path
    spec_path = _Path(args.spec_path) if args.spec_path else None
    spec_text, spec_version, spec_hash = load_briefing_spec(spec_path)

    # Initialize LLM extractor
    extractor = LLMExtractor(
        model=args.model,
        spec_text=spec_text,
        spec_version=spec_version,
        spec_hash=spec_hash,
    )

    stats = {"processed": 0, "errors": 0, "start": datetime.now().isoformat()}

    try:
        for i, measure in enumerate(measures):
            try:
                # Choose research function based on budget
                if args.budget == "minimal":
                    result = research_measure_minimal(measure, conn, extractor)
                else:
                    result = research_measure_standard(measure, conn, extractor)

                # Write to DB via protected update_measure()
                write_results(db, measure['id'], result,
                              spec_version=extractor.spec_version,
                              spec_hash=extractor.spec_hash)
                db.conn.commit()

                # Generate standalone report
                report_path = save_report(measure, result['briefing'], result['sources'])
                logger.info(f"  [{i+1}/{len(measures)}] Done. Report: {report_path}")

                processed_ids.add(measure['id'])
                stats["processed"] += 1

                # Checkpoint every 5
                if stats["processed"] % 5 == 0:
                    save_checkpoint(processed_ids, stats)

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"  Error researching {measure.get('measure_id')}: {e}")
                if "overloaded" in str(e).lower() or "529" in str(e):
                    logger.info("  API overloaded, waiting 60s...")
                    time.sleep(60)

    except KeyboardInterrupt:
        logger.info("Interrupted. Saving checkpoint...")
        save_checkpoint(processed_ids, stats)

    finally:
        conn.close()

    stats["end"] = datetime.now().isoformat()
    save_checkpoint(processed_ids, stats)

    logger.info(f"\nResearch complete! Processed: {stats['processed']}, Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
