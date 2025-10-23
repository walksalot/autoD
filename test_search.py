#!/usr/bin/env python3
"""
Quick test script for SemanticSearchEngine functionality.

Demonstrates:
- Basic search
- Search with metadata filters
- Document similarity search
- Performance metrics
"""

import os
from openai import OpenAI
from src.embeddings import EmbeddingGenerator
from src.search import SemanticSearchEngine
from src.models import Document, init_db

# Initialize components
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
session = init_db("sqlite:///paper_autopilot.db")
generator = EmbeddingGenerator(client, session)
search_engine = SemanticSearchEngine(generator, session)

print("=" * 70)
print("Semantic Search Engine Test")
print("=" * 70)

# Check if we have documents with embeddings
doc_count = (
    session.query(Document)
    .filter(Document.status == "completed", Document.embedding_vector.isnot(None))
    .count()
)

print(f"\nDocuments with embeddings: {doc_count}")

if doc_count == 0:
    print("\nNo documents with embeddings found.")
    print("Run the embedding generation script first to generate embeddings.")
    exit(0)

# Test 1: Basic search
print("\n" + "=" * 70)
print("Test 1: Basic Search")
print("=" * 70)

query = "invoices"
results = search_engine.search(query, limit=5)

print(f"Query: '{query}'")
print(f"Results: {len(results.results)}")
print(f"Total matches: {results.total_count}")
print(f"Execution time: {results.execution_time_ms:.1f}ms")
print(f"Cache hit: {results.cache_hit}")

for result in results.results:
    doc = result.document
    metadata = doc.metadata_json or {}
    print(f"\n  {result.rank}. {doc.original_filename}")
    print(f"     Similarity: {result.similarity_score:.3f}")
    print(f"     Doc Type: {metadata.get('doc_type', 'N/A')}")
    print(f"     Issuer: {metadata.get('issuer', 'N/A')}")

# Test 2: Search with filters
print("\n" + "=" * 70)
print("Test 2: Search with Filters")
print("=" * 70)

results = search_engine.search(
    query="financial documents", filters={"doc_type": "Invoice"}, limit=3
)

print("Query: 'financial documents' (filtered by doc_type=Invoice)")
print(f"Results: {len(results.results)}")
print(f"Total matches: {results.total_count}")
print(f"Execution time: {results.execution_time_ms:.1f}ms")
print(f"Cache hit: {results.cache_hit}")

for result in results.results:
    doc = result.document
    metadata = doc.metadata_json or {}
    print(f"\n  {result.rank}. {doc.original_filename}")
    print(f"     Similarity: {result.similarity_score:.3f}")
    print(f"     Doc Type: {metadata.get('doc_type', 'N/A')}")

# Test 3: Document similarity search
print("\n" + "=" * 70)
print("Test 3: Find Similar Documents")
print("=" * 70)

# Get a document with embedding
doc = (
    session.query(Document)
    .filter(Document.status == "completed", Document.embedding_vector.isnot(None))
    .first()
)

if doc:
    print(f"Source document: {doc.original_filename}")

    results = search_engine.search_by_document(doc, limit=3)

    print(f"Similar documents: {len(results.results)}")
    print(f"Total matches: {results.total_count}")
    print(f"Execution time: {results.execution_time_ms:.1f}ms")

    for result in results.results:
        similar_doc = result.document
        metadata = similar_doc.metadata_json or {}
        print(f"\n  {result.rank}. {similar_doc.original_filename}")
        print(f"     Similarity: {result.similarity_score:.3f}")
        print(f"     Doc Type: {metadata.get('doc_type', 'N/A')}")

# Test 4: Cache performance
print("\n" + "=" * 70)
print("Test 4: Cache Performance")
print("=" * 70)

# Run same query twice to test caching
query = "monthly reports"

print(f"Query: '{query}' (first run - should cache)")
results1 = search_engine.search(query, limit=5)
print(f"Execution time: {results1.execution_time_ms:.1f}ms")
print(f"Cache hit: {results1.cache_hit}")

print(f"\nQuery: '{query}' (second run - should use cache)")
results2 = search_engine.search(query, limit=5)
print(f"Execution time: {results2.execution_time_ms:.1f}ms")
print(f"Cache hit: {results2.cache_hit}")

# Show cache stats
cache_stats = generator.get_cache_stats()
print("\n" + "=" * 70)
print("Embedding Cache Statistics")
print("=" * 70)
print(f"Cache size: {cache_stats['cache_size']}/{cache_stats['max_cache_size']}")
print(f"Memory cache hits: {cache_stats['memory_cache_hits']}")
print(f"DB cache hits: {cache_stats['db_cache_hits']}")
print(f"Total cache hits: {cache_stats['total_cache_hits']}")
print(f"API calls: {cache_stats['api_calls']}")
print(f"Total requests: {cache_stats['total_requests']}")
print(f"Memory hit rate: {cache_stats['memory_hit_rate']:.1%}")
print(f"Overall hit rate: {cache_stats['overall_hit_rate']:.1%}")
print(f"Total tokens: {cache_stats['total_tokens']:,}")

print("\n" + "=" * 70)
print("All tests completed!")
print("=" * 70)
