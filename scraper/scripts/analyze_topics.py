#!/usr/bin/env python3
"""
Analyze ballot measure topics using clustering on pre-computed embeddings.
Discovers natural topic clusters in the data.
"""
import sys
import json
import sqlite3
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / "data" / "ballot_measures.db"
EMBEDDINGS_PATH = Path(__file__).parent.parent / "data" / "embeddings.npz"
METADATA_PATH = Path(__file__).parent.parent / "data" / "embedding_metadata.json"

def get_measures_with_text():
    """Get measures with their text content for topic labeling."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute('''
        SELECT
            measure_id,
            year,
            title,
            summary_text,
            ballot_question,
            description
        FROM measures
        WHERE is_active = 1
        ORDER BY measure_id
    ''')

    measures = {row['measure_id']: dict(row) for row in cursor.fetchall()}
    conn.close()
    return measures

def create_doc_text(measure):
    """Create document text for topic modeling."""
    parts = []
    if measure.get('title'):
        parts.append(measure['title'])
    if measure.get('summary_text'):
        parts.append(measure['summary_text'])
    elif measure.get('ballot_question'):
        parts.append(measure['ballot_question'][:500])
    elif measure.get('description'):
        parts.append(measure['description'][:500])
    return " ".join(parts)

def extract_keywords(texts, n_keywords=10):
    """Extract top keywords from a list of texts using TF-IDF."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    if not texts:
        return []

    vectorizer = TfidfVectorizer(
        stop_words='english',
        ngram_range=(1, 2),
        max_features=1000,
        min_df=2,
        max_df=0.8
    )

    try:
        tfidf = vectorizer.fit_transform(texts)
        feature_names = vectorizer.get_feature_names_out()

        # Sum TF-IDF scores across all documents
        scores = np.asarray(tfidf.sum(axis=0)).flatten()
        top_indices = scores.argsort()[-n_keywords:][::-1]

        return [feature_names[i] for i in top_indices]
    except:
        return []

def main():
    print("=" * 60)
    print("TOPIC ANALYSIS WITH K-MEANS CLUSTERING")
    print("=" * 60)

    # Load embeddings
    print("\n1. Loading pre-computed embeddings...")
    embeddings_data = np.load(EMBEDDINGS_PATH)
    embeddings = embeddings_data['embeddings']

    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    measure_ids = metadata['measure_ids']
    print(f"   Loaded {len(embeddings)} embeddings")

    # Load measure texts
    print("\n2. Loading measure texts...")
    measures = get_measures_with_text()

    # Create document list aligned with embeddings
    docs = []
    valid_indices = []
    valid_measure_ids = []

    for i, mid in enumerate(measure_ids):
        if mid in measures:
            text = create_doc_text(measures[mid])
            if len(text) > 20:
                docs.append(text)
                valid_indices.append(i)
                valid_measure_ids.append(mid)

    # Filter embeddings to match valid docs
    valid_embeddings = embeddings[valid_indices]
    print(f"   Prepared {len(docs)} documents with text")

    # Normalize embeddings for cosine distance
    from sklearn.preprocessing import normalize
    normalized_embeddings = normalize(valid_embeddings)

    # Find optimal number of clusters using elbow method (quick version)
    print("\n3. Finding optimal number of clusters...")
    from sklearn.cluster import KMeans

    # Try a few cluster counts
    n_clusters_to_try = [15, 20, 25, 30]
    inertias = []

    for n in n_clusters_to_try:
        km = KMeans(n_clusters=n, random_state=42, n_init=10)
        km.fit(normalized_embeddings)
        inertias.append(km.inertia_)
        print(f"   k={n}: inertia={km.inertia_:.0f}")

    # Use 20 clusters as a reasonable default
    n_clusters = 20
    print(f"\n   Using {n_clusters} clusters")

    # Run K-Means clustering
    print("\n4. Running K-Means clustering...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(normalized_embeddings)

    # Analyze each cluster
    print("\n5. Analyzing discovered topics...")

    cluster_data = defaultdict(lambda: {'docs': [], 'measure_ids': [], 'texts': []})

    for i, (label, mid, text) in enumerate(zip(cluster_labels, valid_measure_ids, docs)):
        cluster_data[label]['docs'].append(i)
        cluster_data[label]['measure_ids'].append(mid)
        cluster_data[label]['texts'].append(text)

    print(f"\n{'=' * 60}")
    print(f"DISCOVERED {n_clusters} TOPIC CLUSTERS")
    print(f"{'=' * 60}")

    topic_info = []

    # Sort clusters by size
    sorted_clusters = sorted(cluster_data.items(), key=lambda x: len(x[1]['docs']), reverse=True)

    for cluster_id, data in sorted_clusters:
        count = len(data['docs'])

        # Extract keywords for this cluster
        keywords = extract_keywords(data['texts'], n_keywords=8)

        # Get example measures
        example_mids = data['measure_ids'][:3]

        print(f"\n📌 Cluster {cluster_id}: {count} measures")
        print(f"   Keywords: {', '.join(keywords)}")
        print(f"   Examples:")
        for mid in example_mids:
            title = measures[mid].get('title', 'No title')[:55]
            year = measures[mid].get('year', '?')
            print(f"      - [{year}] {title}...")

        topic_info.append({
            'cluster_id': int(cluster_id),
            'count': count,
            'keywords': keywords,
            'suggested_name': keywords[0] if keywords else f"Topic {cluster_id}"
        })

    # Save topic assignments
    print("\n6. Saving topic assignments...")
    topic_assignments = {}
    for i, mid in enumerate(valid_measure_ids):
        topic_assignments[mid] = {
            'cluster_id': int(cluster_labels[i])
        }

    output = {
        'assignments': topic_assignments,
        'topics': {t['cluster_id']: t for t in topic_info},
        'num_topics': n_clusters
    }

    output_path = Path(__file__).parent.parent / "data" / "topic_analysis.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"   Saved to: {output_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total measures analyzed: {len(docs)}")
    print(f"Topics discovered: {n_clusters}")

    # Show topic distribution
    print(f"\nTopic size distribution:")
    sizes = [len(data['docs']) for _, data in sorted_clusters]
    print(f"   Largest: {max(sizes)} measures")
    print(f"   Smallest: {min(sizes)} measures")
    print(f"   Average: {sum(sizes)//len(sizes)} measures")

if __name__ == '__main__':
    main()
