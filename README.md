this is project for linkdin serch network
# liai — LinkedIn AI Networking Assistant

> **AI-powered CLI to find relevant professionals, analyse profiles, generate personalised connection notes, and organise your outreach — without ever sending automated requests.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 **Smart Search** | Filter by title, company, industry, skills, location, experience level |
| 🤖 **AI Analysis** | GPT-powered summaries, networking scores (0–10), interest mapping |
| ✉️ **Connection Notes** | Personalised notes ≤ 300 chars with refinement support |
| 💬 **Conversation Starters** | AI-generated, profile-specific ice-breakers |
| 👀 **Preview Mode** | Interactive approve / edit / skip / open flow |
| 📊 **Reports** | CSV, Excel, JSON, and HTML with score breakdowns |
| 📁 **Local Storage** | SQLite database — everything stays on your machine |
| 🔐 **Manual Login Only** | You log in; liai never stores your password |

---

# Clone the repository
git clone https://github.com/tr285/Linkdin_request_cli_tool.git

# Enter the project
cd Linkdin_request_cli_tool

# Create a virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Install the project
pip install -e .

# Install Playwright
pip install playwright

# Download Chromium
python -m playwright install chromium

# Verify the CLI
liai --help

### 2. Configure

```bash
# Copy the example config
cp .env.example .env

# Edit .env and set your OpenAI API key
OPENAI_API_KEY=sk-...your-key-here...
```

### 3. Run diagnostics

```bash
liai doctor
```

---

## 📖 Usage

### Login

```bash
# Open LinkedIn in your browser for manual login
liai login

# Check if your session is still valid
liai login --check
```

### Search

```bash
# Interactive prompts
liai search --interactive

# Filters via flags
liai search --title "ML Engineer" --company "Google" --city "San Francisco" --max 30

# Additional filter options
liai search \
  --keywords "machine learning" \
  --title "Data Scientist" \
  --industry "Technology" \
  --country "United States" \
  --skills "Python,PyTorch" \
  --experience mid-senior \
  --max 50
```

### Analyze

```bash
# Analyze all new profiles
liai analyze

# Analyze a specific profile
liai analyze --id 42

# Re-analyze already-analyzed profiles
liai analyze --reanalyze

# Only show results above score 7
liai analyze --min-score 7.0

# Process up to 100 profiles
liai analyze --limit 100
```

### Preview (Interactive Review)

```bash
# Review all analyzed profiles
liai preview

# Only show profiles scoring 7+
liai preview --min-score 7.0

# During review, for each profile:
#   [A]pprove — marks for manual outreach
#   [E]dit    — edit the connection note (AI refinement optional)
#   [O]pen    — opens the profile in your browser
#   [S]kip    — marks as skipped
#   [Q]uit    — exit review
```

### Open a Profile

```bash
liai open 42                              # by database ID
liai open https://linkedin.com/in/johndoe  # by URL
```

### Export

```bash
liai export --format csv
liai export --format excel
liai export --format json
liai export --format html
liai export --format all            # generates all 4 formats

# Filter by status
liai export --format csv --status approved
```

### Report

```bash
# Terminal summary report
liai report

# Show top 20 profiles
liai report --top 20 --min-score 6.0
```

### Configuration

```bash
# Show all settings
liai config --show

# Update a setting
liai config --set openai_model --value gpt-4o
liai config --set theme --value light
liai config --set headless --value true

# Reset to default
liai config --reset theme
```

### Other

```bash
liai version    # Show version and dependency info
liai doctor     # Environment health check
liai --help     # Full help
```

---

## 🗂️ Project Structure

```
linkedin-ai-cli/
├── linkedin_ai/
│   ├── cli.py             # Typer root — registers all commands
│   ├── config.py          # Pydantic Settings — env var loading
│   ├── database.py        # SQLite schema + CRUD
│   ├── cache.py           # Disk-based JSON cache with TTL
│   ├── settings.py        # Runtime settings (DB-backed)
│   ├── logger.py          # Loguru multi-sink setup
│   ├── utils.py           # Shared helpers (retry, text, etc.)
│   ├── browser.py         # Playwright browser context
│   ├── auth.py            # LinkedIn session management
│   ├── search.py          # People search scraper
│   ├── profile.py         # Full profile scraper
│   ├── ai.py              # OpenAI integration
│   ├── analyzer.py        # Batch analysis orchestrator
│   ├── messaging.py       # Note templates & editing
│   ├── report.py          # CSV/Excel/JSON/HTML generation
│   ├── exporter.py        # Export pipeline
│   ├── models/            # Pydantic data models
│   │   ├── profile.py
│   │   ├── search.py
│   │   ├── analysis.py
│   │   └── report.py
│   ├── commands/          # One file per CLI command
│   │   ├── login.py
│   │   ├── search.py
│   │   ├── analyze.py
│   │   ├── preview.py
│   │   ├── open.py
│   │   ├── export.py
│   │   ├── report.py
│   │   ├── config.py
│   │   ├── version.py
│   │   └── doctor.py
│   └── templates/
│       └── report.html.jinja2
├── tests/
│   ├── conftest.py
│   ├── test_database.py
│   ├── test_models.py
│   ├── test_analyzer.py
│   └── test_ai.py
├── database/              # SQLite database (auto-created)
├── cache/                 # Profile cache files (auto-created)
├── reports/               # Exported reports (auto-created)
├── logs/                  # Log files (auto-created)
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## 🗄️ Database Schema

```sql
profiles         — Scraped profile data (URL, name, headline, skills, etc.)
searches         — Search history with filters and result counts
search_results   — Many-to-many link between searches and profiles
analyses         — AI-generated summaries, scores, notes, starters
report_runs      — History of generated reports
settings         — User-configurable runtime settings
```

---

## ⚙️ Configuration Reference

| Key | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Your OpenAI API key (required for AI features) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `OPENAI_MAX_TOKENS` | `2048` | Max tokens per API call |
| `OPENAI_TEMPERATURE` | `0.7` | Creativity (0.0–2.0) |
| `LIAI_THEME` | `dark` | CLI theme: `dark` or `light` |
| `LIAI_LOG_LEVEL` | `INFO` | Logging level |
| `LIAI_HEADLESS` | `false` | Headless browser mode |
| `LIAI_RATE_LIMIT_DELAY` | `3.0` | Seconds between LinkedIn requests |
| `LIAI_DATABASE_PATH` | `database/liai.db` | SQLite database path |
| `LIAI_CACHE_DIR` | `cache` | Cache directory |
| `LIAI_EXPORT_DIR` | `reports` | Report output directory |
| `LIAI_LOG_DIR` | `logs` | Log file directory |

---

## 🧪 Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage report
pytest --cov=linkedin_ai --cov-report=html

# Run specific test file
pytest tests/test_database.py -v

# Run with output
pytest -s -v
```

---

## ⚖️ Ethical Usage & Disclaimer

> **Important:** This tool scrapes publicly visible LinkedIn profile information. Users are solely responsible for complying with LinkedIn's Terms of Service and applicable privacy laws.

- ✅ Reads **publicly visible** profile information only
- ✅ Requires **manual human login** (no credential storage)
- ✅ **Never sends** connection requests automatically
- ✅ Rate-limited to reduce server load
- ❌ Do **not** use for mass scraping, spam, or any automated messaging
- ❌ Do **not** store or share scraped data beyond personal networking use

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
