#!/usr/bin/env python3
"""
Batch generate summaries for ballot measures using Claude Sonnet.

Usage:
    python scripts/generate_summaries.py [--limit N] [--dry-run]

Options:
    --limit N     Only process N measures (for testing)
    --dry-run     Show what would be processed without calling API
    --resume      Resume from last checkpoint
"""

import sqlite3
import subprocess
import time
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"
CHECKPOINT_PATH = Path(__file__).parent.parent / "data" / "summary_checkpoint.json"

# API config
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 150
BATCH_SIZE = 50  # Commit to DB every N summaries
RATE_LIMIT_DELAY = 0.1  # Seconds between API calls


def get_api_key():
    """Get API key from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", subprocess.os.environ.get("USER"),
             "-s", "anthropic_api_key", "-w"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        raise RuntimeError("Could not retrieve API key from Keychain. "
                          "Set it with: security add-generic-password -a \"$USER\" -s anthropic_api_key -w <key>")


def get_measures_needing_summaries(conn, limit=None):
    """Get all measures that need summaries generated."""
    query = """
        SELECT
            id, title, county, year,
            topic_primary, category_type,
            vote_threshold, percent_yes, passed
        FROM measures
        WHERE is_active = 1
          AND (summary_text IS NULL OR summary_text = '')
          AND LENGTH(title) > 50
        ORDER BY LENGTH(title) DESC, year DESC
    """
    if limit:
        query += f" LIMIT {limit}"

    cursor = conn.execute(query)
    return cursor.fetchall()


def build_prompt(measure):
    """Build the prompt for a single measure."""
    id, title, county, year, topic, category_type, threshold, pct_yes, passed = measure

    # Build context
    context_parts = []
    if county:
        context_parts.append(f"Location: {county}, California")
    if year:
        context_parts.append(f"Year: {year}")
    if category_type and topic:
        context_parts.append(f"Type: {category_type} ({topic})")
    elif category_type:
        context_parts.append(f"Type: {category_type}")
    elif topic:
        context_parts.append(f"Topic: {topic}")

    # Add outcome if available
    if passed is not None and pct_yes is not None:
        outcome = "Passed" if passed == 1 else "Failed"
        threshold_str = f" (required {threshold})" if threshold else ""
        context_parts.append(f"Outcome: {outcome} with {pct_yes:.1f}% yes{threshold_str}")

    context = "\n".join(context_parts)

    prompt = f"""Summarize this California ballot measure in 1-2 neutral sentences.
Focus on what it would do (or did), not persuasive language from the ballot text.
Output only the summary - no preamble, labels, or explanations.

Context:
{context}

Ballot Text:
{title}"""

    return prompt


def call_claude_api(api_key, prompt):
    """Call Claude API and return the summary."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()


def save_checkpoint(processed_ids, stats):
    """Save progress checkpoint."""
    checkpoint = {
        "processed_ids": processed_ids,
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    }
    with open(CHECKPOINT_PATH, 'w') as f:
        json.dump(checkpoint, f)


def load_checkpoint():
    """Load progress checkpoint if exists."""
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, 'r') as f:
            return json.load(f)
    return None


def main():
    parser = argparse.ArgumentParser(description="Generate summaries for ballot measures")
    parser.add_argument("--limit", type=int, help="Limit number of measures to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without API calls")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    args = parser.parse_args()

    # Get API key
    if not args.dry_run:
        api_key = get_api_key()
        logger.info("API key retrieved from Keychain")

        # Import anthropic here so dry-run works without it
        try:
            import anthropic
        except ImportError:
            logger.error("Please install anthropic: pip install anthropic")
            return

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    logger.info(f"Connected to database: {DB_PATH}")

    # Get measures needing summaries
    measures = get_measures_needing_summaries(conn, args.limit)
    logger.info(f"Found {len(measures)} measures needing summaries")

    # Load checkpoint if resuming
    processed_ids = set()
    if args.resume:
        checkpoint = load_checkpoint()
        if checkpoint:
            processed_ids = set(checkpoint.get("processed_ids", []))
            logger.info(f"Resuming from checkpoint: {len(processed_ids)} already processed")

    # Filter out already processed
    measures = [m for m in measures if m[0] not in processed_ids]
    logger.info(f"Will process {len(measures)} measures")

    if args.dry_run:
        logger.info("DRY RUN - showing first 3 prompts:")
        for measure in measures[:3]:
            print("\n" + "="*60)
            print(f"Measure ID: {measure[0]}")
            print("-"*60)
            print(build_prompt(measure))
        return

    # Process measures
    stats = {
        "processed": 0,
        "errors": 0,
        "start_time": datetime.now().isoformat()
    }

    batch_updates = []

    try:
        for i, measure in enumerate(measures):
            measure_id = measure[0]

            try:
                # Build prompt and call API
                prompt = build_prompt(measure)
                summary = call_claude_api(api_key, prompt)

                # Queue update
                batch_updates.append((summary, measure_id))
                processed_ids.add(measure_id)
                stats["processed"] += 1

                # Log progress
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(measures)} measures")

                # Commit batch
                if len(batch_updates) >= BATCH_SIZE:
                    conn.executemany(
                        "UPDATE measures SET summary_text = ? WHERE id = ?",
                        batch_updates
                    )
                    conn.commit()
                    save_checkpoint(list(processed_ids), stats)
                    logger.info(f"Committed batch of {len(batch_updates)} summaries")
                    batch_updates = []

                # Rate limiting
                time.sleep(RATE_LIMIT_DELAY)

            except Exception as e:
                logger.error(f"Error processing measure {measure_id}: {e}")
                stats["errors"] += 1
                # Continue with next measure
                continue

        # Final commit
        if batch_updates:
            conn.executemany(
                "UPDATE measures SET summary_text = ? WHERE id = ?",
                batch_updates
            )
            conn.commit()
            logger.info(f"Committed final batch of {len(batch_updates)} summaries")

    except KeyboardInterrupt:
        logger.info("Interrupted! Saving checkpoint...")
        if batch_updates:
            conn.executemany(
                "UPDATE measures SET summary_text = ? WHERE id = ?",
                batch_updates
            )
            conn.commit()
        save_checkpoint(list(processed_ids), stats)
        logger.info("Checkpoint saved. Resume with --resume flag.")

    finally:
        conn.close()

    # Final stats
    stats["end_time"] = datetime.now().isoformat()
    save_checkpoint(list(processed_ids), stats)

    logger.info(f"""
Summary Generation Complete!
============================
Processed: {stats['processed']}
Errors: {stats['errors']}
""")


if __name__ == "__main__":
    main()
