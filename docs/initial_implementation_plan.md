

## 0) What you’re building (at a glance)

* **Input:** a scanned PDF placed in an intake folder.
* **Process:** upload → (optional) dedupe pre‑check → Responses API call with PDF + vector store → strict JSON back (metadata, actions, summaries, OCR excerpts) → persist to DB → rename/move file → add/update vector‑store attributes for future dedupe.
* **Control knobs:** `reasoning_effort` and `verbosity` for GPT‑5 (omit parameters if your deployment doesn’t list them). **Do not send `temperature`** to GPT‑5 in Responses; unsupported params can cause validation errors. ([OpenAI Platform][1])

Key platform features we rely on:

* **Structured Outputs** (JSON Schema) to guarantee well‑formed, parseable JSON. ([OpenAI Platform][2])
* **Responses API** (PDF file input, previous_response_id, persisted reasoning between tool calls). ([OpenAI Platform][3])
* **File Search (Vector Stores)** for cross‑doc context, chunking/embeddings, and hybrid retrieval; attach the store to the request. ([OpenAI Platform][4])
* **Prompt caching** is automatic for long, repeated prefixes; you’ll see cache hits in `usage.prompt_tokens_details.cached_tokens`. Keep big prompts stable. ([OpenAI Platform][5])

---

## 1) Message roles and request shape (Responses API)

Use three messages:

* **system** — minimal guardrails (e.g., “follow developer instructions strictly”).
* **developer** — your canonical Paper Autopilot rules (classification/extraction/foldering/OCR budgets). Keep this block **identical** across calls to maximize prompt caching. ([OpenAI Platform][5])
* **user** — per‑file context: `processed_at` (UTC ISO timestamp you generate), `original_file_name`, and the **PDF attached** as `{"type":"input_file","file_id":"..."} `. PDFs are supported as direct inputs to Responses on multimodal models. ([OpenAI Platform][3])

Enforce strict JSON via **Structured Outputs**. In Responses, set the **text format** to a JSON schema with `strict: true` so the model can only emit valid JSON that conforms to your schema. ([OpenAI Platform][2])

You **may** add GPT‑5 steering parameters:

* `reasoning_effort`: `"minimal" | "low" | "medium" | "high"`
* `verbosity`: `"low" | "medium" | "high"`
  Only include these if your specific GPT‑5 deployment lists them (they’re model‑dependent). For this workflow, prefer **`reasoning_effort="minimal"`** and **`verbosity="low"`** because the output is schema‑locked JSON. ([OpenAI][6])

---

## 2) Developer prompt (drop‑in; keep identical across runs)

> **Put this entire block in the `developer` role.** Don’t change it per file. It references large OCR budgets as requested and adds actionability fields (key points, action items, deadlines, urgency, email‑ready fields). Keep it stable to benefit from prompt caching. ([OpenAI Platform][5])

```
You are a **File Systems Architect / Archival Specialist** for “Paper Autopilot”.

GOAL
Return a single JSON object that matches the provided JSON schema exactly (the API enforces it). Output JSON only. If uncertain, use null. Do not invent values.

INPUTS YOU MAY SEE
- A scanned/digital PDF (often multi‑page, image‑only).
- A user message that includes:
  • processed_at (UTC ISO 8601) → echo EXACTLY into `processed_date`.
  • original_file_name → echo EXACTLY into `original_file_name`.
  • Optional hints (base_path, property names, known issuers).

PRIMARY TASKS
1) CLASSIFY: set `category` (enum), `subcategory` (enum), and `doc_type` (free text).
2) EXTRACT FIELDS if present (use null if absent): amount_due, due_date, account_number,
   invoice_number, statement_date, period_start_date, period_end_date, balance, currency,
   policy_number, claim_number, loan_number, service_address/property_address, tax_id,
   customer_name, email, phone, meter_readings.
3) TITLES & SUMMARIES (for email context):
   - `title`: human-friendly title (not a filename).
   - `brief_description`: 1–2 sentences (~≤ 300 chars).
   - `long_description`: short synopsis (~≤ 1,200 chars).
   - `summary_long`: executive summary (~½ page; ~1,200–2,000 chars).
   - `email_subject`, `email_preview_text` (≤ 160 chars), `email_body_markdown`
     (concise, scannable; include amounts, due dates, and required actions).
4) KEY POINTS & ACTIONS:
   - `key_points`: concise bullets with salient facts/flags (e.g., “past due”, “renew by <date>”).
   - `action_items`: list of actionable tasks; for each include: description, assignee_suggestion,
     due (ISO or human text), priority (high/medium/low), blocking (bool), rationale.
   - `deadline`: operative deadline if any (ISO date if explicit; otherwise clear natural‑language).
   - `deadline_source`: one of ["explicit_due_date","implied_in_text","inferred_from_context","none"].
   - `urgency_score`: 0–100 + `urgency_reason`: 1–3 sentences.
5) FILE NAMING & PLACEMENT:
   - `suggested_file_name` (no extension). Sanitize to ASCII; remove slashes/newlines.
     Prefer: `YYYY-MM-DD – {issuer} – {doc_type} – {short_topic}`; ≤ 150 chars.
   - `suggested_relative_path`: compact path like
     `Financial & Administrative/Bills/Utilities` or `Property & Assets/[Property]/Insurance`.
6) OCR & VISUAL (heavy budgets, per request):
   - `ocr_text_excerpt`: up to **40,000 characters**; if longer, end with “ … (truncated)”.
   - `ocr_page_summaries`: for each page: {page, text_excerpt (≤ **8,000 chars**), image_description}.
     Use best effort even for image‑only scans (describe layout/logos/stamps).
7) DEDUPE & CROSS‑DOC NORMALIZATION:
   - `content_signature`: first ~512 chars of normalized text (heuristic fingerprint).
   - `cross_doc_matches`: if similar docs are found (via File Search results), list matches with score/rationale.
   - `normalization`: canonical issuer name, canonical account label, property identifier, if inferable.
8) TAGS: 5–12 concise tags (issuer, doc_type, lifecycle flags like `due_soon`, domain like `utilities`, property IDs).
9) PII SAFETY: Keep masked values masked (e.g., ****1234).
10) DATES:
    - Prefer ISO `YYYY-MM-DD` for date‑only fields.
    - For `processed_date`, echo the provided `processed_at` exactly (ISO date‑time allowed).
11) NULL RIGOR: If ambiguous or conflicting, output null rather than guessing.

CATEGORIES (enum)
- category ∈ ["Financial & Administrative","Property & Assets","Personal & Family",
              "Business & Professional","Legal & Government","Household & Lifestyle",
              "Creative & Miscellaneous"]
- subcategory (best‑fit or null) ∈ ["Bills","Invoices","Receipts","Banking","Taxes","Investments",
              "Loans & Mortgages","Insurance","Legal","Government","Medical","Education",
              "Property Management","Utilities","Telecom","Subscriptions","Payroll","HR",
              "Travel","Vehicle","Misc"]

OUTPUT
Return ONLY the JSON object that matches the schema. No markdown, no extra text.
```

---

## 3) Python (upload → vector store → cached prompt → Responses → parse → persist)

**Notes that matter:**

* **Don’t send `temperature`** for GPT‑5 with Responses unless your model’s ref page lists it; unsupported params can 4xx.
* Use **PDF as `input_file`** on the **user** message. ([OpenAI Platform][3])
* Attach **File Search** to Responses by enabling the tool and attaching your **vector store** to the call. ([OpenAI Platform][7])
* **Structured Outputs**: pass a **JSON Schema** via `text.format` with `strict:true` (or `response_format` on older SDKs). ([OpenAI Platform][2])
* **Prompt caching** is automatic. Keep system/developer messages identical to maximize cached tokens (inspect `usage.prompt_tokens_details.cached_tokens`). ([OpenAI Platform][5])

```python
# pip install --upgrade openai tiktoken sqlalchemy pydantic PyPDF2
import os, sys, json, base64, hashlib, datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from openai import OpenAI
import tiktoken  # for preflight token estimates (approximate)
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, Boolean, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from PyPDF2 import PdfReader  # optional: page_count

# ---------- CONFIG ----------
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")  # use your GPT‑5 variant
PDF_PATH = "/path/to/input.pdf"

DB_URL = os.getenv("PAPER_AUTOPILOT_DB_URL", "sqlite:///paper_autopilot.db")
VECTOR_STORE_NAME = os.getenv("PAPER_AUTOPILOT_VECTOR_STORE_NAME", "Paper Autopilot Corpus")
VSTORE_ID_PATH = os.getenv("PAPER_AUTOPILOT_VECTOR_STORE_ID_FILE", "./.paper_autopilot_vs_id")

# Pricing (USD per 1K tokens). Keep in env so you can update without code changes.
# Include a discounted rate for cached prompt tokens if your plan lists one.
INPUT_USD_PER_1K = float(os.getenv("PA_INPUT_USD_PER_1K", "0.00"))
OUTPUT_USD_PER_1K = float(os.getenv("PA_OUTPUT_USD_PER_1K", "0.00"))
CACHED_INPUT_USD_PER_1K = float(os.getenv("PA_CACHED_INPUT_USD_PER_1K", "0.00"))

SYSTEM_PROMPT = "You are a careful, reliable assistant. Follow developer instructions strictly."

DEVELOPER_PROMPT = r"""(Paste the Developer Prompt block from Section 2 here verbatim.)"""

# ---------- DB SETUP ----------
Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Local file identity
    original_file_name = Column(String(512))
    sha256_hex = Column(String(64), unique=True, index=True)  # dedupe key
    sha256_b64 = Column(String(100))
    page_count = Column(Integer)

    # OpenAI
    source_file_id = Column(String(64), index=True)     # Files API id for this run
    vector_store_id = Column(String(64), index=True)    # persistent corpus id
    vector_store_file_id = Column(String(64), index=True)

    # Extracted / normalized
    processed_date = Column(String(64), index=True)
    category = Column(String(128))
    subcategory = Column(String(128))
    doc_type = Column(String(256))
    issuer = Column(String(256))
    primary_date = Column(String(64))
    due_date = Column(String(64))
    amount_due = Column(Float)
    deadline = Column(String(128))
    urgency_score = Column(Integer)

    suggested_file_name = Column(String(512))
    suggested_relative_path = Column(String(1024))
    tags_json = Column(JSON)
    summary = Column(Text)
    title = Column(Text)
    brief_description = Column(Text)
    long_description = Column(Text)
    summary_long = Column(Text)
    email_subject = Column(Text)
    email_preview_text = Column(Text)
    email_body_markdown = Column(Text)

    # OCR
    ocr_text_excerpt = Column(Text)
    content_signature = Column(Text)

    # Raw full JSON from the model
    model_json = Column(JSON)

# ---------- Helpers ----------
def sha256_file(path: str) -> (str, str):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    digest = h.digest()
    return h.hexdigest(), base64.b64encode(digest).decode("ascii")

def get_tokenizer(model: str):
    """
    Try to use model-specific encoding; fall back to o200k_base, then cl100k_base.
    GPT‑5 commonly maps to o200k* encodings.
    """
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        try:
            return tiktoken.get_encoding("o200k_base")
        except Exception:
            return tiktoken.get_encoding("cl100k_base")

def estimate_tokens(text: str, model: str) -> int:
    enc = get_tokenizer(model)
    return len(enc.encode(text or ""))

# ---------- OpenAI client ----------
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ---------- Vector store ----------
def get_or_create_vector_store() -> str:
    """Load a persistent vector store ID or create one."""
    if os.path.exists(VSTORE_ID_PATH):
        return Path(VSTORE_ID_PATH).read_text().strip()
    vs = client.vector_stores.create(name=VECTOR_STORE_NAME)
    Path(VSTORE_ID_PATH).write_text(vs.id)
    return vs.id

def add_file_to_vector_store(vector_store_id: str, file_id: str, *, attributes: Optional[Dict[str, Any]] = None) -> str:
    """
    Attach a Files API file to the vector store for File Search.
    Attributes (metadata) can be set/updated on vector store files (up to 16 key-value pairs).
    """
    vs_file = client.vector_stores.files.create(vector_store_id=vector_store_id, file_id=file_id)
    # Optional: update attributes (metadata) after creation
    if attributes:
        client.vector_stores.files.update(
            vector_store_id=vector_store_id,
            file_id=vs_file.id,
            attributes=attributes
        )
    return vs_file.id

# ---------- JSON Schema (built per-file to lock consts) ----------
def build_schema(file_id: str, processed_at_iso: str, original_name: str) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            # Tracking (locked)
            "processed_date": {"type": "string", "const": processed_at_iso},
            "original_file_name": {"type": "string", "const": original_name},
            "source_file_id": {"type": "string", "const": file_id},

            # Titles & summaries
            "title": {"type": ["string","null"]},
            "brief_description": {"type": ["string","null"]},
            "long_description": {"type": ["string","null"]},
            "summary_long": {"type": ["string","null"]},
            "email_subject": {"type": ["string","null"]},
            "email_preview_text": {"type": ["string","null"]},
            "email_body_markdown": {"type": ["string","null"]},

            # Classification
            "category": {
                "type": "string",
                "enum": [
                    "Financial & Administrative","Property & Assets","Personal & Family",
                    "Business & Professional","Legal & Government","Household & Lifestyle",
                    "Creative & Miscellaneous"
                ]
            },
            "subcategory": {
                "type": ["string","null"],
                "enum": [
                    "Bills","Invoices","Receipts","Banking","Taxes","Investments",
                    "Loans & Mortgages","Insurance","Legal","Government","Medical",
                    "Education","Property Management","Utilities","Telecom","Subscriptions",
                    "Payroll","HR","Travel","Vehicle","Misc", None
                ]
            },
            "doc_type": {"type": ["string","null"]},

            # Parties & dates
            "issuer": {"type": ["string","null"]},
            "author_organization": {"type": ["string","null"]},
            "author_individual": {"type": ["string","null"]},
            "primary_date": {"type": ["string","null"]},
            "period_start_date": {"type": ["string","null"]},
            "period_end_date": {"type": ["string","null"]},

            # Core summary
            "summary": {"type": ["string","null"]},

            # Actionability
            "key_points": {"type": "array", "items": {"type": "string"}},
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "description": {"type": "string"},
                        "assignee_suggestion": {"type": ["string","null"]},
                        "due": {"type": ["string","null"]},
                        "priority": {"type": ["string","null"]},
                        "blocking": {"type": ["boolean","null"]},
                        "rationale": {"type": ["string","null"]}
                    },
                    "required": ["description"]
                }
            },
            "deadline": {"type": ["string","null"]},
            "deadline_source": {
                "type": "string",
                "enum": ["explicit_due_date","implied_in_text","inferred_from_context","none"]
            },
            "urgency_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "urgency_reason": {"type": ["string","null"]},

            # Extracted fields
            "extracted_fields": {
                "type": "object",
                "properties": {
                    "amount_due": {"type": ["number","null"]},
                    "due_date": {"type": ["string","null"]},
                    "account_number": {"type": ["string","null"]},
                    "invoice_number": {"type": ["string","null"]},
                    "statement_date": {"type": ["string","null"]},
                    "balance": {"type": ["number","null"]},
                    "service_address": {"type": ["string","null"]},
                    "property_address": {"type": ["string","null"]},
                    "policy_number": {"type": ["string","null"]},
                    "claim_number": {"type": ["string","null"]},
                    "loan_number": {"type": ["string","null"]},
                    "meter_readings": {"type": ["string","null"]},
                    "tax_id": {"type": ["string","null"]},
                    "currency": {"type": ["string","null"]},
                    "customer_name": {"type": ["string","null"]},
                    "email": {"type": ["string","null"]},
                    "phone": {"type": ["string","null"]}
                },
                "additionalProperties": True
            },

            # Org & dedupe
            "suggested_file_name": {"type": "string", "minLength": 1, "maxLength": 150},
            "suggested_relative_path": {"type": ["string","null"]},
            "tags": {"type": "array", "items": {"type": "string"}},
            "language": {"type": ["string","null"]},
            "page_count": {"type": ["integer","null"]},

            # OCR outputs (length caps enforced by instruction text)
            "ocr_text_excerpt": {"type": ["string","null"]},
            "ocr_page_summaries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "page": {"type": "integer"},
                        "text_excerpt": {"type": "string"},
                        "image_description": {"type": "string"}
                    },
                    "required": ["page","text_excerpt","image_description"]
                }
            },

            "content_signature": {"type": ["string","null"]},
            "cross_doc_matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "vector_store_id": {"type": ["string","null"]},
                        "file_id": {"type": ["string","null"]},
                        "filename": {"type": ["string","null"]},
                        "score": {"type": ["number","null"]},
                        "rationale": {"type": ["string","null"]}
                    },
                    "required": ["score"]
                }
            },
            "normalization": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "canonical_issuer": {"type": ["string","null"]},
                    "canonical_account_label": {"type": ["string","null"]},
                    "property_identifier": {"type": ["string","null"]}
                }
            },

            "errors": {"type": "array", "items": {"type": "string"}}
        },
        "required": [
            "processed_date","original_file_name","source_file_id",
            "category","subcategory","suggested_file_name","summary"
        ]
    }

# ---------- Boot DB ----------
engine = create_engine(DB_URL, future=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# ---------- Preflight dedupe (file-level) ----------
pdf_path = Path(PDF_PATH)
sha_hex, sha_b64 = sha256_file(str(pdf_path))

exists = session.query(Document).filter_by(sha256_hex=sha_hex).first()
if exists:
    print(f"[SKIP] Already processed {pdf_path.name} (sha256={sha_hex})")
    sys.exit(0)

# Optional: page count for bookkeeping
try:
    page_count = len(PdfReader(str(pdf_path)).pages)
except Exception:
    page_count = None

# ---------- Upload PDF (inline to this request) ----------
inline_file = client.files.create(file=open(PDF_PATH, "rb"), purpose="user_data")

# ---------- Create/load vector store ----------
vs_id = (Path(VSTORE_ID_PATH).read_text().strip()
         if os.path.exists(VSTORE_ID_PATH) else get_or_create_vector_store())

# ---------- Build per-file schema (locks tracking fields) ----------
processed_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
schema = build_schema(inline_file.id, processed_at, pdf_path.name)

# ---------- Build user message ----------
USER_PROMPT = f"""Context for this file:
- processed_at (UTC ISO 8601): {processed_at}
- original_file_name: {pdf_path.name}

Instructions:
- Set `processed_date` to processed_at exactly.
- Set `original_file_name` exactly.
- Use the attached PDF only; do not fabricate values.
- Return only JSON per the schema.
"""

# ---------- Responses call ----------
# GPT‑5 steering (include only if supported in your deployment):
reasoning_effort = os.getenv("PA_REASONING_EFFORT")  # e.g., "minimal"
verbosity = os.getenv("PA_VERBOSITY")               # e.g., "low"

create_kwargs = dict(
    model=MODEL,
    tools=[{"type": "file_search"}],
    attachments=[{"vector_store_id": vs_id}],
    input=[
        {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
        {"role": "developer", "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}]},
        {"role": "user", "content": [
            {"type": "input_text", "text": USER_PROMPT},
            {"type": "input_file", "file_id": inline_file.id}
        ]}
    ],
    # Structured Outputs: JSON Schema (strict)
    text={
        "format": {
            "type": "json_schema",
            "json_schema": {
                "name": "paper_autopilot_metadata_v3",
                "schema": schema,
                "strict": True
            }
        }
    },
    # Large output budgets (subject to model caps)
    max_output_tokens=60000
)

# Add GPT‑5 steering params only if set (avoid unsupported param errors)
if reasoning_effort:
    create_kwargs["reasoning_effort"] = reasoning_effort
if verbosity:
    create_kwargs["verbosity"] = verbosity

resp = client.responses.create(**create_kwargs)

# ---------- Token/cost tracking ----------
# Usage object typically includes prompt/output tokens and cached prompt tokens.
usage = getattr(resp, "usage", None)
if usage:
    prompt_tokens = getattr(usage, "prompt_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    cached = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details and isinstance(details, dict):
        cached = int(details.get("cached_tokens", 0))
    # Cost estimation (parametrize prices in env)
    billable_input = max(prompt_tokens - cached, 0)
    estimated_cost = (
        (billable_input / 1000.0) * INPUT_USD_PER_1K +
        (cached / 1000.0) * CACHED_INPUT_USD_PER_1K +
        (output_tokens / 1000.0) * OUTPUT_USD_PER_1K
    )
    print({
        "prompt_tokens": prompt_tokens,
        "cached_prompt_tokens": cached,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(estimated_cost, 6)
    })

# ---------- Parse JSON result ----------
out_json = resp.output_text  # Strict JSON per schema
data = json.loads(out_json)

# ---------- Persist to DB ----------
doc = Document(
    original_file_name=data["original_file_name"],
    processed_date=data["processed_date"],
    source_file_id=data["source_file_id"],
    vector_store_id=vs_id,
    sha256_hex=sha_hex,
    sha256_b64=sha_b64,
    page_count=page_count,

    category=data.get("category"),
    subcategory=data.get("subcategory"),
    doc_type=data.get("doc_type"),
    issuer=data.get("issuer"),
    primary_date=data.get("primary_date"),

    due_date=(data.get("extracted_fields") or {}).get("due_date"),
    amount_due=(data.get("extracted_fields") or {}).get("amount_due"),
    deadline=data.get("deadline"),
    urgency_score=data.get("urgency_score"),

    suggested_file_name=data.get("suggested_file_name"),
    suggested_relative_path=data.get("suggested_relative_path"),
    tags_json=data.get("tags"),
    summary=data.get("summary"),

    title=data.get("title"),
    brief_description=data.get("brief_description"),
    long_description=data.get("long_description"),
    summary_long=data.get("summary_long"),
    email_subject=data.get("email_subject"),
    email_preview_text=data.get("email_preview_text"),
    email_body_markdown=data.get("email_body_markdown"),

    ocr_text_excerpt=data.get("ocr_text_excerpt"),
    content_signature=data.get("content_signature"),

    model_json=data  # full payload for audit/debug
)
session.add(doc)
session.commit()

# ---------- Post-write: attach a copy to vector store with attributes for future dedupe ----------
# (Optional but recommended) Upload the same PDF specifically for the vector store and attach attributes.
# Use purpose="assistants" for files destined for vector stores.
vs_file = client.files.create(file=open(PDF_PATH, "rb"), purpose="assistants")
vs_file_id = add_file_to_vector_store(
    vs_id, vs_file.id,
    attributes={
        # Up to 16 key-value pairs (64-char keys, 512-char values are typical limits)
        "sha256_hex": sha_hex,
        "original_file_name": data["original_file_name"],
        "processed_date": data["processed_date"],
        "issuer": (data.get("issuer") or "")[:512],
        "doc_type": (data.get("doc_type") or "")[:512],
        "primary_date": (data.get("primary_date") or "")[:64],
        "content_sig_256": hashlib.sha256((data.get("content_signature") or "").encode("utf-8")).hexdigest()[:64],
        "document_id": str(doc.id)
    }
)
doc.vector_store_file_id = vs_file_id
session.commit()

print(f"[OK] Processed {pdf_path.name} → doc.id={doc.id}")
```

**Why these pieces:**

* **Structured Outputs** prevents schema drift and lets you parse without heuristics. ([OpenAI Platform][2])
* **PDF as input** unlocks OCR/vision extraction within the model; no pre‑processing required on your side. ([OpenAI Platform][3])
* **File Search (Vector Stores)**: OpenAI handles parsing/chunking/embeddings + hybrid retrieval; attaching the store gives cross‑doc context and makes dedupe easier. ([OpenAI Platform][4])
* **Prompt caching**: the large, stable `developer` message will be cached; you’ll see `cached_tokens` in usage. ([OpenAI Platform][5])

---

## 4) Dedupe strategy (pre & post)

**Before processing**

1. Compute **file SHA‑256** (we store both hex and base64).
2. Check the local DB for `sha256_hex` — if present, **skip**. (Fast path.)
3. Optionally query your vector store for a file with matching metadata (if you maintain a `sha256_hex` attribute on vector‑store files). If your deployment doesn’t expose attribute filters, you can keep a local index and treat vector store as a secondary signal. (File Search supports hybrid retrieval and metadata‑aware filtering in current docs; exact filter APIs vary by surface.) ([OpenAI Platform][4])

**After processing**

1. Store the model’s **`content_signature`** (first ~512 normalized chars) and (optionally) a **hash** of it.
2. Add the PDF to the **vector store** and attach attributes (metadata). OpenAI objects commonly support up to **16 key‑value metadata pairs**, with length limits for keys/values—use these for dedupe and routing. ([OpenAI Platform][8])

---

## 5) What to store server‑side (DB) vs. vector‑store attributes

**Database (authoritative, unlimited):**

* `sha256_hex`, `sha256_b64`, `source_file_id`, `vector_store_file_id`, `vector_store_id`
* All JSON metadata (normalized fields, action items, deadlines, urgency, titles/summaries)
* OCR excerpt + `content_signature`
* Suggested path/filename, tags, etc.

**Vector‑store file attributes (fast filter / cross‑doc context, up to ~16 kv pairs):**

* `sha256_hex` (primary dedupe key)
* `content_sig_256` (hash of normalized text signature)
* `issuer` (canonical), `doc_type`, `primary_date` (YYYY‑MM‑DD), `due_date`, `amount_due` (string), `property_identifier` (if any)
* `processed_date`, `original_file_name`, `document_id` (DB PK)

These attributes keep lookups cheap on the server side and let you pre‑filter candidates before vector retrieval. (Docs describe metadata/attributes for vector stores; limits are key/value count and length.) ([OpenAI Platform][8])

---

## 6) Token & cost tracking (preflight + actuals)

* **Actuals:** read `resp.usage.prompt_tokens`, `resp.usage.output_tokens`, and `resp.usage.prompt_tokens_details.cached_tokens` for cache hits; then multiply by your price per 1K tokens (environment variables in the code). ([OpenAI Platform][9])
* **Preflight estimate:** approximate with `tiktoken` using the model’s encoder (GPT‑5 models typically map to `o200k_*`). Estimation is helpful for budgeting UI but actual billing follows the API’s `usage`. ([GitHub][10])

---

## 7) GPT‑5 prompting guide alignment (what we changed)

* We **omit `temperature`** and prefer schema‑locked JSON; this matches “instruction adherence” guidance and avoids unsupported‑param errors on some GPT‑5 deployments.
* We keep a **concise system message** and put all rules in **developer**; this maximizes **prompt caching** (stable large prefix). ([OpenAI Platform][5])
* If you want even tighter control, set **`reasoning_effort="minimal"`** and **`verbosity="low"`** (only if your deployment lists those params). This reduces agentic eagerness and verbosity while keeping file_search retrieval. ([OpenAI][6])
* For multi‑step workflows, you can chain calls using **`previous_response_id`** to pass reasoning context. (Useful if you split “classify/extract” and “draft email” into separate turns.) ([OpenAI Platform][11])

---

## 8) Database choice

Use **SQLite** for local/dev and **PostgreSQL (or Supabase)** for production; both work with SQLAlchemy and JSON fields. PostgreSQL gives you:

* **JSONB** for raw model payloads and tags
* Strong indexing (btree, GIN on JSONB)
* Straightforward migration path if you start in SQLite

The code above defaults to SQLite but will run unchanged against Postgres by switching `DB_URL`.

---

## 9) Optional: batching & throughput

If you process large intake folders, consider the **Batch API** to push many classification jobs asynchronously at lower cost/overheads. Keep the same request shape but batch files. ([OpenAI Platform][12])

---

## 10) Minimal user message template (per file)

```
Context for this file:
- processed_at (UTC ISO 8601): <your timestamp>
- original_file_name: <name.pdf>

Instructions:
- Set `processed_date` to processed_at exactly.
- Set `original_file_name` exactly.
- Use the attached PDF only; do not fabricate values.
- Return only JSON per the schema.
```

Attach the PDF in the same **user** message: `{"type":"input_file","file_id":"<uploaded id>"}`. ([OpenAI Platform][3])

---

## 11) Final reminders (practical)

* **Strict JSON**: Using Structured Outputs with `strict:true` will fail fast if the schema can’t be satisfied—log errors and retry if needed. ([OpenAI Platform][2])
* **File Search**: You get hybrid retrieval over your corpus; add prior months’ statements to the vector store so the model normalizes issuer/account naming and flags duplicates. ([OpenAI Platform][4])
* **Prompt caching**: You don’t need extra code; keep system/developer prompts identical and watch `cached_tokens` in responses. ([OpenAI Platform][5])
* **GPT‑5 params**: Only include `reasoning_effort`/`verbosity` if your model page lists them. Do **not** include `temperature` for GPT‑5 Responses unless your specific deployment supports it. ([OpenAI][6])

This is everything an engineer needs to implement the end‑to‑end pipeline, with actionability fields, large OCR budgets (40k / 8k page excerpts), dedupe, vector store metadata, token/cost tracking, and a database to persist results.

[1]: https://platform.openai.com/docs/models/gpt-5?utm_source=chatgpt.com "Model - OpenAI API"
[2]: https://platform.openai.com/docs/guides/structured-outputs?utm_source=chatgpt.com "Structured model outputs - OpenAI API"
[3]: https://platform.openai.com/docs/guides/pdf-files?api-mode=responses&utm_source=chatgpt.com "pdf-files?api-mode=responses"
[4]: https://platform.openai.com/docs/assistants/tools/file-search?utm_source=chatgpt.com "Assistants File Search - OpenAI API"
[5]: https://platform.openai.com/docs/guides/prompt-caching?utm_source=chatgpt.com "Prompt caching - OpenAI API"
[6]: https://openai.com/index/introducing-gpt-5-for-developers/?utm_source=chatgpt.com "Introducing GPT‑5 for developers"
[7]: https://platform.openai.com/docs/guides/tools-file-search?utm_source=chatgpt.com "File search - OpenAI API"
[8]: https://platform.openai.com/docs/api-reference/usage/vector_stores_object?utm_source=chatgpt.com "API Reference"
[9]: https://platform.openai.com/docs/assistants/migration?utm_source=chatgpt.com "Assistants migration guide - OpenAI API"
[10]: https://github.com/openai/tiktoken?utm_source=chatgpt.com "tiktoken is a fast BPE tokeniser for use with OpenAI's models."
[11]: https://platform.openai.com/docs/guides/prompt-engineering?utm_source=chatgpt.com "Prompt engineering - OpenAI API"
[12]: https://platform.openai.com/docs/guides/batch/batch-api?utm_source=chatgpt.com "Batch API"
