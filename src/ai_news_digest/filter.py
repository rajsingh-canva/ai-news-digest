from __future__ import annotations

import json
import logging

import anthropic

from .config import Config
from .feeds import Article

logger = logging.getLogger(__name__)

FILTER_SYSTEM_PROMPT = """\
You are an AI news curator. You will receive a list of recent AI-related articles.
Your job is to select and rank the top articles by significance, novelty, and breadth of impact.

Selection criteria:
- Prioritize breaking news, major product launches, significant research breakthroughs
- Include a mix of categories: industry news, research papers, tool releases, policy/regulation
- Prefer primary sources over commentary
- Deprioritize listicles, opinion pieces, and rehashed stories
- Include at most 2 research papers unless there's a major breakthrough

Return a JSON array of the top articles, ranked by importance. Each entry:
{
  "title": "original title",
  "url": "original url",
  "rank": 1,
  "category": "industry|research|tools|policy|labs|community",
  "one_line_summary": "one sentence explaining why this matters"
}

Return ONLY valid JSON. No markdown, no explanation."""

FILTER_USER_TEMPLATE = """\
Here are {count} recent AI articles from the last 28 hours. Select the top {max_articles} most important ones.

Articles:
{articles_text}"""


def filter_articles(articles: list[Article], config: Config) -> list[dict]:
    """Use Claude Haiku to filter and rank articles."""
    if not articles:
        logger.warning("No articles to filter")
        return []

    # Format articles for the prompt
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"\n{i}. [{a.source}] {a.title}\n   URL: {a.url}\n   Summary: {a.summary[:200]}\n"

    user_msg = FILTER_USER_TEMPLATE.format(
        count=len(articles),
        max_articles=config.max_articles,
        articles_text=articles_text,
    )

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    logger.info("Filtering %d articles with %s", len(articles), config.filter_model)

    response = client.messages.create(
        model=config.filter_model,
        max_tokens=4096,
        system=FILTER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()

    # Parse JSON response
    try:
        # Handle potential markdown wrapping
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        ranked = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse filter response as JSON: %s", raw[:200])
        # Fallback: return first N articles unranked
        return [
            {
                "title": a.title,
                "url": a.url,
                "rank": i,
                "category": a.category,
                "one_line_summary": a.summary[:100],
            }
            for i, a in enumerate(articles[: config.max_articles], 1)
        ]

    # Sort by rank
    ranked.sort(key=lambda x: x.get("rank", 99))

    logger.info("Selected %d top articles", len(ranked))
    return ranked[: config.max_articles]
