"""Performance benchmarks for embedding cache."""

import time
from typing import List

from src.cache import EmbeddingCache, generate_cache_key


class TestCachePerformance:
    """Performance benchmarks for cache operations."""

    def test_cache_lookup_latency_single(self):
        """Benchmark single cache lookup performance (target: <5ms P95)."""
        cache = EmbeddingCache()
        embedding = [0.1] * 1536  # text-embedding-3-small dimension

        # Populate cache with test data
        cache.set("benchmark_key", embedding)

        # Warm up (JIT compilation, etc.)
        for _ in range(100):
            cache.get("benchmark_key")

        # Measure lookup time over 10,000 iterations
        iterations = 10_000
        latencies: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            _ = cache.get("benchmark_key")
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        # Calculate statistics
        avg_latency_ms = sum(latencies) / len(latencies)
        latencies_sorted = sorted(latencies)
        p50_ms = latencies_sorted[len(latencies) // 2]
        p95_ms = latencies_sorted[int(len(latencies) * 0.95)]
        p99_ms = latencies_sorted[int(len(latencies) * 0.99)]

        # Report results
        print("\n=== Cache Lookup Latency (Single Key) ===")
        print(f"Iterations: {iterations:,}")
        print(f"Average: {avg_latency_ms:.4f}ms")
        print(f"P50: {p50_ms:.4f}ms")
        print(f"P95: {p95_ms:.4f}ms")
        print(f"P99: {p99_ms:.4f}ms")

        # Performance targets
        assert avg_latency_ms < 0.1, f"Average latency too high: {avg_latency_ms:.4f}ms"
        assert p95_ms < 5.0, f"P95 latency too high: {p95_ms:.4f}ms (target: <5ms)"
        assert p99_ms < 10.0, f"P99 latency too high: {p99_ms:.4f}ms"

    def test_cache_lookup_latency_full_cache(self):
        """Benchmark lookup performance with full cache (1000 entries)."""
        cache = EmbeddingCache(max_entries=1000)
        embedding = [0.1] * 1536

        # Fill cache to capacity
        for i in range(1000):
            cache.set(f"key{i:04d}", embedding)

        # Measure lookup time for entries throughout cache
        iterations = 1000
        latencies: List[float] = []

        for i in range(iterations):
            key = f"key{i:04d}"
            start = time.perf_counter()
            _ = cache.get(key)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        # Calculate statistics
        avg_latency_ms = sum(latencies) / len(latencies)
        latencies_sorted = sorted(latencies)
        p95_ms = latencies_sorted[int(len(latencies) * 0.95)]

        print("\n=== Cache Lookup Latency (Full Cache) ===")
        print("Cache size: 1000 entries")
        print(f"Iterations: {iterations}")
        print(f"Average: {avg_latency_ms:.4f}ms")
        print(f"P95: {p95_ms:.4f}ms")

        # With 1000 entries, lookup should still be fast (dict-based)
        assert avg_latency_ms < 0.1, f"Average latency degraded: {avg_latency_ms:.4f}ms"
        assert p95_ms < 5.0, f"P95 latency degraded: {p95_ms:.4f}ms"

    def test_cache_set_latency(self):
        """Benchmark cache set operation performance."""
        cache = EmbeddingCache(max_entries=1000)
        embedding = [0.1] * 1536

        iterations = 1000
        latencies: List[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            cache.set(f"key{i:04d}", embedding)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        avg_latency_ms = sum(latencies) / len(latencies)
        latencies_sorted = sorted(latencies)
        p95_ms = latencies_sorted[int(len(latencies) * 0.95)]

        print("\n=== Cache Set Latency ===")
        print(f"Iterations: {iterations}")
        print(f"Average: {avg_latency_ms:.4f}ms")
        print(f"P95: {p95_ms:.4f}ms")

        # Set operations should be fast (no eviction overhead yet)
        assert avg_latency_ms < 1.0, f"Set latency too high: {avg_latency_ms:.4f}ms"
        assert p95_ms < 2.0, f"P95 set latency too high: {p95_ms:.4f}ms"

    def test_cache_eviction_latency(self):
        """Benchmark LRU eviction performance."""
        cache = EmbeddingCache(max_entries=100)
        embedding = [0.1] * 1536

        # Fill cache to capacity
        for i in range(100):
            cache.set(f"init_key{i}", embedding)

        # Measure eviction overhead (each set triggers eviction)
        iterations = 100
        latencies: List[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            cache.set(f"evict_key{i}", embedding)  # Triggers LRU eviction
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        avg_latency_ms = sum(latencies) / len(latencies)
        latencies_sorted = sorted(latencies)
        p95_ms = latencies_sorted[int(len(latencies) * 0.95)]

        print("\n=== Cache Eviction Latency ===")
        print(f"Evictions: {iterations}")
        print(f"Average: {avg_latency_ms:.4f}ms")
        print(f"P95: {p95_ms:.4f}ms")

        # Eviction should add minimal overhead
        assert avg_latency_ms < 2.0, f"Eviction too slow: {avg_latency_ms:.4f}ms"
        assert p95_ms < 5.0, f"P95 eviction too slow: {p95_ms:.4f}ms"

    def test_cache_memory_overhead(self):
        """Verify cache memory efficiency (minimal overhead)."""
        cache = EmbeddingCache()
        embedding = [0.1] * 1536

        # Expected size per embedding
        expected_size_per_embedding = len(embedding) * 8  # 8 bytes per float64

        # Add single embedding
        cache.set("key1", embedding)

        actual_size = cache.metrics.size_bytes
        overhead_pct = ((actual_size / expected_size_per_embedding) - 1) * 100

        print("\n=== Cache Memory Overhead ===")
        print(f"Expected size: {expected_size_per_embedding:,} bytes")
        print(f"Actual size: {actual_size:,} bytes")
        print(f"Overhead: {overhead_pct:.2f}%")

        # Allow reasonable overhead for tracking structures
        assert overhead_pct < 10, f"Memory overhead too high: {overhead_pct:.2f}%"

    def test_cache_memory_efficiency_realistic(self):
        """Test cache with realistic workload (100 embeddings)."""
        cache = EmbeddingCache(max_entries=100, max_size_bytes=100 * 1024 * 1024)
        embedding = [0.1] * 1536  # 12,288 bytes per embedding

        # Add 100 embeddings
        for i in range(100):
            cache.set(f"doc{i:03d}", embedding)

        expected_total = 100 * (len(embedding) * 8)  # 100 * 12,288 bytes
        actual_total = cache.metrics.size_bytes
        efficiency_pct = (expected_total / actual_total) * 100

        print("\n=== Cache Memory Efficiency (100 Embeddings) ===")
        print(f"Expected: {expected_total / (1024**2):.2f} MB")
        print(f"Actual: {actual_total / (1024**2):.2f} MB")
        print(f"Efficiency: {efficiency_pct:.2f}%")
        print(f"Entries: {cache.metrics.entries}")

        # Should be highly efficient (>90%)
        assert efficiency_pct >= 90, f"Memory efficiency too low: {efficiency_pct:.2f}%"
        assert cache.metrics.entries == 100

    def test_cache_hit_rate_realistic_workload(self):
        """Test cache hit rate with realistic access patterns."""
        cache = EmbeddingCache(max_entries=100)
        embedding = [0.1] * 1536

        # Populate cache with documents
        num_docs = 50
        for i in range(num_docs):
            cache.set(f"doc{i:03d}", embedding)

        # Simulate realistic access pattern:
        # - 70% access to recent documents (high temporal locality)
        # - 20% access to random documents
        # - 10% new documents
        import random

        iterations = 1000
        for _ in range(iterations):
            rand = random.random()

            if rand < 0.7:
                # Access recent document (high hit rate)
                doc_id = random.randint(max(0, num_docs - 20), num_docs - 1)
                cache.get(f"doc{doc_id:03d}")
            elif rand < 0.9:
                # Access random document
                doc_id = random.randint(0, num_docs - 1)
                cache.get(f"doc{doc_id:03d}")
            else:
                # New document (cache miss)
                num_docs += 1
                cache.set(f"doc{num_docs:03d}", embedding)

        hit_rate = cache.metrics.hit_rate
        print("\n=== Cache Hit Rate (Realistic Workload) ===")
        print(f"Iterations: {iterations}")
        print(f"Hits: {cache.metrics.hits}")
        print(f"Misses: {cache.metrics.misses}")
        print(f"Hit Rate: {hit_rate:.2f}%")

        # With temporal locality, expect >60% hit rate
        assert hit_rate >= 60.0, f"Hit rate too low: {hit_rate:.2f}% (target: ≥60%)"

    def test_cache_key_generation_performance(self):
        """Benchmark cache key generation (SHA-256 hashing)."""
        iterations = 10_000
        latencies: List[float] = []

        for i in range(iterations):
            doc_hash = f"document_hash_{i:06d}_" + "x" * 50  # Realistic hash length
            model = "text-embedding-3-small"

            start = time.perf_counter()
            _ = generate_cache_key(doc_hash, model)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        avg_latency_ms = sum(latencies) / len(latencies)
        latencies_sorted = sorted(latencies)
        p95_ms = latencies_sorted[int(len(latencies) * 0.95)]

        print("\n=== Cache Key Generation Performance ===")
        print(f"Iterations: {iterations:,}")
        print(f"Average: {avg_latency_ms:.4f}ms")
        print(f"P95: {p95_ms:.4f}ms")

        # Key generation should be very fast (<0.1ms average)
        assert avg_latency_ms < 0.1, f"Key generation too slow: {avg_latency_ms:.4f}ms"
        assert p95_ms < 0.5, f"P95 key generation too slow: {p95_ms:.4f}ms"

    def test_cache_throughput_sequential(self):
        """Measure cache throughput for sequential access."""
        cache = EmbeddingCache(max_entries=1000)
        embedding = [0.1] * 1536

        # Populate cache
        for i in range(1000):
            cache.set(f"key{i:04d}", embedding)

        # Measure sequential access throughput
        iterations = 10_000
        start = time.perf_counter()

        for i in range(iterations):
            key = f"key{i % 1000:04d}"  # Cycle through 1000 keys
            _ = cache.get(key)

        elapsed_sec = time.perf_counter() - start
        throughput = iterations / elapsed_sec

        print("\n=== Cache Throughput (Sequential) ===")
        print(f"Operations: {iterations:,}")
        print(f"Duration: {elapsed_sec:.2f}s")
        print(f"Throughput: {throughput:,.0f} lookups/sec")

        # Should achieve >1M lookups/sec on modern hardware
        assert throughput >= 100_000, f"Throughput too low: {throughput:,.0f} ops/sec"

    def test_cache_scalability_large_cache(self):
        """Test cache performance with large number of entries."""
        # Test with 10,000 entries (10x default max)
        cache = EmbeddingCache(max_entries=10_000, max_size_bytes=500 * 1024 * 1024)
        embedding = [0.1] * 1536

        # Populate large cache
        print("\n=== Cache Scalability (10K entries) ===")
        start = time.perf_counter()

        for i in range(10_000):
            cache.set(f"doc{i:05d}", embedding)

        populate_time = time.perf_counter() - start
        print(f"Population time: {populate_time:.2f}s")
        print(f"Avg set time: {(populate_time / 10_000) * 1000:.4f}ms")

        # Measure lookup performance with large cache
        iterations = 1000
        lookup_latencies: List[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            _ = cache.get(f"doc{i:05d}")
            elapsed_ms = (time.perf_counter() - start) * 1000
            lookup_latencies.append(elapsed_ms)

        avg_lookup_ms = sum(lookup_latencies) / len(lookup_latencies)
        p95_lookup_ms = sorted(lookup_latencies)[int(len(lookup_latencies) * 0.95)]

        print(f"Lookup latency (avg): {avg_lookup_ms:.4f}ms")
        print(f"Lookup latency (P95): {p95_lookup_ms:.4f}ms")

        # Performance should scale well (dict-based lookup is O(1))
        assert (
            avg_lookup_ms < 0.2
        ), f"Lookup degraded with large cache: {avg_lookup_ms:.4f}ms"
        assert p95_lookup_ms < 5.0, f"P95 lookup degraded: {p95_lookup_ms:.4f}ms"
