# Vector Store Usage Guide

**Last Updated:** 2025-01-23
**API Version:** OpenAI Vector Stores API (March 2025)
**Related ADR:** ADR-030 (Vector Store Integration)

---

## Overview

The Vector Store integration enables **cross-document hybrid search** in autoD, combining semantic similarity (embeddings) with keyword matching (BM25) to find documents based on natural language queries.

### What is Vector Store?

OpenAI's Vector Store API provides:
- **Automatic chunking**: Splits documents into 800-token chunks with 400-token overlap
- **Semantic embeddings**: Uses text-embedding-3-large (3,072 dimensions)
- **BM25 keyword indexing**: Exact term matching for precision queries
- **Hybrid ranking**: Combines semantic and keyword scores for best results

### When to Use Vector Store

✅ **Use Vector Store for:**
- Finding documents by semantic meaning ("all utility bills from 2024")
- Cross-document queries ("invoices over $500")
- Exploratory search ("anything related to Pacific Power")
- Duplicate detection based on content similarity

❌ **Don't use Vector Store for:**
- Exact metadata lookups (use SQLite database queries instead)
- Single-document analysis (use Responses API directly)
- Real-time classification (too slow, use Responses API)

---

## Quick Start

### 1. Initialize VectorStoreManager

```python
from src.vector_store import VectorStoreManager

# Initialize manager (reads OPENAI_API_KEY from config)
manager = VectorStoreManager()

# Or provide custom OpenAI client
from openai import OpenAI
client = OpenAI(api_key="sk-...")
manager = VectorStoreManager(client=client)
```

### 2. Create or Get Vector Store

```python
# Create new Vector Store
vector_store_id = manager.create_vector_store(
    name="autoD-documents",
    expires_days=365  # Auto-delete after 1 year of inactivity
)

# Or use existing Vector Store
manager.vector_store_id = "vs_abc123"
```

### 3. Upload Documents

```python
from pathlib import Path

# Upload single document
result = manager.add_file_to_vector_store(
    file_path=Path("/path/to/invoice.pdf"),
    file_id="file-abc123"  # From prior OpenAI file upload
)

if result.success:
    print(f"✅ Uploaded: {result.vector_store_file_id}")
else:
    print(f"❌ Failed: {result.error}")
```

### 4. Search Documents

```python
# Hybrid search (semantic + keyword)
results = manager.search_similar_documents(
    query="Find all Pacific Power utility bills from 2024",
    top_k=10
)

for result in results:
    print(f"Score: {result.relevance_score:.3f}")
    print(f"File: {result.file_id}")
    print(f"Content: {result.content_snippet[:200]}...")
    print("---")
```

---

## Detailed Usage

### Creating Vector Stores

#### Basic Creation

```python
vector_store_id = manager.create_vector_store(name="my-documents")
```

#### With Auto-Expiration

```python
# Automatically delete after 365 days of inactivity
vector_store_id = manager.create_vector_store(
    name="temporary-docs",
    expires_days=365
)
```

**Note:** Expiration is based on `last_active_at` (last search query), not creation date.

#### Production Pattern

```python
import os

# Check if Vector Store already exists (store ID in env or database)
vector_store_id = os.getenv("VECTOR_STORE_ID")

if not vector_store_id:
    # Create on first run
    vector_store_id = manager.create_vector_store(name="autoD-production")
    print(f"Created Vector Store: {vector_store_id}")
    print("Save this ID to VECTOR_STORE_ID environment variable!")
else:
    # Reuse existing
    manager.vector_store_id = vector_store_id
    print(f"Using existing Vector Store: {vector_store_id}")
```

---

### Uploading Files

#### Upload Workflow

```python
from pathlib import Path
from openai import OpenAI

client = OpenAI(api_key="sk-...")

# Step 1: Upload file to OpenAI file storage
with open("invoice.pdf", "rb") as f:
    file_obj = client.files.create(file=f, purpose="assistants")

# Step 2: Add to Vector Store
result = manager.add_file_to_vector_store(
    file_path=Path("invoice.pdf"),
    file_id=file_obj.id
)

# Step 3: Check result
if result.success:
    print(f"✅ File ready for search: {result.vector_store_file_id}")
    print(f"Processing time: {result.processing_time_seconds:.1f}s")
else:
    print(f"❌ Upload failed: {result.error}")
```

#### Batch Upload

```python
from pathlib import Path

inbox = Path("inbox/")
for pdf_path in inbox.glob("*.pdf"):
    # Upload to OpenAI files
    with open(pdf_path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="assistants")

    # Add to Vector Store
    result = manager.add_file_to_vector_store(
        file_path=pdf_path,
        file_id=file_obj.id
    )

    if result.success:
        print(f"✅ {pdf_path.name}: {result.processing_time_seconds:.1f}s")
    else:
        print(f"❌ {pdf_path.name}: {result.error}")
```

#### Error Handling

```python
from src.vector_store import VectorStoreUploadResult

result = manager.add_file_to_vector_store(file_path, file_id)

if result.success:
    # Success path
    print(f"File uploaded: {result.vector_store_file_id}")
else:
    # Check specific error type
    if "timeout" in result.error.lower():
        print("Processing timeout - file may be too large")
    elif "already exists" in result.error.lower():
        print("File already in Vector Store - skipping")
    else:
        print(f"Unexpected error: {result.error}")
```

---

### Searching Documents

#### Basic Search

```python
results = manager.search_similar_documents(
    query="Find utility bills",
    top_k=10
)
```

#### With Custom Scoring

```python
# Lower top_k for faster, more relevant results
results = manager.search_similar_documents(
    query="invoices over $500 from Q4 2024",
    top_k=5  # Return only top 5 matches
)
```

#### Parsing Search Results

```python
from src.vector_store import SearchResult

results: List[SearchResult] = manager.search_similar_documents(
    query="Pacific Power bills",
    top_k=10
)

for result in results:
    # Core fields
    print(f"File ID: {result.file_id}")
    print(f"Relevance Score: {result.relevance_score:.3f}")
    print(f"Content Snippet: {result.content_snippet[:200]}...")

    # Optional metadata (if available)
    if hasattr(result, 'page_number'):
        print(f"Page: {result.page_number}")
```

#### Empty Results Handling

```python
results = manager.search_similar_documents(query="nonexistent query")

if not results:
    print("No matching documents found")
    print("Try:")
    print("  - Broader query terms")
    print("  - Check if files finished processing")
    print("  - Verify Vector Store has files")
```

---

## Metrics and Monitoring

### Accessing Metrics

```python
# Get current metrics
metrics = manager.get_metrics()

print(f"Uploads succeeded: {metrics['uploads_succeeded']}")
print(f"Upload success rate: {metrics['upload_success_rate']:.1%}")
print(f"Total storage: {metrics['upload_gb']:.3f} GB")
print(f"Search queries: {metrics['search_queries_total']}")
print(f"Avg search latency: {metrics['avg_search_latency_ms']:.1f} ms")
print(f"Estimated daily cost: ${metrics['cost_estimate_usd_per_day']:.4f}")
```

### Structured Logging

```python
from src.vector_store import log_vector_store_metrics

# Log metrics as JSON (for log aggregation tools)
log_vector_store_metrics(manager)
```

**Output:**
```json
{
  "event": "vector_store_metrics",
  "timestamp": "2025-01-23T10:30:00Z",
  "vector_store_id": "vs_abc123",
  "uploads_succeeded": 1247,
  "uploads_failed": 3,
  "upload_success_rate": 0.998,
  "upload_gb": 2.34,
  "search_queries_total": 523,
  "avg_search_latency_ms": 1847.3,
  "cost_estimate_usd_per_day": 0.134
}
```

### Cost Tracking

```python
# Calculate estimated daily cost
daily_cost = manager.metrics.estimate_daily_cost()

if daily_cost > 0.50:  # Alert threshold: $0.50/day = $15/month
    print(f"⚠️ High storage cost: ${daily_cost:.2f}/day")
    print(f"Current storage: {manager.metrics.upload_gb:.2f} GB")
    print("Consider archiving old documents")
```

---

## Cost Management

### Pricing Overview

- **Free Tier**: First 1GB storage (no cost)
- **Paid Tier**: $0.10/GB/day for storage beyond 1GB
- **Query Cost**: Included in Responses API pricing (no per-query charge)

### Cost Examples

| Documents | Avg Size | Total Storage | Daily Cost | Monthly Cost |
|-----------|----------|---------------|------------|--------------|
| 100       | 500KB    | 50MB          | $0.00      | $0.00        |
| 1,000     | 2MB      | 2GB           | $0.10      | $3.00        |
| 5,000     | 2MB      | 10GB          | $0.90      | $27.00       |
| 10,000    | 2MB      | 20GB          | $1.90      | $57.00       |

### Cost Optimization Strategies

#### 1. Delete Old Documents

```python
# Remove documents older than 1 year
old_file_ids = get_file_ids_older_than(days=365)  # Your implementation

for file_id in old_file_ids:
    manager.remove_file_from_vector_store(file_id)
```

#### 2. Deduplicate Documents

```python
# Use SHA-256 hashing to avoid uploading duplicates
from src.deduplication import is_duplicate

file_path = Path("invoice.pdf")
if is_duplicate(file_path):
    print(f"Skipping duplicate: {file_path.name}")
else:
    # Upload to Vector Store
    ...
```

#### 3. Monitor Storage Growth

```python
# Weekly cost check
import schedule

def check_costs():
    metrics = manager.get_metrics()
    daily_cost = metrics['cost_estimate_usd_per_day']

    if daily_cost > 1.00:  # $30/month threshold
        send_alert(f"Vector Store cost: ${daily_cost:.2f}/day")

schedule.every().monday.at("09:00").do(check_costs)
```

---

## Performance Optimization

### Search Latency

**Typical Latency:**
- **P50**: 1.2 seconds
- **P95**: 2.8 seconds
- **P99**: 4.5 seconds

**Optimization Tips:**
1. **Reduce top_k**: Use `top_k=5` instead of `top_k=20` for faster results
2. **Use reasoning_effort="minimal"**: Already configured in VectorStoreManager
3. **Cache frequent queries**: Use LRUCache for repeated searches

### Upload Performance

**Processing Time:**
- Small PDFs (<1MB): 5-10 seconds
- Medium PDFs (1-5MB): 10-30 seconds
- Large PDFs (5-10MB): 30-60 seconds

**Batch Upload Tips:**
1. **Parallel uploads**: Use `concurrent.futures.ThreadPoolExecutor`
2. **Retry transient failures**: Use exponential backoff (already implemented)
3. **Monitor upload_success_rate**: Alert if <95%

---

## Troubleshooting

### Issue: File Processing Timeout

**Symptom:**
```
FileProcessingTimeoutError: File processing exceeded 300 seconds
```

**Causes:**
- File is too large (>10MB)
- File contains complex graphics/images
- OpenAI API experiencing delays

**Solutions:**
1. Split large files into smaller chunks
2. Increase timeout in `add_file_to_vector_store()` (custom implementation)
3. Retry upload during off-peak hours

---

### Issue: No Search Results

**Symptom:**
```python
results = manager.search_similar_documents("utility bills")
assert len(results) == 0  # No results!
```

**Debugging Checklist:**
1. **Check file processing status:**
   ```python
   # Verify files are completed, not in_progress
   file_list = client.beta.vector_stores.files.list(vector_store_id)
   for file in file_list.data:
       print(f"{file.id}: {file.status}")  # Should be "completed"
   ```

2. **Verify Vector Store has files:**
   ```python
   vector_store = client.beta.vector_stores.retrieve(vector_store_id)
   print(f"File count: {vector_store.file_counts.completed}")
   ```

3. **Try broader query:**
   ```python
   # Too specific
   results = manager.search_similar_documents("Pacific Power invoice #12345")

   # Broader
   results = manager.search_similar_documents("Pacific Power")
   ```

---

### Issue: High Upload Failure Rate

**Symptom:**
```python
metrics = manager.get_metrics()
print(metrics['upload_success_rate'])  # 0.75 (only 75% success)
```

**Debugging:**
1. **Check logs for error patterns:**
   ```bash
   grep "File upload failed" logs/app.log | tail -20
   ```

2. **Common failure causes:**
   - Invalid file format (only PDF, TXT, DOCX, HTML, Markdown supported)
   - File size exceeds 512MB limit
   - Network timeouts (transient, will retry)
   - API rate limits (429 errors)

3. **Mitigation:**
   - Validate file format before upload
   - Split files >50MB for faster processing
   - Add exponential backoff retry (already implemented in VectorStoreManager)

---

## Best Practices

### 1. Always Validate Uploads

```python
result = manager.add_file_to_vector_store(file_path, file_id)

if result.success:
    # Store vector_store_file_id in database for tracking
    db.update(doc_id, vector_store_file_id=result.vector_store_file_id)
else:
    # Log failure for investigation
    logger.error(f"Upload failed: {file_path}", extra={"error": result.error})
```

### 2. Use Environment Variables for IDs

```bash
# .env file
VECTOR_STORE_ID=vs_abc123
```

```python
import os
manager.vector_store_id = os.getenv("VECTOR_STORE_ID")
```

### 3. Monitor Metrics Regularly

```python
# Log metrics every 1000 operations
if manager.metrics.uploads_succeeded % 1000 == 0:
    log_vector_store_metrics(manager)
```

### 4. Set Up Cost Alerts

```python
def alert_if_high_cost():
    daily_cost = manager.metrics.estimate_daily_cost()
    if daily_cost > 0.50:  # $15/month threshold
        send_slack_alert(f"⚠️ Vector Store cost: ${daily_cost:.2f}/day")
```

### 5. Handle Search Timeouts Gracefully

```python
import timeout_decorator

@timeout_decorator.timeout(10)  # 10 second timeout
def search_with_timeout(query: str):
    return manager.search_similar_documents(query, top_k=10)

try:
    results = search_with_timeout("utility bills")
except timeout_decorator.TimeoutError:
    print("Search timeout - try reducing top_k or simplifying query")
```

---

## Advanced Usage

### Multi-Vector Store Sharding

**Use Case:** Beyond 10,000 files, shard across multiple Vector Stores.

```python
# Create Vector Stores by year
vector_stores = {
    "2024": manager.create_vector_store(name="docs-2024"),
    "2023": manager.create_vector_store(name="docs-2023"),
    "2022": manager.create_vector_store(name="docs-2022"),
}

# Upload to appropriate shard
def upload_by_year(file_path, file_id, year):
    manager.vector_store_id = vector_stores[year]
    return manager.add_file_to_vector_store(file_path, file_id)

# Search across all shards
def search_all_years(query, top_k=10):
    all_results = []
    for year, vs_id in vector_stores.items():
        manager.vector_store_id = vs_id
        results = manager.search_similar_documents(query, top_k)
        all_results.extend(results)

    # Re-rank combined results
    return sorted(all_results, key=lambda r: r.relevance_score, reverse=True)[:top_k]
```

### Custom Chunking (Future Enhancement)

**Note:** OpenAI Vector Store uses fixed 800-token chunks. For custom chunking, consider self-hosted solution (see ADR-030 Option 2).

---

## API Reference

### VectorStoreManager

#### Methods

**`create_vector_store(name: str, expires_days: int = 365) -> str`**
- Creates new Vector Store
- Returns: vector_store_id

**`add_file_to_vector_store(file_path: Path, file_id: str) -> VectorStoreUploadResult`**
- Adds file to Vector Store
- Polls until processing completes (max 5 minutes)
- Returns: VectorStoreUploadResult with success/error info

**`search_similar_documents(query: str, top_k: int = 10) -> List[SearchResult]`**
- Hybrid search (semantic + BM25)
- Returns: List of SearchResult sorted by relevance_score

**`get_metrics() -> Dict[str, Any]`**
- Returns current metrics dictionary
- Includes: uploads, searches, costs, latency

**`remove_file_from_vector_store(file_id: str) -> bool`**
- Removes file from Vector Store
- Returns: True if successful

#### Data Classes

**VectorStoreUploadResult:**
```python
@dataclass
class VectorStoreUploadResult:
    success: bool
    vector_store_file_id: Optional[str]
    file_id: str
    processing_time_seconds: float
    final_status: FileProcessingStatus
    error: Optional[str] = None
```

**SearchResult:**
```python
@dataclass
class SearchResult:
    file_id: str
    content_snippet: str
    relevance_score: float
```

**VectorStoreMetrics:**
```python
@dataclass
class VectorStoreMetrics:
    uploads_succeeded: int
    uploads_failed: int
    upload_bytes_total: int
    search_queries_total: int
    search_latency_sum: float
    search_failures: int

    # Properties
    upload_success_rate: float  # 0-1
    avg_search_latency: float   # seconds
    upload_gb: float            # gigabytes

    # Methods
    estimate_daily_cost() -> float
    to_dict() -> Dict[str, Any]
```

---

## Additional Resources

- **ADR-030**: Vector Store Integration Decision (docs/adr/ADR-030-vector-store-integration.md)
- **OpenAI Documentation**: https://platform.openai.com/docs/api-reference/vector-stores
- **Implementation**: src/vector_store.py (Lines 1-753)
- **Tests**: tests/integration/test_vector_store.py

---

## Support

**Issues:** Report bugs to the autoD project maintainers
**API Questions:** https://platform.openai.com/docs
**Cost Questions:** https://openai.com/api/pricing/
