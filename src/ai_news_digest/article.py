from __future__ import annotations

import logging
from datetime import datetime

import anthropic

from .config import Config

logger = logging.getLogger(__name__)

ARTICLE_SYSTEM_PROMPT = """\
You are an expert AI journalist writing a daily digest for a technical audience.
Write a concise, engaging daily briefing that someone can read in 3-5 minutes.

Structure:
1. **Lead** — One paragraph summarizing the day's biggest story
2. **Top Stories** — Each story gets a heading (## ), 2-3 sentences explaining what happened and why it matters, and a source link
3. **Quick Hits** — Bullet list of remaining stories (1 sentence each with links)
4. **What to Watch** — 1-2 sentences on emerging trends or things to follow

Style:
- Professional but conversational, like a knowledgeable colleague briefing you
- Focus on "why it matters" not just "what happened"
- Use plain language, avoid hype words like "revolutionary" or "groundbreaking"
- Link to sources inline using markdown: [Source Name](url)
- No emojis in headings, minimal elsewhere"""

ARTICLE_USER_TEMPLATE = """\
Write today's AI Daily Digest for {date}.

Here are the top stories, ranked by importance:

{stories}

Write the digest now."""


def generate_article(
    ranked_articles: list[dict],
    config: Config,
    date: datetime | None = None,
) -> str:
    """Generate a polished article digest using Claude Sonnet."""
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%A, %B %-d, %Y")

    # Format stories for the prompt
    stories = ""
    for article in ranked_articles:
        stories += (
            f"\n**Rank {article['rank']}** [{article.get('category', 'general')}]\n"
            f"Title: {article['title']}\n"
            f"URL: {article['url']}\n"
            f"Summary: {article.get('one_line_summary', '')}\n"
        )

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    logger.info("Generating article with %s", config.article_model)

    response = client.messages.create(
        model=config.article_model,
        max_tokens=4096,
        system=ARTICLE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": ARTICLE_USER_TEMPLATE.format(
                    date=date_str,
                    stories=stories,
                ),
            }
        ],
    )

    article_text = response.content[0].text.strip()
    logger.info("Article generated: %d characters", len(article_text))
    return article_text
