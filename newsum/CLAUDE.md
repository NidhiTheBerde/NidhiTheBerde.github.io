# Newsletter Intelligence Pipeline
## Claude Code Project Instructions

## Project Overview
An agentic pipeline that connects to a user's email account, detects and categorizes newsletters, extracts key insights using Claude (or a local Llama model via Ollama), and synthesizes a ranked 10-point summary per topic filter. Runs on a daily schedule.

Core problem it solves: A person subscribed to 20+ newsletters across categories (AI/software, politics, shopping, finance) cannot realistically read all of them. This pipeline distills the week's signal into a single structured brief per category.

## Tech Stack
| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Async support, rich email/LLM libraries |
| LLM | Claude API (primary) or Ollama + Llama 3.1 70B (local fallback) | Claude for quality; Ollama for offline/privacy |
| Email access | Gmail API via google-api-python-client | Structured metadata before body parsing |
| Orchestration | Pure Python async (asyncio) | No overengineering; LangGraph optional extension |
| Storage | SQLite (email cache) + JSON (summaries output) | Zero-infrastructure, local-first |
| Scheduling | APScheduler | Embedded cron, no external dependencies |
| Output | Markdown digest + optional HTML artifact | Portable, readable anywhere |

## File Structure
```
newsum/
├── CLAUDE.md                   # This file — project instructions
├── README.md                   # User-facing setup guide
├── .env.example                # Environment variable template
├── requirements.txt            # Python dependencies
│
├── config/
│   └── filters.yaml            # User-defined topic filters and keywords
│
├── agents/
│   ├── __init__.py
│   ├── ingestion.py             # Layer 1: Email fetch agent
│   ├── classifier.py            # Layer 2: Newsletter detection + category classifier
│   ├── extractor.py             # Layer 3: Per-newsletter key point extractor
│   ├── aggregator.py            # Layer 4: Cross-newsletter synthesis → 10-point summary
│   └── delivery.py              # Layer 5: Output formatting + delivery
│
├── core/
│   ├── __init__.py
│   ├── email_client.py          # Gmail API wrapper
│   ├── llm_client.py            # Unified Claude / Ollama client
│   ├── database.py               # SQLite cache layer
│   └── models.py                 # Pydantic data models
│
├── prompts/
│   ├── classify.txt              # Classification prompt template
│   ├── extract.txt               # Key point extraction prompt template
│   └── aggregate.txt             # 10-point synthesis prompt template
│
├── outputs/
│   └── .gitkeep                  # Daily summaries land here as .md files
│
├── scheduler.py                 # APScheduler entry point
└── main.py                      # CLI entry point (manual run)
```

## Data Models (core/models.py)
Define all data structures with Pydantic for validation and serialization: `RawEmail`, `ClassifiedNewsletter`, `ExtractedInsight`, `SummaryPoint`, `DailySummary`.

## Layer 1 — Ingestion Agent (agents/ingestion.py)
Responsibility: Authenticate with Gmail, fetch emails from the last 24 hours (or configurable window), return a list of `RawEmail` objects.

Implementation notes:
- Use `google-auth-oauthlib` for the OAuth2 flow. Credentials are stored in `~/.credentials/gmail_token.json` after first run.
- Request only the `https://www.googleapis.com/auth/gmail.readonly` scope. Never request write access.
- Extract plain text from `text/plain` MIME part first. Fall back to stripping HTML from `text/html` if plain text is absent. Use `beautifulsoup4` for HTML stripping.
- Cache fetched email IDs in SQLite to avoid reprocessing on re-runs within the same day.
- Respect Gmail API rate limits: max 250 quota units per second. Batch `messages.get` calls using the batch endpoint.

Key method signature:
```python
async def fetch_emails(hours_back: int = 24) -> list[RawEmail]:
    ...
```

Gmail query to use:
```
newer_than:1d category:updates OR category:promotions
```
This targets the Gmail tabs where newsletters land, cutting noise before any LLM call.

## Layer 2 — Classifier Agent (agents/classifier.py)
Responsibility: For each raw email, decide (a) is it a newsletter and (b) which filter category does it belong to.

**Step 1: Heuristic pre-filter (no LLM).** Check signals in order (List-Unsubscribe header, known newsletter platform domains, subject keywords). If any match, mark `is_newsletter = True` without an LLM call.

**Step 2: LLM classification (ambiguous cases only).** Use `prompts/classify.txt`. Pass only the first 500 characters of the body to keep latency/cost low. Confidence threshold: only pass emails with `confidence >= 0.7` and `is_newsletter = True` to Layer 3.

## Layer 3 — Extractor Agent (agents/extractor.py)
Responsibility: For each classified newsletter, extract 3–5 structured key insights (atomic, standalone facts — not a summary). Use `prompts/extract.txt`.

Chunking large newsletters: If `body_text` exceeds 6000 tokens, chunk into overlapping segments of 4000 tokens with 500-token overlap. Run extraction on each chunk, then deduplicate insights by semantic similarity before passing to Layer 4.

Run all newsletters in a category concurrently using `asyncio.gather()`.

## Layer 4 — Aggregator Agent (agents/aggregator.py)
Responsibility: Take all `ExtractedInsight` objects for a given category and synthesize exactly 10 ranked, non-redundant summary points. This is the most important layer — quality here determines the product's value. Use `prompts/aggregate.txt`.

Edge cases:
- Fewer than 10 distinct topics: return only what exists. Do not pad with weak content.
- Zero newsletters matched a category: skip aggregation, log at INFO.

## Layer 5 — Delivery Agent (agents/delivery.py)
Responsibility: Format `DailySummary` objects into readable output.
- Output 1: Markdown file, always written to `outputs/YYYY-MM-DD_{category}.md`.
- Output 2 (optional): Unified daily digest at `outputs/YYYY-MM-DD_digest.md` with a table of contents.
- Output 3 (optional): Email to self via `smtplib` + Gmail SMTP, configured via `.env`. Requires an App Password if using Gmail with 2FA.

## Config File (config/filters.yaml)
User-defined categories with keyword hints (software_ai, politics, shopping, finance by default) plus `settings` (hours_back, min_confidence, max_newsletters_per_category, output_dir).

## LLM Client (core/llm_client.py)
Abstract over Claude API and Ollama so the rest of the codebase is model-agnostic. All LLM calls must:
- Wrap JSON parsing in try/except and retry once on malformed output.
- Log token usage to SQLite for cost tracking.
- Have a timeout (30s for Claude, 120s for Ollama).

## Database Schema (core/database.py)
SQLite, three tables: `processed_emails`, `extracted_insights`, `llm_usage`.

## Environment Variables (.env.example)
`LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `GMAIL_CREDENTIALS_PATH`, `SEND_EMAIL_DIGEST`, `SELF_EMAIL`, `SMTP_APP_PASSWORD`, `LOG_LEVEL`, `DB_PATH`.

## Entry Points
Manual run (CLI):
```
python main.py --category software_ai --hours-back 48
python main.py --all-categories
python main.py --category politics --dry-run   # prints without writing
```
Scheduled run:
```
python scheduler.py   # starts APScheduler, runs daily at 7:00 AM local time
```

## Setup Steps
1. `pip install -r requirements.txt`
2. Create Google Cloud project → enable Gmail API → download credentials.json
3. Run `python main.py --auth` to complete OAuth flow (opens browser once)
4. Copy `.env.example` to `.env` and fill in values
5. Edit `config/filters.yaml` to match actual newsletter subscriptions
6. Run `python main.py --all-categories --dry-run` to validate without writing output
7. Run `python scheduler.py` to start the daily job

## Error Handling & Resilience
- Gmail API quota exceeded: exponential backoff with jitter, max 3 retries. Log and skip if still failing.
- LLM returns malformed JSON: retry once with an explicit instruction to return only JSON. If still failing, skip that newsletter and log.
- Zero newsletters matched a filter: log as INFO (not ERROR). Empty summaries are valid — do not fabricate content.
- Ollama timeout: if a local model call exceeds 120s, skip that newsletter and log a WARNING. Do not crash the pipeline.
- Duplicate processing: the `processed_emails` table prevents reprocessing the same email ID. Always check before calling any LLM.

## Extension Points (not in scope for v1)
| Feature | How to add |
|---|---|
| Semantic deduplication | Add ChromaDB; embed each insight with text-embedding-3-small; cosine similarity > 0.85 = duplicate |
| Slack delivery | Add `slack_sdk`; post digest as formatted blocks to a channel |
| Web UI | FastAPI + Jinja2 serving `outputs/*.md` as HTML; sortable by date and category |
| Multi-email provider | Abstract `email_client.py` behind an interface; add Outlook via Microsoft Graph |
| User feedback loop | Let user mark points as "not relevant" → stored in SQLite → used as few-shot examples in future classification prompts |
| Newsletter auto-discovery | At first run, scan the last 30 days of email and present candidate newsletters for the user to approve |
