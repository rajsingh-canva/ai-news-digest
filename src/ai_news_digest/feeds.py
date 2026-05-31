from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import feedparser

from .config import FEEDS_TOML, Config

logger = logging.getLogger(__name__)

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class Article:
    title: str
    url: str
    summary: str
    published: datetime
    source: str
    category: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "published": self.published.isoformat(),
            "source": self.source,
            "category": self.category,
        }


def load_feeds(feeds_path: Path = FEEDS_TOML) -> list[dict]:
    """Load feed definitions from feeds.toml."""
    with open(feeds_path, "rb") as f:
        data = tomllib.load(f)
    feeds = []
    for _key, feed in data.get("feeds", {}).items():
        if isinstance(feed, dict) and "url" in feed:
            feeds.append(feed)
    return feeds


def parse_date(entry: dict) -> datetime:
    """Extract published date from a feed entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            return datetime(*parsed[:6], tzinfo=UTC)
    return datetime.now(UTC)


def fetch_feed(feed: dict, cutoff: datetime) -> list[Article]:
    """Fetch and parse a single RSS feed, filtering to recent articles."""
    url = feed["url"]
    name = feed.get("name", url)
    category = feed.get("category", "other")

    try:
        result = feedparser.parse(url)
        if result.bozo and not result.entries:
            logger.warning("Feed %s returned error: %s", name, result.bozo_exception)
            return []

        articles = []
        for entry in result.entries:
            pub_date = parse_date(entry)
            if pub_date < cutoff:
                continue

            link = entry.get("link", "")
            if not link:
                continue

            title = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            # Truncate long summaries
            if len(summary) > 500:
                summary = summary[:497] + "..."

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                published=pub_date,
                source=name,
                category=category,
            ))

        logger.info("Fetched %d articles from %s", len(articles), name)
        return articles

    except Exception:
        logger.exception("Failed to fetch feed %s", name)
        return []


def _jaccard_similarity(a: str, b: str) -> float:
    """Simple word-level Jaccard similarity for deduplication."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def deduplicate(articles: list[Article], seen_urls_path: Path | None = None) -> list[Article]:
    """Remove duplicate articles by URL and fuzzy title matching."""
    # Load previously seen URLs
    seen_urls: set[str] = set()
    if seen_urls_path and seen_urls_path.exists():
        try:
            data = json.loads(seen_urls_path.read_text())
            # Only keep URLs from last 7 days
            cutoff = time.time() - 7 * 86400
            seen_urls = {url for url, ts in data.items() if ts > cutoff}
        except Exception:
            logger.warning("Could not load seen URLs, starting fresh")

    unique: list[Article] = []
    seen_titles: list[str] = []

    for article in articles:
        # Skip if URL already seen
        if article.url in seen_urls:
            continue

        # Skip if title is too similar to an already-selected article
        is_dup = False
        for seen_title in seen_titles:
            if _jaccard_similarity(article.title, seen_title) > 0.7:
                is_dup = True
                break

        if not is_dup:
            unique.append(article)
            seen_titles.append(article.title)
            seen_urls.add(article.url)

    # Save updated seen URLs
    if seen_urls_path:
        seen_urls_path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        # Merge with existing data
        existing: dict[str, float] = {}
        if seen_urls_path.exists():
            try:
                existing = json.loads(seen_urls_path.read_text())
            except Exception:
                pass
        for article in unique:
            existing[article.url] = now
        # Prune old entries
        cutoff = now - 7 * 86400
        existing = {url: ts for url, ts in existing.items() if ts > cutoff}
        seen_urls_path.write_text(json.dumps(existing, indent=2))

    logger.info("Deduplicated: %d -> %d articles", len(articles), len(unique))
    return unique


def fetch_all(config: Config) -> list[Article]:
    """Fetch all feeds and return deduplicated, sorted articles."""
    feeds = load_feeds()
    cutoff = datetime.now(UTC) - timedelta(hours=config.lookback_hours)

    all_articles: list[Article] = []
    for feed in feeds:
        articles = fetch_feed(feed, cutoff)
        all_articles.extend(articles)

    # Sort by published date, newest first
    all_articles.sort(key=lambda a: a.published, reverse=True)

    # Deduplicate
    unique = deduplicate(all_articles, config.seen_urls_path)

    logger.info("Total unique articles: %d from %d feeds", len(unique), len(feeds))
    return unique
