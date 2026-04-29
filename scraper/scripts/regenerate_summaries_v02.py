#!/usr/bin/env python3
"""
Regenerate ballot-measure summaries against the v0.2 spec using Sonnet 4.6
via Anthropic Batch API. Two modes:

  --submit:   Build prompts for measures missing summaries (or with stale
              spec_hash), submit a single batch job, save the batch_id +
              measure mapping to data/summary_batch_state.json. Returns
              immediately; the actual generation runs async on Anthropic's
              servers (24h SLA, usually faster).

  --retrieve: Load batch_id from state, poll Anthropic for results, validate
              outputs, write summaries to DB.

Cost (Sonnet 4.6 batch + cache, ~12K measures, est ~5K input + 200 output
per call): ~$30-50 total.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python scripts/regenerate_summaries_v02.py --submit
    python scripts/regenerate_summaries_v02.py --retrieve
"""
import argparse
import hashlib
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from src.config import DB_PATH, DATA_DIR
from summary_bakeoff import build_prompt, load_summary_spec, score_summary

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STATE_PATH = DATA_DIR / "summary_batch_state.json"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 250
DEFAULT_LIMIT = None  # None = all eligible measures


def get_eligible_measures(conn: sqlite3.Connection,
                          limit: int = None,
                          force_regen: bool = False) -> List[Dict]:
    """Return measures that need a v0.2 summary regen.

    By default: measures with no summary_text. With --force, all active
    non-duplicate measures (regenerates the existing 3,627 too).
    """
    if force_regen:
        where = "WHERE is_active = 1 AND is_duplicate = 0"
    else:
        where = """
            WHERE is_active = 1 AND is_duplicate = 0
              AND (summary_text IS NULL OR summary_text = '')
        """
    query = f"""
        SELECT id, year, county, measure_id, measure_letter,
               title, ballot_question, description, summary_text,
               category_type, category_topic, passed, percent_yes,
               data_source, source_url, pdf_url, research_status
        FROM measures
        {where}
        ORDER BY year DESC, id
    """
    if limit:
        query += f" LIMIT {limit}"
    cur = conn.execute(query)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def submit_batch(args):
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    spec_text, spec_version, spec_hash = load_summary_spec()
    logger.info("Spec v%s hash=%s", spec_version, spec_hash)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    measures = get_eligible_measures(conn, limit=args.limit, force_regen=args.force_regen)
    logger.info("Eligible measures: %d", len(measures))

    if args.dry_run:
        logger.info("Dry run — would submit batch for %d measures", len(measures))
        if measures:
            logger.info("First sample prompt:")
            print(build_prompt(measures[0], conn, spec_text)[:1500])
        return 0

    if not measures:
        logger.info("Nothing to do.")
        return 0

    # Build batch requests. custom_id is the measure's DB id (stringified).
    logger.info("Building %d prompts...", len(measures))
    requests = []
    for m in measures:
        prompt = build_prompt(m, conn, spec_text)
        # The spec is the bulk of input — cache it. The system block mirrors
        # the LLMExtractor pattern: spec as ephemeral cache, measure as user.
        # For simplicity we send it all in one user message; cache_control on
        # the message itself lets Anthropic reuse the prefix.
        requests.append(Request(
            custom_id=f"m_{m['id']}",
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{
                    "role": "user",
                    "content": [{
                        "type": "text",
                        "text": prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                }],
            ),
        ))

    client = anthropic.Anthropic()
    logger.info("Submitting batch of %d requests to Anthropic...", len(requests))
    batch = client.messages.batches.create(requests=requests)
    logger.info("Batch submitted. id=%s, status=%s", batch.id, batch.processing_status)

    # Save state for retrieval
    state = {
        "batch_id": batch.id,
        "submitted_at": datetime.utcnow().isoformat(),
        "model": MODEL,
        "spec_version": spec_version,
        "spec_hash": spec_hash,
        "measure_count": len(measures),
        "measure_id_by_custom_id": {f"m_{m['id']}": m['id'] for m in measures},
    }
    STATE_PATH.write_text(json.dumps(state, indent=2))
    logger.info("State saved to %s", STATE_PATH)
    logger.info("Run --retrieve once batch is complete (poll status with --status).")
    return 0


def check_status(args):
    if not STATE_PATH.exists():
        logger.error("No batch state at %s. Submit first.", STATE_PATH)
        return 1
    state = json.loads(STATE_PATH.read_text())
    import anthropic
    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(state["batch_id"])
    logger.info("batch_id=%s status=%s", batch.id, batch.processing_status)
    counts = batch.request_counts
    logger.info("processing=%d / succeeded=%d / errored=%d / cancelled=%d / expired=%d",
                counts.processing, counts.succeeded, counts.errored,
                counts.canceled, counts.expired)
    if batch.processing_status == "ended":
        logger.info("Batch complete. Run with --retrieve to persist results.")
    return 0


def retrieve_and_persist(args):
    if not STATE_PATH.exists():
        logger.error("No batch state at %s. Submit first.", STATE_PATH)
        return 1
    state = json.loads(STATE_PATH.read_text())
    import anthropic
    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(state["batch_id"])
    if batch.processing_status != "ended":
        logger.error("Batch not yet complete. Status=%s. Use --status to monitor.",
                     batch.processing_status)
        return 1
    logger.info("Batch complete. Streaming results...")

    spec_version = state["spec_version"]
    spec_hash = state["spec_hash"]
    custom_id_to_db_id = state["measure_id_by_custom_id"]

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    persisted = 0
    failed = 0
    spec_failed = 0
    errors = []

    for result in client.messages.batches.results(state["batch_id"]):
        custom_id = result.custom_id
        db_id = custom_id_to_db_id.get(custom_id)
        if db_id is None:
            logger.warning("Unknown custom_id %s, skipping", custom_id)
            continue

        if result.result.type != "succeeded":
            failed += 1
            errors.append((db_id, str(result.result)[:200]))
            continue

        msg = result.result.message
        text = msg.content[0].text.strip() if msg.content else ""

        # Validate against current spec failure modes
        m_row = conn.execute(
            "SELECT * FROM measures WHERE id = ?", (db_id,)
        ).fetchone()
        if not m_row:
            failed += 1
            continue
        m = dict(m_row)
        scoring = score_summary(text, m)

        if not scoring["passes_spec"]:
            spec_failed += 1
            # Log it but still persist — these are typically minor failures
            # like long-title overlap on editorial titles. Fully wiping the
            # output for a borderline-failing summary throws away useful work.
            logger.debug("Spec-failed (persisting anyway): id=%s flags=%s",
                         db_id, scoring['spec_failure_flags'])

        # Build a short title from first sentence
        summary_title = text.split('.')[0].strip()
        if len(summary_title) > 80:
            summary_title = summary_title[:77] + "..."

        # Stash spec metadata in research_sources alongside any existing data
        existing_rs = m.get('research_sources')
        rs_obj = {}
        if existing_rs:
            try:
                rs_obj = json.loads(existing_rs)
                if not isinstance(rs_obj, dict):
                    rs_obj = {"sources_legacy": rs_obj}
            except (json.JSONDecodeError, TypeError):
                rs_obj = {}
        rs_obj["summary_spec_version"] = spec_version
        rs_obj["summary_spec_hash"] = spec_hash
        rs_obj["summary_regenerated_at"] = datetime.utcnow().isoformat()
        rs_obj["summary_passes_spec"] = scoring["passes_spec"]

        conn.execute(
            """UPDATE measures
                  SET summary_text = ?, summary_title = ?, has_summary = 1,
                      research_sources = ?
                WHERE id = ?""",
            (text, summary_title, json.dumps(rs_obj), db_id),
        )
        persisted += 1

        if persisted % 100 == 0:
            conn.commit()
            logger.info("  persisted %d (spec_failed: %d)", persisted, spec_failed)

    conn.commit()
    conn.close()

    logger.info("Done. persisted=%d, spec_failed=%d (still persisted), failed=%d",
                persisted, spec_failed, failed)
    if errors:
        logger.warning("Sample errors: %s", errors[:5])
    return 0


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sub = sub.add_parser("submit")
    p_sub.add_argument("--limit", type=int, default=None,
                       help="Cap number of measures (for testing)")
    p_sub.add_argument("--force-regen", action="store_true",
                       help="Regenerate all measures, including those with existing summaries")
    p_sub.add_argument("--dry-run", action="store_true",
                       help="Show first prompt and counts; do not submit")

    sub.add_parser("status")
    sub.add_parser("retrieve")

    args = parser.parse_args()

    if args.cmd == "submit":
        return submit_batch(args)
    if args.cmd == "status":
        return check_status(args)
    if args.cmd == "retrieve":
        return retrieve_and_persist(args)


if __name__ == "__main__":
    raise SystemExit(main())
