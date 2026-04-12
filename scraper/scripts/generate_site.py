#!/usr/bin/env python3
"""
Generate static website from ballot measures database
"""
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH, BASE_DIR, WEBSITE_CONFIG
from src.database.operations import Database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Construct website output path from config
WEBSITE_OUTPUT_PATH = BASE_DIR / WEBSITE_CONFIG.get('output_filename', 'index.html')

def main():
    """Main function for website generation"""
    parser = argparse.ArgumentParser(description='Generate static website from ballot measures database')
    parser.add_argument(
        '--output',
        type=str,
        default=str(WEBSITE_OUTPUT_PATH),
        help='Output HTML file path (default: index.html)'
    )
    parser.add_argument(
        '--style',
        choices=['modern', 'clean', 'newspaper'],
        default='modern',
        help='Website style template (default: modern)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration even if no changes detected'
    )
    parser.add_argument(
        '--deploy',
        action='store_true',
        help='Deploy to GitHub Pages after generation'
    )
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Open website in browser after generation'
    )
    
    args = parser.parse_args()
    
    try:
        # Check if database exists
        if not DB_PATH.exists():
            logger.error(f"Database not found at {DB_PATH}")
            logger.info("Run 'scripts/update_db.py' to create/update the database")
            return 1
        
        # Initialize database operations
        db = Database(DB_PATH)
        
        # Get statistics
        stats = db.get_statistics()
        logger.info(f"Database contains {stats['total_measures']} measures")
        
        # Check if generation is needed
        output_path = Path(args.output)
        if output_path.exists() and not args.force:
            # Check if database was updated after website
            db_mtime = DB_PATH.stat().st_mtime
            site_mtime = output_path.stat().st_mtime
            
            if db_mtime <= site_mtime:
                logger.info("Website is up to date. Use --force to regenerate.")
                return 0
        
        # Get all measures from database
        logger.info("Loading measures from database...")
        
        # Valid BallotMeasure fields
        valid_fields = {
            'fingerprint', 'measure_fingerprint', 'content_hash',
            'measure_id', 'measure_letter', 'year', 'state', 'county', 'jurisdiction',
            'title', 'description', 'ballot_question',
            'generated_title', 'original_title',
            'yes_votes', 'no_votes', 'total_votes', 'percent_yes', 'percent_no',
            'passed', 'pass_fail',
            'measure_type', 'topic_primary', 'topic_secondary', 'category_type', 'category_topic',
            'data_source', 'source_url', 'pdf_url',
            'has_summary', 'summary_title', 'summary_text',
            'election_type', 'election_date', 'decade', 'century',
            'created_at', 'updated_at', 'last_seen_at', 'update_count',
            'is_active', 'is_duplicate', 'duplicate_type', 'master_id', 'merged_from'
        }
        
        # Get measures and handle field issues
        conn = db.connect()
        cursor = conn.execute("""
            SELECT * FROM active_measures
            ORDER BY year DESC, county, measure_letter
        """)
        
        measures = []
        measures_data = []
        for row in cursor:
            # Convert row to dict
            measure_dict = dict(row)
            
            # Store original dict for website
            measures_data.append(measure_dict.copy())
            
            # Filter to only valid fields for BallotMeasure
            filtered_dict = {k: v for k, v in measure_dict.items() if k in valid_fields}
            
            # Ensure required fields exist
            filtered_dict.setdefault('fingerprint', '')
            filtered_dict.setdefault('measure_fingerprint', '')
            filtered_dict.setdefault('content_hash', '')
            
            from src.database.models import BallotMeasure
            measure = BallotMeasure(**filtered_dict)
            measures.append(measure)
        
        logger.info(f"Loaded {len(measures)} measures")
        
        # Close database connection
        db.close()
        
        # Initialize website generator  
        from src.website.generator import WebsiteGenerator
        generator = WebsiteGenerator()
        
        # Prepare data for website
        # Convert measures to format needed by generator
        from src.utils.topic_mapping import get_display_topic
        from src.utils.category_type_mapping import get_display_category_type
        from src.utils.external_links import generate_external_links, is_landmark_measure

        measures_for_website = []
        links_generated = 0
        landmark_count = 0
        for m in measures:
            m_dict = m.to_dict()
            # Add display fields
            m_dict['measure_text'] = m_dict.get('title') or m_dict.get('ballot_question', 'Unknown Measure')
            m_dict['source'] = m_dict.get('data_source', 'Historical')

            # Normalize county names to Title Case with spelling corrections
            county = m_dict.get('county')
            if county:
                county = county.strip().title()
                county = {
                    'San Bernadino': 'San Bernardino',
                    'Toulumne': 'Tuolumne',
                }.get(county, county)
                m_dict['county'] = county
            else:
                # Statewide measures (ICPSR, NCSL, CA SOS) have no county
                m_dict['county'] = 'Statewide'

            # Add consolidated display topic (maps detailed topics to ~12 categories)
            raw_topic = m_dict.get('topic_primary') or m_dict.get('category_topic')
            m_dict['display_topic'] = get_display_topic(raw_topic)

            # Add consolidated display category type (maps ~23 raw types to ~13 clean types)
            m_dict['display_category_type'] = get_display_category_type(m_dict.get('category_type'))

            # Normalize percent_yes/percent_no to 0-100 scale
            # CEDA/NCSL store as decimals (0-1), ICPSR stores as percentages (0-100)
            pct_yes = m_dict.get('percent_yes')
            if pct_yes is not None and pct_yes <= 1:
                m_dict['percent_yes'] = pct_yes * 100

            pct_no = m_dict.get('percent_no')
            if pct_no is not None and pct_no <= 1:
                m_dict['percent_no'] = pct_no * 100
            elif pct_no is None and m_dict.get('percent_yes') is not None:
                m_dict['percent_no'] = 100 - m_dict['percent_yes']

            # Generate external links for the measure
            external_links = generate_external_links(m_dict)
            if external_links:
                m_dict['external_links'] = external_links
                links_generated += 1

            # Flag landmark measures
            if is_landmark_measure(m_dict):
                m_dict['is_landmark'] = True
                landmark_count += 1

            measures_for_website.append(m_dict)

        # Compute historical context for pending measures using semantic similarity
        # Embed pending measure text, compare against historical embeddings
        pending_context_count = 0
        try:
            import numpy as np
            from pathlib import Path as _Path

            emb_path = _Path(__file__).parent.parent / 'data' / 'embeddings.npz'
            meta_path = _Path(__file__).parent.parent / 'data' / 'embedding_metadata.json'

            if emb_path.exists() and meta_path.exists():
                import json as _json
                embeddings = np.load(str(emb_path))['embeddings']
                with open(meta_path) as _f:
                    emb_meta = _json.load(_f)
                emb_ids = emb_meta.get('measure_ids', [])

                # Build id → index mapping and id → measure mapping
                id_to_emb_idx = {str(mid): i for i, mid in enumerate(emb_ids)}
                id_to_measure = {}
                for m in measures_for_website:
                    mid = str(m.get('measure_id', '')) or str(m.get('id', ''))
                    id_to_measure[mid] = m

                # Historical measures: have outcome + embedding
                hist_indices = []
                hist_measures = []
                for mid, idx in id_to_emb_idx.items():
                    m = id_to_measure.get(mid)
                    if m and m.get('passed') in (0, 1) and m.get('percent_yes') is not None:
                        hist_indices.append(idx)
                        hist_measures.append(m)
                hist_embeddings = embeddings[hist_indices] if hist_indices else np.array([])

                logger.info(f"  Embedding similarity: {len(hist_indices)} historical measures with embeddings")

                # Load model for pending measures
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer('all-MiniLM-L6-v2')

                for m in measures_for_website:
                    year = int(m.get('year', 0))
                    is_pending = year >= 2025 or (m.get('passed') is None and m.get('percent_yes') is None)
                    if not is_pending:
                        continue

                    # Build text for embedding
                    text = ' '.join(filter(None, [
                        str(m.get('title', '')),
                        str(m.get('summary_text', '')),
                        str(m.get('ballot_question', '')),
                        str(m.get('description', '')),
                    ])).strip()

                    if len(text) < 10:
                        continue

                    # Embed and find similar
                    query_emb = model.encode([text])[0]
                    if len(hist_embeddings) == 0:
                        continue

                    # Cosine similarity
                    norms = np.linalg.norm(hist_embeddings, axis=1) * np.linalg.norm(query_emb)
                    norms[norms == 0] = 1e-10
                    sims = hist_embeddings @ query_emb / norms
                    top_k = min(50, len(sims))
                    top_indices = np.argsort(sims)[-top_k:][::-1]

                    similar = [hist_measures[i] for i in top_indices if sims[i] > 0.3]
                    if len(similar) < 3:
                        continue

                    # Determine the dominant topic among similar measures
                    from collections import Counter as _Counter
                    topic_counts = _Counter(s.get('display_topic') for s in similar if s.get('display_topic'))
                    matched_topic = topic_counts.most_common(1)[0][0] if topic_counts else 'Similar measures'

                    # Compute stats from semantically similar measures
                    total = len(similar)
                    passed_count = sum(1 for s in similar if s.get('passed') == 1)
                    pass_rate = round(100 * passed_count / total, 1)
                    pcts = [s['percent_yes'] for s in similar if s.get('percent_yes') is not None and 0 <= s['percent_yes'] <= 100]
                    avg_yes = round(sum(pcts) / len(pcts), 1) if pcts else None
                    median_yes = round(sorted(pcts)[len(pcts) // 2], 1) if pcts else None

                    years = [int(s.get('year', 0)) for s in similar if s.get('year')]
                    year_range = f"{min(years)}-{max(years)}" if years else ""

                    # Top 3 most similar with outcome details
                    top_similar = []
                    for s in similar[:3]:
                        top_similar.append({
                            'year': s.get('year'),
                            'county': s.get('county'),
                            'title': s.get('generated_title') or s.get('summary_title') or s.get('title', '')[:60],
                            'percent_yes': round(s['percent_yes'], 1) if s.get('percent_yes') else None,
                            'passed': s.get('passed'),
                            'similarity': round(float(sims[top_indices[similar.index(s)]]) * 100, 0) if similar.index(s) < len(top_indices) else None,
                        })

                    # Closest races among similar
                    with_pct = [(s, abs(s['percent_yes'] - 50)) for s in similar if s.get('percent_yes') and 0 <= s['percent_yes'] <= 100]
                    closest = sorted(with_pct, key=lambda x: x[1])[:3]
                    closest_measures = [{
                        'year': s.get('year'),
                        'county': s.get('county'),
                        'title': s.get('generated_title') or s.get('title', '')[:60],
                        'percent_yes': round(s['percent_yes'], 1),
                        'passed': s.get('passed'),
                    } for s, _ in closest]

                    m['historical_context'] = {
                        'matched_topic': matched_topic,
                        'total_similar': total,
                        'pass_rate': pass_rate,
                        'avg_yes': avg_yes,
                        'median_yes': median_yes,
                        'year_range': year_range,
                        'top_similar': top_similar,
                        'closest_races': closest_measures,
                    }
                    pending_context_count += 1

        except ImportError as e:
            logger.warning(f"  Could not compute embedding similarity (missing dependency: {e}). Falling back to no context.")
        except Exception as e:
            logger.warning(f"  Error computing historical context: {e}")

        if pending_context_count:
            logger.info(f"  Added semantic historical context to {pending_context_count} pending measures")

        # Extract topics
        from collections import Counter
        topic_counts = Counter()
        for measure in measures:
            topic = measure.topic_primary or measure.category_topic
            if topic:
                topic_counts[topic] += 1
        
        topics = [
            {'topic': topic, 'count': count}
            for topic, count in topic_counts.most_common(20)
        ]

        # Load recommendations for related measures
        recommendations = generator._load_recommendations()

        # Generate website
        logger.info(f"Generating website...")
        html_content = generator._generate_html(measures_for_website, stats, topics, recommendations)
        
        # Save website
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding='utf-8')
        logger.info(f"Website saved to: {output_path}")
        
        # Also save to root directory for GitHub Pages
        # Get the actual project root (parent of scraper directory)
        script_dir = Path(__file__).resolve().parent.parent  # This is the scraper/ directory
        project_root = script_dir.parent  # This is cal_vgp/ directory
        root_index = project_root / 'index.html'
        logger.info(f"Copying to project root: {root_index.resolve()}")
        try:
            root_index.write_text(html_content, encoding='utf-8')
            # Verify the write
            if root_index.exists() and root_index.stat().st_size > 1000000:  # Should be > 1MB
                logger.info(f"✓ Successfully saved to: {root_index.resolve()}")
            else:
                logger.warning(f"⚠️  File may not have been written correctly: {root_index.resolve()}")
        except Exception as e:
            logger.error(f"Failed to save to project root: {e}")
        
        # Deploy if requested
        if args.deploy:
            logger.info("Deploying to GitHub Pages...")
            deploy_to_github()
        
        # Preview if requested
        if args.preview:
            import webbrowser
            webbrowser.open(f'file://{output_path.absolute()}')
            logger.info("Opened website in browser")
        
        # Print summary
        print("\n" + "="*60)
        print("✅ Website Generation Complete!")
        print("="*60)
        print(f"📊 Total Measures: {stats['total_measures']}")
        print(f"📝 With Summaries: {stats['with_summaries']}")
        print(f"🗳️ With Vote Data: {stats['with_votes']}")
        print(f"📅 Year Range: {stats.get('year_min', 'N/A')}-{stats.get('year_max', 'N/A')}")
        print(f"🔗 With External Links: {links_generated}")
        print(f"⭐ Landmark Measures: {landmark_count}")
        print(f"🌐 Output: {output_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error generating website: {e}", exc_info=True)
        return 1

def deploy_to_github():
    """Deploy website to GitHub Pages"""
    try:
        import subprocess
        
        # Stage changes
        subprocess.run(['git', 'add', '../index.html'], check=True)
        subprocess.run(['git', 'add', 'data/'], check=True)
        
        # Commit
        commit_msg = f"Update website - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=False)
        
        # Push
        subprocess.run(['git', 'push'], check=True)
        
        logger.info("Successfully deployed to GitHub Pages")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error deploying to GitHub: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during deployment: {e}")
        raise

if __name__ == "__main__":
    sys.exit(main())