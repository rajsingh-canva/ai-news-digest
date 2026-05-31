from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FEEDS_TOML = PROJECT_ROOT / "feeds.toml"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"


@dataclass
class Config:
    # API keys
    anthropic_api_key: str = field(default_factory=lambda: os.environ["ANTHROPIC_API_KEY"])
    resend_api_key: str = field(default_factory=lambda: os.environ.get("RESEND_API_KEY", ""))
    discord_webhook_url: str = field(default_factory=lambda: os.environ.get("DISCORD_WEBHOOK_URL", ""))

    # Paths
    obsidian_vault: Path = field(
        default_factory=lambda: Path(os.environ.get("OBSIDIAN_VAULT_PATH", "~/TheBible")).expanduser()
    )
    notebooklm_cli: str = os.environ.get("NOTEBOOKLM_CLI", "/opt/homebrew/bin/notebooklm")

    # Model config
    filter_model: str = "claude-haiku-4-5-20251001"
    article_model: str = "claude-sonnet-4-6"

    # Feed settings
    lookback_hours: int = 28  # overlap buffer for timezone edge cases
    max_articles: int = 12
    min_articles: int = 8

    # NotebookLM settings
    audio_format: str = "brief"
    audio_length: str = "short"

    # Email
    email_from: str = "AI News Digest <digest@rsnetworks.com.au>"
    email_to: str = os.environ.get("EMAIL_TO", "raj.singh@rsnetworks.com.au")

    @property
    def obsidian_notes_dir(self) -> Path:
        return self.obsidian_vault / "6 - Main Notes"

    @property
    def obsidian_attachments_dir(self) -> Path:
        return self.obsidian_vault / "attachments"

    @property
    def obsidian_tags_dir(self) -> Path:
        return self.obsidian_vault / "3 - Tags"

    @property
    def seen_urls_path(self) -> Path:
        return DATA_DIR / "seen_urls.json"
