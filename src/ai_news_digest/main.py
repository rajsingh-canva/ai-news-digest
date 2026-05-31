from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import LOGS_DIR, Config

logger = logging.getLogger("ai_news_digest")


def setup_logging() -> None:
    """Configure logging to file and stderr."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{date_str}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )


def run() -> None:
    """Execute the full daily digest pipeline."""
    setup_logging()
    logger.info("=== AI News Digest starting ===")

    config = Config()
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    # Phase 1: Health check
    logger.info("Phase 0: NotebookLM health check")
    from .notebook import health_check

    if not health_check(config):
        logger.error("NotebookLM health check failed — sending alert and aborting")
        try:
            from .delivery import send_discord
            send_discord(
                config,
                "AI News Digest — FAILED",
                ["NotebookLM authentication expired. Re-authenticate and retry."],
            )
        except Exception:
            pass
        sys.exit(1)

    # Phase 1: Fetch RSS feeds
    logger.info("Phase 1: Fetching RSS feeds")
    from .feeds import fetch_all

    articles = fetch_all(config)
    if not articles:
        logger.warning("No articles found, aborting")
        sys.exit(0)

    logger.info("Fetched %d unique articles", len(articles))

    # Phase 2: Filter and rank with Claude Haiku
    logger.info("Phase 2: Filtering articles with AI")
    from .filter import filter_articles

    ranked = filter_articles(articles, config)
    if not ranked:
        logger.warning("No articles passed filtering, aborting")
        sys.exit(0)

    logger.info("Selected %d top articles", len(ranked))

    # Phase 3: NotebookLM — create notebook, add sources, generate report + audio
    logger.info("Phase 3: NotebookLM pipeline")
    from .notebook import run_notebook_pipeline

    audio_path = config.obsidian_attachments_dir / f"ai-news-{date_str}.mp3"
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    article_urls = [a["url"] for a in ranked]
    nb_result = run_notebook_pipeline(
        config,
        title=f"AI News {date_str}",
        article_urls=article_urls,
        audio_output_path=audio_path,
    )

    logger.info("NotebookLM pipeline complete (notebook: %s)", nb_result.notebook_id)

    # Phase 4: Generate article with Claude Sonnet
    logger.info("Phase 4: Generating article")
    from .article import generate_article

    article_text = generate_article(ranked, config, today)

    # Phase 5: Deliver to all channels
    logger.info("Phase 5: Delivering digest")
    from .delivery import deliver_all

    results = deliver_all(
        config,
        article_text=article_text,
        ranked_articles=ranked,
        notebook_id=nb_result.notebook_id,
        public_url=nb_result.public_url,
        audio_path=nb_result.audio_path,
        date=today,
    )

    # Summary
    for channel, success in results.items():
        status = "OK" if success else "FAILED"
        logger.info("Delivery [%s]: %s", channel, status)

    logger.info("=== AI News Digest complete ===")


def main() -> None:
    """Entry point for the CLI."""
    try:
        run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception:
        logger.exception("Unhandled error in AI News Digest")
        sys.exit(1)


if __name__ == "__main__":
    main()
