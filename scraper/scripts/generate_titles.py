#!/usr/bin/env python3
"""
Generate AI-powered titles for ballot measures with long text
Supports multiple providers: Ollama (free), Groq (free), Claude (paid)
"""
import sys
import logging
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.operations import Database
from src.utils import TitleGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Generate titles for measures that need them"""

    print("=" * 60)
    print("AI Title Generation for Ballot Measures")
    print("=" * 60)

    # Get provider from environment or use auto
    provider = os.getenv('TITLE_GENERATION_PROVIDER', 'auto')

    # Initialize
    db = Database()
    title_gen = TitleGenerator(database=db, provider=provider)

    # Check if any providers are available
    available_providers = title_gen.get_available_providers()

    if not available_providers:
        print("\n⚠️  No AI providers available!")
        print("\nAvailable options:")
        print("\n1. Ollama (local, free):")
        print("   brew install ollama")
        print("   ollama pull llama3.2:3b")
        print("\n2. Groq (cloud, free):")
        print("   export GROQ_API_KEY='your-key-here'")
        print("   pip install groq")
        print("\n3. Claude (cloud, paid):")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        print("   pip install anthropic")
        print("\nWithout an AI provider, the website will use CSS truncation for long titles.\n")
        return

    print(f"\n✅ Using provider: {title_gen.active_provider}")
    print(f"📋 Available providers: {', '.join(available_providers)}\n")

    # Get all measures
    measures = db.get_all_active_measures()
    logger.info(f"Loaded {len(measures)} measures from database")

    # Find measures that need titles
    needs_title = []
    for measure in measures:
        title = measure.title or ''
        if title_gen.should_generate_title(title):
            needs_title.append(measure)

    print(f"\n📊 Found {len(needs_title)} measures with long titles that need generation")

    if not needs_title:
        print("✅ All measures have suitable titles!")
        return

    # Ask for confirmation
    print(f"\n⚠️  This will make ~{len(needs_title)} API calls to Claude")
    print(f"💰 Estimated cost: ~${len(needs_title) * 0.0001:.2f} (using Haiku model)")
    response = input("\nProceed? (y/n): ")

    if response.lower() != 'y':
        print("Cancelled.")
        return

    # Generate titles
    print("\n🤖 Generating titles...\n")
    generated = 0

    for i, measure in enumerate(needs_title, 1):
        title = measure.title or measure.measure_text or ''
        measure_id = measure.measure_id or f"measure_{i}"

        print(f"[{i}/{len(needs_title)}] {measure_id}")
        print(f"  Original: {title[:100]}...")

        new_title = title_gen.generate_title(title, measure_id)

        if new_title:
            print(f"  Generated: {new_title}")
            generated += 1
        else:
            print(f"  ⚠️  Failed to generate")

        print()

    print("=" * 60)
    print(f"✅ Successfully generated {generated}/{len(needs_title)} titles")
    print(f"💾 Cached to: {title_gen.cache_path}")
    print("\n🌐 Run 'python scripts/generate_site.py --force' to rebuild website with new titles")
    print("=" * 60)


if __name__ == '__main__':
    main()
