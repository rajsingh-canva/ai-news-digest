# AI News Digest

An automated daily pipeline that aggregates AI news from RSS feeds, filters and ranks the top stories with Claude, generates a readable article digest **and** a short podcast via NotebookLM, then delivers everything to your inbox, Obsidian vault, and Discord — every weekday morning.

Staying on top of AI is hard when the field moves this fast. This tool does the reading for you and hands back a 5–10 minute brief you can read or listen to over coffee.

## What it does

```
launchd (weekdays 6:50am AEST)
        │
        ▼
┌──────────────────────────────────────────────┐
│  Phase 0  Health check    NotebookLM auth OK?  │
│  Phase 1  Fetch           ~18 RSS feeds        │
│  Phase 2  Filter          Claude Haiku ranks   │
│  Phase 3  Notebook        NotebookLM report    │
│                           + short podcast      │
│  Phase 4  Article         Claude Sonnet writes │
│  Phase 5  Deliver         Email · Obsidian ·   │
│                           Discord              │
└──────────────────────────────────────────────┘
```

1. **Fetch** — pulls recent items (last 28h) from RSS feeds across major labs, industry press, research (arXiv), community (Reddit), and YouTube. Deduplicates by URL and title similarity.
2. **Filter** — Claude Haiku ranks the candidates and returns the top 8–12 with one-line summaries and categories.
3. **Notebook** — creates a NotebookLM notebook from the top article URLs, generates a report and a short audio "podcast", and downloads the MP3.
4. **Article** — Claude Sonnet writes an email-friendly digest (Lead → Top Stories → Quick Hits → What to Watch).
5. **Deliver** — writes an Obsidian note with the embedded podcast, emails the digest via Resend, and posts a Discord notification with headlines and links.

## Requirements

- **Python 3.12+** and [`uv`](https://github.com/astral-sh/uv)
- **[NotebookLM CLI](https://github.com/)** installed locally (default path `/opt/homebrew/bin/notebooklm`) and authenticated — there is no public NotebookLM API, so this must run on a machine where you're signed in.
- **Anthropic API key** (required)
- **Resend API key** (optional — email delivery) and a **Discord webhook URL** (optional — notifications)
- macOS for the bundled `launchd` schedule (the pipeline itself is cross-platform; only the scheduler is macOS-specific)

## Setup

```bash
git clone https://github.com/rajsingh-canva/ai-news-digest.git
cd ai-news-digest

# install dependencies
uv sync

# configure secrets
cp .env.example .env
$EDITOR .env   # fill in ANTHROPIC_API_KEY, and optionally RESEND/Discord
```

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Claude filtering + article generation |
| `RESEND_API_KEY` | optional | Email delivery (skipped if unset) |
| `DISCORD_WEBHOOK_URL` | optional | Discord notifications (skipped if unset) |
| `EMAIL_TO` | optional | Recipient address |
| `OBSIDIAN_VAULT_PATH` | optional | Defaults to `~/TheBible` |
| `NOTEBOOKLM_CLI` | optional | Defaults to `/opt/homebrew/bin/notebooklm` |

## Usage

Run the full pipeline manually:

```bash
uv run python -m ai_news_digest.main
# or, via the installed script entry point:
uv run ai-news-digest
```

Logs are written to `logs/YYYY-MM-DD.log`.

## Configuration

- **Feeds** — edit `feeds.toml`. Each entry has a `url`, `category`, and display `name`. Add or remove sources freely; broken feeds are logged and skipped.
- **Models, lookback window, article count, audio format** — tunable in `src/ai_news_digest/config.py`. Defaults: Haiku for filtering, Sonnet for the article, 28h lookback, 8–12 articles, `brief`/`short` audio.

## Scheduling (macOS)

The repo ships a `launchd` job that runs weekdays at **6:50am** (10-minute buffer before a 7am target, AEST).

```bash
# copy and load
cp com.rajsingh.ai-news-digest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.rajsingh.ai-news-digest.plist

# trigger a one-off run to test
launchctl start com.rajsingh.ai-news-digest

# unload
launchctl unload ~/Library/LaunchAgents/com.rajsingh.ai-news-digest.plist
```

If the Mac is asleep at the scheduled time, `launchd` runs the job on next wake. Optionally use `pmset` to schedule a wake a few minutes earlier.

## Project structure

```
ai-news-digest/
├── feeds.toml                       # RSS sources (editable)
├── pyproject.toml                   # uv project, deps, script entry
├── com.rajsingh.ai-news-digest.plist# launchd schedule (weekdays 6:50am)
├── .env.example                     # secrets template
└── src/ai_news_digest/
    ├── main.py        # orchestrator (Phases 0–5)
    ├── config.py      # paths, API keys, model + feed settings
    ├── feeds.py       # RSS fetch, dedup, seen-URL tracking
    ├── filter.py      # Claude Haiku ranking
    ├── article.py     # Claude Sonnet digest
    ├── notebook.py    # NotebookLM CLI wrapper (report + audio)
    └── delivery.py    # Obsidian note, Resend email, Discord webhook
```

## Cost

Roughly **~$2/month** in API spend on the default (Haiku filter + Sonnet article); NotebookLM, Resend's free tier, and Discord webhooks are free. See the implementation plan for Quality-First (~$7/mo) and Minimize-Cost (~$0.50/mo with a local LLM) tiers.

## Security

- Secrets live in `.env`, which is gitignored — only `.env.example` is committed. Never commit real keys.
- NotebookLM must be authenticated locally; the pipeline health-checks auth at startup and alerts via Discord if it has expired.

## License

Personal project — no license specified.
