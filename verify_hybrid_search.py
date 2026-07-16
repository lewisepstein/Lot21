"""
Quick health check for hybrid search (BM25 + semantic).

Usage (from the repo root, venv active):
    python verify_hybrid_search.py
    python verify_hybrid_search.py "your test query here"

Checks that the training_data collection has the Ollama vectorizer and
embedded vectors, then shows BM25 vs hybrid results side by side so you
can compare retrieval quality.
"""
import sys

import weaviate

query = sys.argv[1] if len(sys.argv) > 1 else "keeping university buildings safe from natural disasters"

client = weaviate.connect_to_local()
try:
    col = client.collections.get("training_data")

    # 1. Collection setup
    cfg = col.config.get()
    vc = cfg.vector_config or {}
    vectorizer = next(iter(vc.values())).vectorizer.vectorizer if vc else None
    total = col.aggregate.over_all(total_count=True).total_count
    print(f"collection: training_data | objects: {total} | vectorizer: {vectorizer}")

    sample = col.query.fetch_objects(limit=1, include_vector=True).objects
    dims = {k: len(v) for k, v in sample[0].vector.items()} if sample and sample[0].vector else None
    print(f"sample object vector dims: {dims}")

    if not vectorizer or not dims:
        print("\n*** PROBLEM: no vectorizer or no vectors — hybrid search will fall back to BM25 ***")

    # 2. Side-by-side retrieval comparison
    print(f'\nquery: "{query}"\n')
    bm = col.query.bm25(query=query, limit=3, return_properties=["text"])
    print("--- BM25 (old, keyword only) ---")
    for o in bm.objects:
        print("  -", o.properties["text"][:100].replace("\n", " "))

    hy = col.query.hybrid(query=query, alpha=0.5, limit=3, return_properties=["text"])
    print("--- HYBRID (new, keyword + semantic) ---")
    for o in hy.objects:
        print("  -", o.properties["text"][:100].replace("\n", " "))
finally:
    client.close()
