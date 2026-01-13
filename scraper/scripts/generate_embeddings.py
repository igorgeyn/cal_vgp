#!/usr/bin/env python3
"""
Generate sentence embeddings for ballot measures to power recommendations.
Uses all-MiniLM-L6-v2 for fast, quality embeddings.
"""
import sys
import json
import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_transformers import SentenceTransformer

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"
EMBEDDINGS_PATH = Path(__file__).parent.parent / "data" / "embeddings.npz"
METADATA_PATH = Path(__file__).parent.parent / "data" / "embedding_metadata.json"

def get_measures_for_embedding():
    """Get all measures with enough text content for meaningful embeddings."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute('''
        SELECT
            measure_id,
            year,
            county,
            jurisdiction,
            title,
            summary_title,
            summary_text,
            ballot_question,
            description,
            topic_primary,
            topic_secondary
        FROM measures
        WHERE is_active = 1
        ORDER BY measure_id
    ''')

    measures = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return measures

def create_embedding_text(measure):
    """Create the text to embed for a measure. Combines available fields."""
    parts = []

    # Title is most important
    if measure.get('title'):
        parts.append(measure['title'])

    # Summary provides context
    if measure.get('summary_text'):
        parts.append(measure['summary_text'])
    elif measure.get('summary_title'):
        parts.append(measure['summary_title'])

    # Ballot question has the actual legal text
    if measure.get('ballot_question'):
        parts.append(measure['ballot_question'][:500])  # Truncate long questions

    # Description if available
    if measure.get('description'):
        parts.append(measure['description'][:500])

    # Topics help with categorization
    if measure.get('topic_primary'):
        parts.append(f"Topic: {measure['topic_primary']}")
    if measure.get('topic_secondary'):
        parts.append(f"Related to: {measure['topic_secondary']}")

    return " ".join(parts)

def compute_nearest_neighbors(embeddings, k=5):
    """Compute k nearest neighbors for each embedding using cosine similarity."""
    # Normalize embeddings for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / norms

    # Compute similarity matrix
    similarity = np.dot(normalized, normalized.T)

    # For each item, get top k+1 (excluding self) neighbors
    neighbors = []
    for i in range(len(embeddings)):
        # Get indices sorted by similarity (descending)
        sorted_indices = np.argsort(similarity[i])[::-1]
        # Skip self (index 0 after sorting since self-similarity = 1)
        neighbor_indices = [idx for idx in sorted_indices if idx != i][:k]
        neighbor_scores = [float(similarity[i][idx]) for idx in neighbor_indices]
        neighbors.append(list(zip(neighbor_indices, neighbor_scores)))

    return neighbors

def main():
    print("=" * 60)
    print("GENERATING EMBEDDINGS FOR RECOMMENDATIONS")
    print("=" * 60)

    # Load model
    print("\n1. Loading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"   Model loaded: all-MiniLM-L6-v2 (384 dimensions)")

    # Get measures
    print("\n2. Loading measures from database...")
    measures = get_measures_for_embedding()
    print(f"   Found {len(measures)} measures")

    # Create texts to embed
    print("\n3. Creating embedding texts...")
    texts = []
    measure_ids = []
    skipped = 0

    for m in measures:
        text = create_embedding_text(m)
        if len(text) < 20:  # Skip measures with too little content
            skipped += 1
            continue
        texts.append(text)
        measure_ids.append(m['measure_id'])

    print(f"   Prepared {len(texts)} texts ({skipped} skipped due to insufficient content)")

    # Generate embeddings
    print("\n4. Generating embeddings (this may take a few minutes)...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    print(f"   Generated embeddings: shape {embeddings.shape}")

    # Compute nearest neighbors
    print("\n5. Computing nearest neighbors (k=5)...")
    neighbors = compute_nearest_neighbors(embeddings, k=5)
    print(f"   Computed neighbors for {len(neighbors)} measures")

    # Create neighbor lookup by measure_id
    neighbor_lookup = {}
    for i, mid in enumerate(measure_ids):
        neighbor_lookup[mid] = [
            {"measure_id": measure_ids[idx], "score": score}
            for idx, score in neighbors[i]
        ]

    # Save embeddings
    print("\n6. Saving embeddings and metadata...")
    np.savez_compressed(EMBEDDINGS_PATH, embeddings=embeddings)
    print(f"   Embeddings saved to: {EMBEDDINGS_PATH}")

    # Save metadata
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "model": "all-MiniLM-L6-v2",
        "dimensions": 384,
        "num_measures": len(measure_ids),
        "measure_ids": measure_ids,
        "neighbors": neighbor_lookup
    }

    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"   Metadata saved to: {METADATA_PATH}")

    # Summary
    print("\n" + "=" * 60)
    print("EMBEDDING GENERATION COMPLETE")
    print("=" * 60)
    print(f"Total measures embedded: {len(measure_ids)}")
    print(f"Embedding dimensions: 384")
    print(f"Embeddings file: {EMBEDDINGS_PATH.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"Metadata file: {METADATA_PATH.stat().st_size / 1024:.2f} KB")

    # Show sample neighbors
    print("\nSample recommendations:")
    sample_ids = measure_ids[:3]
    for mid in sample_ids:
        print(f"\n  {mid}:")
        for n in neighbor_lookup[mid][:3]:
            print(f"    - {n['measure_id']} (similarity: {n['score']:.3f})")

if __name__ == '__main__':
    main()
