# Newsletter Intelligence Pipeline

Distills your newsletter subscriptions into a ranked 10-point brief per topic, once a day.

## Setup

```bash
# 1. Activate the virtualenv (already created)
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create a Google Cloud project, enable the Gmail API, and download
#    the OAuth client credentials JSON. Save it to:
#    ~/.credentials/gmail_credentials.json

# 4. Run the OAuth flow once (opens a browser)
python main.py --auth

# 5. Configure environment variables
cp .env.example .env
# edit .env: set LLM_PROVIDER, ANTHROPIC_API_KEY (or OLLAMA_*), etc.

# 6. Edit config/filters.yaml to match your actual newsletter subscriptions

# 7. Validate without writing output
python main.py --all-categories --dry-run

# 8. Start the daily scheduled job (runs at 7:00 AM local time)
python scheduler.py
```

## Manual runs

```bash
python main.py --category software_ai --hours-back 48
python main.py --all-categories
python main.py --category politics --dry-run
```

Output lands in `outputs/YYYY-MM-DD_{category}.md`, plus a combined
`outputs/YYYY-MM-DD_digest.md`. See `CLAUDE.md` for full architecture notes.
