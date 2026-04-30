#!/usr/bin/env python3
"""
Batch generate summaries for ballot measures using Claude Sonnet.
Processes Tier A (ballot_question) and Tier B (description) measures.

Usage:
    ANTHROPIC_API_KEY=sk-... python scripts/generate_summaries_batch.py
    ANTHROPIC_API_KEY=sk-... python scripts/generate_summaries_batch.py --limit 10 --dry-run
"""
import sys
import sqlite3
import time
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"
CHECKPOINT_PATH = Path(__file__).parent.parent / "data" / "summary_checkpoint.json"

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 150
BATCH_SIZE = 50
RATE_LIMIT_DELAY = 0.5  # seconds between API calls (increased to avoid 529s)


def get_measures_needing_summaries(conn, limit=None):
    """Get measures that need summaries — Tier A (ballot text), B (description), C (long title)."""
    query = """
        SELECT id, year, county, measure_letter, measure_id,
               ballot_question, description, title,
               category_type, category_topic, passed, percent_yes
        FROM measures
        WHERE is_active = 1 AND is_duplicate = 0
          AND (has_summary = 0 OR has_summary IS NULL)
          AND (
              (ballot_question IS NOT NULL AND length(ballot_question) > 30)
              OR (description IS NOT NULL AND length(description) > 30)
              OR (title IS NOT NULL AND length(title) > 50)
          )
        ORDER BY
            CASE WHEN ballot_question IS NOT NULL AND length(ballot_question) > 30 THEN 0
                 WHEN description IS NOT NULL AND length(description) > 30 THEN 1
                 ELSE 2 END,
            year DESC, county
    """
    if limit:
        query += f" LIMIT {limit}"
    return conn.execute(query).fetchall()


def _normalize_pct(pct):
    """Normalize percent_yes to 0-100 scale.
    DB has mixed scales — most rows store 0-100 but ~1,679 (CEDA + NCSL)
    historically stored 0-1 fractions. Without normalization, the LLM
    faithfully reproduces "0.4%" in the summary text when the actual
    outcome was 40%. This fix is forward-looking; existing broken
    summaries are cleaned up by a separate one-shot script.
    """
    if pct is None:
        return None
    if 0 < pct <= 1:
        return pct * 100
    return pct


def build_prompt(row):
    """Build the prompt for a single measure."""
    mid, year, county, letter, meas_id, bq, desc, title, ctype, ctopic, passed, pct = row

    # Use ballot question if available, then description, then title
    text = bq if (bq and len(bq) > 30) else (desc if (desc and len(desc) > 30) else title)

    # Normalize percent_yes BEFORE composing the prompt
    pct = _normalize_pct(pct)

    # Build context
    parts = []
    if county:
        parts.append(f"Location: {county}, California")
    if year:
        parts.append(f"Year: {year}")
    if ctype:
        parts.append(f"Type: {ctype}")
    if ctopic:
        parts.append(f"Topic: {ctopic}")
    if passed is not None and pct is not None and 0 <= pct <= 100:
        outcome = "Passed" if passed == 1 else "Failed"
        parts.append(f"Outcome: {outcome} ({pct:.1f}% yes)")

    context = "\n".join(parts)

    return f"""Summarize this California ballot measure in 1-2 neutral sentences.
Focus on what it would do (or did), not persuasive language.
Output only the summary — no preamble, labels, or explanations.

Context:
{context}

Ballot Text:
{text}"""


def generate_summary(client, prompt):
    """Call Claude API and return the summary text."""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text.strip()


def save_checkpoint(processed_ids, stats):
    checkpoint = {
        "processed_ids": list(processed_ids),
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    }
    with open(CHECKPOINT_PATH, 'w') as f:
        json.dump(checkpoint, f)


def load_checkpoint():
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, 'r') as f:
            return json.load(f)
    return None


def main():
    parser = argparse.ArgumentParser(description="Batch generate summaries with Claude Sonnet")
    parser.add_argument("--limit", type=int, help="Limit number of measures")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts without calling API")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    args = parser.parse_args()

    # Verify API key
    import anthropic
    client = anthropic.Anthropic()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    measures = get_measures_needing_summaries(conn, args.limit)
    logger.info(f"Found {len(measures)} measures needing summaries")

    # Resume support
    processed_ids = set()
    if args.resume:
        cp = load_checkpoint()
        if cp:
            processed_ids = set(cp.get("processed_ids", []))
            logger.info(f"Resuming: {len(processed_ids)} already done")

    measures = [m for m in measures if m['id'] not in processed_ids]
    logger.info(f"Will process {len(measures)} measures")

    if args.dry_run:
        for m in measures[:3]:
            print("\n" + "=" * 60)
            print(f"ID={m['id']} | {m['year']} {m['county']} Measure {m['measure_letter']}")
            print("-" * 60)
            print(build_prompt(tuple(m)))
        print(f"\n(Would process {len(measures)} total)")
        return

    stats = {"processed": 0, "errors": 0, "start": datetime.now().isoformat()}
    batch_updates = []

    try:
        for i, row in enumerate(measures):
            mid = row['id']
            try:
                prompt = build_prompt(tuple(row))
                summary = generate_summary(client, prompt)

                # Create a short title from the summary (first sentence, capped at 80 chars)
                summary_title = summary.split('.')[0].strip()
                if len(summary_title) > 80:
                    summary_title = summary_title[:77] + "..."

                batch_updates.append((summary, summary_title, mid))
                processed_ids.add(mid)
                stats["processed"] += 1

                if (i + 1) % 10 == 0:
                    logger.info(f"  [{i+1}/{len(measures)}] Last: {row['year']} {row['county']} {row['measure_letter']}")

                # Commit batch
                if len(batch_updates) >= BATCH_SIZE:
                    conn.executemany(
                        "UPDATE measures SET summary_text = ?, summary_title = ?, has_summary = 1 WHERE id = ?",
                        batch_updates
                    )
                    conn.commit()
                    save_checkpoint(processed_ids, stats)
                    logger.info(f"  Committed batch of {len(batch_updates)}")
                    batch_updates = []

                time.sleep(RATE_LIMIT_DELAY)

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"  Error on ID={mid}: {e}")
                if "rate_limit" in str(e).lower() or "overloaded" in str(e).lower() or "529" in str(e):
                    logger.info("  Rate limited / overloaded, waiting 60s...")
                    time.sleep(60)

        # Final batch
        if batch_updates:
            conn.executemany(
                "UPDATE measures SET summary_text = ?, summary_title = ?, has_summary = 1 WHERE id = ?",
                batch_updates
            )
            conn.commit()
            logger.info(f"  Committed final batch of {len(batch_updates)}")

    except KeyboardInterrupt:
        logger.info("Interrupted! Saving checkpoint...")
        if batch_updates:
            conn.executemany(
                "UPDATE measures SET summary_text = ?, summary_title = ?, has_summary = 1 WHERE id = ?",
                batch_updates
            )
            conn.commit()
        save_checkpoint(processed_ids, stats)
        logger.info("Checkpoint saved. Resume with --resume")

    finally:
        conn.close()

    stats["end"] = datetime.now().isoformat()
    save_checkpoint(processed_ids, stats)

    logger.info(f"\nDone! Processed: {stats['processed']}, Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
