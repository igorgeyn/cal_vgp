#!/usr/bin/env python3
"""
Compare title generation quality across different AI providers
Generates titles using all available providers and saves comparison results
"""
import sys
import logging
import json
import random
from pathlib import Path
from datetime import datetime

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
    """Compare title generation across providers"""

    print("=" * 70)
    print("AI Title Generation Provider Comparison")
    print("=" * 70)

    # Get sample size from user
    try:
        sample_size = int(input("\nHow many measures to test? (default: 50): ") or "50")
    except ValueError:
        sample_size = 50

    # Initialize
    db = Database()
    title_gen = TitleGenerator(database=db, provider='auto')

    # Check available providers
    providers = title_gen.get_available_providers()

    if not providers:
        print("\n❌ No AI providers available!")
        print("\nAvailable options:")
        print("  • Ollama (local, free): brew install ollama && ollama pull llama3.2:3b")
        print("  • Groq (cloud, free): export GROQ_API_KEY='your-key'")
        print("  • Claude (cloud, paid): export ANTHROPIC_API_KEY='your-key'")
        return

    print(f"\n✅ Found {len(providers)} provider(s): {', '.join(providers)}")

    # Get measures that need titles
    conn = db.connect()
    cursor = conn.execute("""
        SELECT id, measure_id, title, year
        FROM measures
        WHERE is_active = 1
        ORDER BY year DESC
    """)
    all_measures = [dict(row) for row in cursor.fetchall()]

    # Filter to those that need generation
    measures_needing_titles = [
        m for m in all_measures
        if title_gen.should_generate_title(m['title'] or '')
    ]

    print(f"\n📊 Found {len(measures_needing_titles)} measures with long titles")

    # Random sample
    if len(measures_needing_titles) > sample_size:
        sample = random.sample(measures_needing_titles, sample_size)
    else:
        sample = measures_needing_titles

    print(f"🎲 Testing on {len(sample)} random measures\n")

    # Estimate cost
    cost_per_title = {
        'ollama': 0.0,  # Free
        'groq': 0.0,    # Free
        'claude': 0.0001  # ~$0.0001 per title
    }

    total_cost = sum(cost_per_title.get(p, 0) * len(sample) for p in providers)

    if total_cost > 0:
        print(f"💰 Estimated cost: ${total_cost:.4f}")
        if total_cost > 1.0:
            response = input(f"\n⚠️  This will cost ~${total_cost:.2f}. Continue? (y/n): ")
            if response.lower() != 'y':
                print("Cancelled.")
                return

    # Generate titles with all providers
    results = []

    print("\n" + "=" * 70)
    print("Generating titles...")
    print("=" * 70 + "\n")

    for i, measure in enumerate(sample, 1):
        measure_id = measure['measure_id'] or f"measure_{i}"
        title = measure['title'] or ''
        year = measure['year']

        print(f"[{i}/{len(sample)}] {measure_id} ({year})")
        print(f"  Original: {title[:100]}...")

        result = {
            'measure_id': measure_id,
            'year': year,
            'original_title': title,
            'original_length': len(title),
            'generated_titles': {}
        }

        # Generate with each provider
        for provider in providers:
            try:
                generated = title_gen.generate_title(title, measure_id, provider=provider)
                result['generated_titles'][provider] = generated
                print(f"  {provider:8s}: {generated}")
            except Exception as e:
                logger.error(f"  {provider:8s}: ERROR - {e}")
                result['generated_titles'][provider] = None

        results.append(result)
        print()

    # Save results
    output_file = Path(__file__).parent.parent / 'data' / f'title_comparison_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'providers': providers,
            'sample_size': len(sample),
            'total_cost_estimate': total_cost,
            'results': results
        }, f, indent=2)

    print("=" * 70)
    print("Comparison Complete!")
    print("=" * 70)
    print(f"\n📁 Results saved to: {output_file}")

    # Summary statistics
    print("\n📊 Summary Statistics:\n")

    for provider in providers:
        successful = sum(1 for r in results if r['generated_titles'].get(provider))
        avg_length = sum(
            len(r['generated_titles'][provider])
            for r in results
            if r['generated_titles'].get(provider)
        ) / max(successful, 1)

        print(f"{provider.capitalize():10s}: {successful}/{len(sample)} successful, avg {avg_length:.1f} chars")

    # Show some examples side-by-side
    print("\n📝 Example Comparisons:\n")

    for i, result in enumerate(results[:3], 1):
        print(f"Example {i}: {result['measure_id']}")
        print(f"  Original ({result['original_length']} chars):")
        print(f"    {result['original_title'][:120]}...")
        print(f"  Generated:")
        for provider in providers:
            title = result['generated_titles'].get(provider, 'ERROR')
            print(f"    {provider:8s}: {title}")
        print()

    # Instructions for review
    print("=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print(f"\n1. Review the comparison file: {output_file.name}")
    print("2. Pick your preferred provider based on quality")
    print("3. Set the provider in your environment:")
    print("   export TITLE_GENERATION_PROVIDER=ollama  # or groq, claude")
    print("\n4. Generate all titles with chosen provider:")
    print("   python scripts/generate_titles.py")
    print("\n5. Update database:")
    print("   python scripts/update_generated_titles.py")
    print("\n6. Rebuild website:")
    print("   python scripts/generate_site.py --force")
    print("=" * 70)


if __name__ == '__main__':
    main()
