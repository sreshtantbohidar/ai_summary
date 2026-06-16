#!/usr/bin/env python3
"""
Create vec_fatboy_data index from fatboy_data with unified 768-dim
nomic-embed-text vectorization.

Steps:
  1. Read connection constants from constants.py
  2. Create vec_fatboy_data index with dense_vector(768) mapping
  3. Scroll through fatboy_data, embed key text fields, bulk index

Usage:
    python3 create_vec_index.py                  # full run
    python3 create_vec_index.py --create-only    # only create the index
    python3 create_vec_index.py --index-only     # only index (index must exist)
    python3 create_vec_index.py --dry-run        # show what would happen
    python3 create_vec_index.py --batch-size 50  # tune batch size
"""

import sys
import os
import re
import json
import time
import argparse
import importlib
import requests as req_lib
from datetime import datetime

# ---------------------------------------------------------------------------
# 1. Load connection constants from constants.py
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import constants

ES_HOST = constants.ELASTIC_HOST       # 192.168.1.125
ES_PORT = constants.ELASTIC_PORT       # 9200
ES_SCHEME = constants.ELASTIC_CLIENT_SCHEME  # https
ES_USER = constants.ELASTICSEARCH_USERNAME     # elastic
ES_PASS = constants.ELASTICSEARCH_PASSWORD     # 30oIsFcjJa8Zao+iq5*e
ES_VERIFY = False

OLLAMA_HOST = constants.ollama_api_host   # 192.168.1.125
OLLAMA_PORT = constants.ollama_api_port   # 11434
OLLAMA_MODEL = "nomic-embed-text"
EMBED_DIM = 768

SOURCE_INDEX = "fatboy_data"
TARGET_INDEX = "vec_fatboy_data"

# ---------------------------------------------------------------------------
# 2. Key text fields to concatenate for embedding
#    These carry the semantic content of each document.
# ---------------------------------------------------------------------------
EMBED_FIELDS = [
    "description",
    "title",
    "orignal_description",
    "paragraph",
    "form_data_search",
    "source_data",
    "activity_name",
    "location_name",
    "form_title",
    "form_type",
    "activity_type",
    "source_type",
    "relevance",
    "sentiment_label",
    "doc_data_type",
    "keywords",
    "equipment_name",
    "equipment_type",
    "name",
    "type",
    "sub_activity_type",
    "remark",
    "remarks",
    "comment",
    "comments",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_es():
    from elasticsearch import Elasticsearch
    return Elasticsearch(
        [{"host": ES_HOST, "port": ES_PORT, "scheme": ES_SCHEME}],
        basic_auth=(ES_USER, ES_PASS),
        verify_certs=ES_VERIFY,
        ssl_show_warn=False,
    )


def embed_text(text: str) -> list:
    """Call Ollama /api/embeddings and return the 768-dim vector."""
    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/embeddings"
    resp = req_lib.post(url, json={"model": OLLAMA_MODEL, "prompt": text}, timeout=120)
    resp.raise_for_status()
    return resp.json()["embedding"]


def embed_batch(texts: list) -> list:
    """Embed a list of texts one-by-one (Ollama /embeddings accepts single prompt)."""
    vectors = []
    for t in texts:
        vectors.append(embed_text(t))
    return vectors


def build_text(doc: dict) -> str:
    """Concatenate selected text fields into one string for embedding."""
    parts = []
    for field in EMBED_FIELDS:
        val = doc.get(field)
        if val and isinstance(val, str) and val.strip():
            parts.append(val.strip())
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return " ".join(unique)


def build_mapping(source_mapping: dict) -> dict:
    """
    Build the target mapping: copy all source properties and add
    a dense_vector field for embeddings.
    """
    source_props = source_mapping["fatboy_data"]["mappings"]["properties"]
    # Add the vector field
    props = dict(source_props)
    props["embedding"] = {
        "type": "dense_vector",
        "dims": EMBED_DIM,
        "index": True,
        "similarity": "cosine",
    }
    props["embedded_text"] = {
        "type": "text",
        "index": False,
    }
    props["embedded_at"] = {
        "type": "date",
    }
    return {
        "mappings": {
            "properties": props
        }
    }


def create_index(es, dry_run=False):
    """Create vec_fatboy_data index. Delete first if it already exists."""
    if es.indices.exists(index=TARGET_INDEX):
        print(f"[!] Target index '{TARGET_INDEX}' already exists.")
        if not dry_run:
            print(f"    Deleting and recreating...")
            es.indices.delete(index=TARGET_INDEX)
        else:
            print(f"    [dry-run] Would delete and recreate.")

    source_mapping = es.indices.get_mapping(index=SOURCE_INDEX).body
    mapping = build_mapping(source_mapping)

    index_body = {
        "settings": {
            "index": {
                "number_of_shards": 4,
                "number_of_replicas": 0,
                "mapping": {
                    "total_fields": {
                        "limit": 2000
                    }
                }
            }
        },
        "mappings": mapping["mappings"],
    }

    if dry_run:
        print(f"[dry-run] Would create index '{TARGET_INDEX}' with:")
        print(f"  Shards: {index_body['settings']['index']['number_of_shards']}")
        print(f"  Replicas: {index_body['settings']['index']['number_of_replicas']}")
        print(f"  Vector dims: {EMBED_DIM}")
        print(f"  Properties count: {len(index_body['mappings']['properties'])}")
        return

    es.indices.create(index=TARGET_INDEX, body=index_body)
    print(f"[+] Created index '{TARGET_INDEX}' ({EMBED_DIM} dims, cosine similarity)")


def scroll_and_embed(es, batch_size=50, dry_run=False, limit=None):
    """
    Scroll through fatboy_data, embed each doc, bulk-index into vec_fatboy_data.
    """
    total = es.count(index=SOURCE_INDEX)["count"]
    if limit:
        total = min(total, limit)
    print(f"[i] Source index '{SOURCE_INDEX}' has {total:,} documents"
          + (f" (limited to {limit:,})" if limit else ""))

    if dry_run:
        # Just show first 3 docs' text
        result = es.search(index=SOURCE_INDEX, size=3).body
        for hit in result["hits"]["hits"]:
            doc = hit["_source"]
            text = build_text(doc)
            print(f"\n[dry-run] _id={hit['_id']}")
            print(f"  Text length: {len(text)} chars")
            print(f"  Text preview: {text[:200]}...")
        return

    # Initialize scroll
    scroll_time = "5m"
    result = es.search(
        index=SOURCE_INDEX,
        scroll=scroll_time,
        size=batch_size,
        body={"query": {"match_all": {}}},
    )
    scroll_id = result["_scroll_id"]
    hits = result["hits"]["hits"]
    processed = 0
    errors = 0
    start_time = time.time()

    print(f"[i] Starting indexing with batch_size={batch_size}...")

    while hits:
        if limit and processed >= limit:
            print(f"[i] Reached limit of {limit:,} docs, stopping.")
            break
        actions = []
        docs_batch = []

        for hit in hits:
            doc = hit["_source"]
            text = build_text(doc)
            if not text.strip():
                continue
            docs_batch.append((hit["_id"], doc, text))
            if limit and len(docs_batch) + processed >= limit:
                break

        if docs_batch:
            # Embed all texts in this batch
            texts = [t for _, _, t in docs_batch]
            try:
                vectors = embed_batch(texts)
            except Exception as e:
                print(f"[!] Embedding error: {e}")
                print(f"    Retrying one-by-one...")
                vectors = []
                for t in texts:
                    try:
                        vectors.append(embed_text(t))
                    except Exception as e2:
                        print(f"[!] Failed to embed: {e2}")
                        vectors.append([0.0] * EMBED_DIM)

            now_iso = datetime.utcnow().isoformat() + "Z"
            for (doc_id, doc, text), vector in zip(docs_batch, vectors):
                # Use the same _id so re-runs are idempotent
                actions.append({"index": {"_index": TARGET_INDEX, "_id": doc_id}})
                actions.append({
                    **doc,
                    "embedding": vector,
                    "embedded_text": text[:10000],  # cap stored text
                    "embedded_at": now_iso,
                })

            if actions:
                try:
                    # Build the NDJSON body for the bulk API
                    body = []
                    for a in actions:
                        body.append(json.dumps(a))
                    bulk_body = "\n".join(body) + "\n"
                    resp = es.bulk(body=bulk_body, refresh=False)
                    if resp.body.get("errors"):
                        err_count = sum(1 for item in resp.body["items"] if "error" in item.get("index", {}))
                        errors += err_count
                        processed += len(actions) // 2 - err_count
                    else:
                        processed += len(actions) // 2
                except Exception as e:
                    print(f"[!] Bulk index error: {e}")
                    errors += len(actions) // 2

        # Progress
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        pct = (processed / total) * 100 if total > 0 else 0
        print(
            f"  Processed: {processed:,}/{total:,} ({pct:.1f}%) | "
            f"Errors: {errors} | Rate: {rate:.1f} docs/s | "
            f"Elapsed: {elapsed:.0f}s"
        )

        # Next scroll
        try:
            result = es.scroll(scroll_id=scroll_id, scroll=scroll_time)
            scroll_id = result["_scroll_id"]
            hits = result["hits"]["hits"]
        except Exception:
            hits = []

    # Clear scroll
    try:
        es.clear_scroll(scroll_id=scroll_id)
    except Exception:
        pass

    elapsed = time.time() - start_time
    print(f"\n[+] Done! Indexed {processed:,} docs in {elapsed:.0f}s")
    if errors:
        print(f"[!] {errors} errors during indexing")

    # Refresh and verify
    es.indices.refresh(index=TARGET_INDEX)
    target_count = es.count(index=TARGET_INDEX)["count"]
    print(f"[i] Target index '{TARGET_INDEX}' now has {target_count:,} documents")


def verify_index(es):
    """Quick sanity check on the new index."""
    print("\n=== Verification ===")

    # Count
    count = es.count(index=TARGET_INDEX)["count"]
    print(f"Document count: {count:,}")

    # Sample doc with embedding
    result = es.search(
        index=TARGET_INDEX,
        size=1,
        body={"_source": ["description", "title", "embedding", "embedded_text", "embedded_at"]},
    ).body
    hits = result["hits"]["hits"]
    if hits:
        doc = hits[0]["_source"]
        emb = doc.get("embedding", [])
        print(f"Sample doc embedding length: {len(emb)}")
        print(f"Embedding first 5 values: {emb[:5]}")
        print(f"Embedded text preview: {doc.get('embedded_text', '')[:150]}...")
        print(f"Embedded at: {doc.get('embedded_at', 'N/A')}")

    # Test kNN search
    print("\n--- kNN Search Test ---")
    query_text = "military deployment activity"
    try:
        query_vec = embed_text(query_text)
        knn_result = es.search(
            index=TARGET_INDEX,
            size=3,
            body={
                "knn": {
                    "field": "embedding",
                    "query_vector": query_vec,
                    "k": 3,
                    "num_candidates": 100,
                },
                "_source": ["description", "title", "activity_name", "location_name"],
            },
        )
        print(f"Query: '{query_text}'")
        for hit in knn_result["hits"]["hits"]:
            src = hit["_source"]
            print(f"  Score: {hit['_score']:.4f} | {src.get('description', '')[:100]}...")
    except Exception as e:
        print(f"kNN search failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Create vec_fatboy_data index with nomic-embed-text 768-dim vectors"
    )
    parser.add_argument("--create-only", action="store_true", help="Only create the index")
    parser.add_argument("--index-only", action="store_true", help="Only run indexing (index must exist)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without doing it")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for indexing (default: 50)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of docs to index (for dev/test)")
    parser.add_argument("--verify", action="store_true", help="Run verification after indexing")
    parser.add_argument("--skip-verify", action="store_true", help="Skip verification")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  Vector Index Creator")
    print(f"  Source: {SOURCE_INDEX} -> Target: {TARGET_INDEX}")
    print(f"  Model: {OLLAMA_MODEL} ({EMBED_DIM} dims)")
    print(f"  Ollama: http://{OLLAMA_HOST}:{OLLAMA_PORT}")
    print(f"  Elasticsearch: {ES_SCHEME}://{ES_HOST}:{ES_PORT}")
    print("=" * 60)

    es = get_es()

    # Check connection
    try:
        health = es.cluster.health().body
        print(f"[i] Cluster: {health['cluster_name']} ({health['status']})")
    except Exception as e:
        print(f"[!] Cannot connect to Elasticsearch: {e}")
        sys.exit(1)

    # Check Ollama
    try:
        r = req_lib.get(f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        if OLLAMA_MODEL not in models and f"{OLLAMA_MODEL}:latest" not in models:
            print(f"[!] Model '{OLLAMA_MODEL}' not found in Ollama. Available: {models}")
            sys.exit(1)
        print(f"[i] Ollama model '{OLLAMA_MODEL}' is available")
    except Exception as e:
        print(f"[!] Cannot connect to Ollama: {e}")
        sys.exit(1)

    if not args.index_only:
        create_index(es, dry_run=args.dry_run)

    if not args.create_only and not args.dry_run:
        scroll_and_embed(es, batch_size=args.batch_size, dry_run=args.dry_run, limit=args.limit)

    if not args.skip_verify and not args.dry_run:
        verify_index(es)

    print("\n[+] All done!")


if __name__ == "__main__":
    main()
