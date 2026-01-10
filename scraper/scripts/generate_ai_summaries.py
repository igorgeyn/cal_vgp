#!/usr/bin/env python3
"""
Generate AI summaries for ballot measures that don't have them
Uses Ollama (local, free) to generate summaries from measure titles and descriptions
"""
import sys
import logging
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Prompt template for generating summaries
SUMMARY_PROMPT = """You are analyzing a California ballot measure. Based on the information provided, generate a clear, neutral summary.

Title: {title}
{description_section}
{ballot_question_section}

Generate a concise 2-3 sentence summary that explains:
1. What this measure does
2. The main change or effect it would have

Write in a neutral, factual tone. Do not include opinions or recommendations.

Summary:"""


def generate_summary_with_ollama(title: str, description: str = None,
                                  ballot_question: str = None,
                                  model: str = "llama3.2") -> dict:
    """
    Generate a summary using Ollama

    Args:
        title: Measure title
        description: Optional description text
        ballot_question: Optional ballot question text
        model: Ollama model to use

    Returns:
        Dict with summary_text and summary_title
    """
    if not OLLAMA_AVAILABLE:
        raise ImportError("Ollama not installed. Run: pip install ollama")

    # Build prompt with available information
    description_section = f"Description: {description}" if description else ""
    ballot_question_section = f"Ballot Question: {ballot_question}" if ballot_question else ""

    prompt = SUMMARY_PROMPT.format(
        title=title,
        description_section=description_section,
        ballot_question_section=ballot_question_section
    )

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={
                'temperature': 0.3,  # Lower temperature for more factual output
                'num_predict': 150,  # Limit length to ~2-3 sentences
            }
        )

        summary_text = response['response'].strip()

        # Create summary_title from first sentence
        import re
        sentences = re.split(r'[.!?]', summary_text)
        first_sentence = sentences[0].strip() if sentences else summary_text

        if len(first_sentence) > 150:
            summary_title = first_sentence[:147] + '...'
        else:
            summary_title = first_sentence

        return {
            'summary_text': summary_text,
            'summary_title': summary_title
        }

    except Exception as e:
        logger.error(f"Ollama generation failed: {e}")
        return None


def main():
    """Generate AI summaries for measures without them"""

    print("=" * 60)
    print("Generate AI Summaries for Ballot Measures")
    print("=" * 60)

    # Check if Ollama is available
    if not OLLAMA_AVAILABLE:
        print("\n❌ Error: Ollama not installed")
        print("   Install with: pip install ollama")
        print("   Also ensure Ollama is running: https://ollama.ai")
        return

    # Test Ollama connection
    try:
        models = ollama.list()
        print(f"\n✓ Ollama connected. Available models: {len(models.get('models', []))}")
    except Exception as e:
        print(f"\n❌ Error: Cannot connect to Ollama: {e}")
        print("   Make sure Ollama is running (see https://ollama.ai)")
        return

    # Initialize database
    db = Database()
    conn = db.connect()

    # Get measures that need summaries
    # Priority: measures with no summary at all, or only AI-generated titles but no summaries
    cursor = conn.execute("""
        SELECT id, measure_id, year, county, jurisdiction,
               title, description, ballot_question, original_title,
               data_source
        FROM measures
        WHERE is_active = 1
          AND year >= 2020
          AND (has_summary = 0 OR has_summary IS NULL)
        ORDER BY year DESC, county, measure_id
    """)

    measures = cursor.fetchall()
    total = len(measures)

    print(f"\n📊 Found {total} measures needing AI summaries")

    if total == 0:
        print("\n✅ All measures already have summaries!")
        return

    # Ask for model choice
    print("\nAvailable models:")
    print("  1. llama3.2 (fast, recommended)")
    print("  2. llama3.2:1b (faster, smaller)")
    print("  3. mistral (alternative)")

    model_choice = input("\nSelect model (1-3, default=1): ").strip() or "1"
    model_map = {
        "1": "llama3.2",
        "2": "llama3.2:1b",
        "3": "mistral"
    }
    model = model_map.get(model_choice, "llama3.2")

    # Estimate time
    avg_time_per_measure = 3  # seconds
    estimated_minutes = (total * avg_time_per_measure) / 60

    print(f"\n⏱️  Estimated time: {estimated_minutes:.1f} minutes")
    print(f"   Using model: {model}")

    response = input(f"\nGenerate summaries for {total} measures? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return

    # Process measures
    print(f"\n🤖 Generating summaries...\n")
    generated = 0
    failed = 0
    skipped = 0

    for i, measure in enumerate(measures, 1):
        db_id = measure['id']
        measure_id = measure['measure_id'] or 'N/A'
        year = measure['year']
        county = measure['county'] or measure['jurisdiction'] or 'Statewide'
        title = measure['title']
        description = measure['description']
        ballot_question = measure['ballot_question']
        original_title = measure['original_title']

        print(f"[{i}/{total}] {measure_id} ({year}) {county}")

        # Skip if we don't have enough information
        if not title and not description and not ballot_question and not original_title:
            print(f"  ⚠️  Skipped: No text available")
            skipped += 1
            continue

        # Use best available text
        input_title = title or original_title or f"Measure {measure_id}"
        input_description = description or ""
        input_ballot_question = ballot_question or ""

        try:
            # Generate summary
            result = generate_summary_with_ollama(
                title=input_title,
                description=input_description,
                ballot_question=input_ballot_question,
                model=model
            )

            if result:
                summary_text = result['summary_text']
                summary_title = result['summary_title']

                # Update database
                conn.execute("""
                    UPDATE measures
                    SET summary_title = ?,
                        summary_text = ?,
                        has_summary = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (summary_title, summary_text, db_id))

                print(f"  ✓ Generated ({len(summary_text)} chars)")
                print(f"    {summary_text[:100]}...")
                generated += 1

                # Commit every 10 measures
                if generated % 10 == 0:
                    conn.commit()
            else:
                print(f"  ✗ Generation failed")
                failed += 1

        except Exception as e:
            logger.error(f"Failed to generate summary for {db_id}: {e}")
            failed += 1

        # Small delay to avoid overwhelming the system
        time.sleep(0.1)

    # Final commit
    conn.commit()

    # Count results
    cursor = conn.execute("""
        SELECT COUNT(*)
        FROM measures
        WHERE year >= 2020
          AND is_active = 1
          AND has_summary = 1
    """)
    total_with_summaries = cursor.fetchone()[0]

    db.close()

    print("\n" + "=" * 60)
    print("✅ AI Summary Generation Complete!")
    print(f"   Generated: {generated}/{total}")
    print(f"   Skipped: {skipped}/{total}")
    print(f"   Failed: {failed}/{total}")
    print(f"\n   Total measures with summaries: {total_with_summaries}")
    print("=" * 60)
    print("\n📋 Next steps:")
    print("  Run 'make website' to rebuild website with new summaries")


if __name__ == '__main__':
    main()
