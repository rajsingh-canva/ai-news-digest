from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import httpx

from .config import Config

logger = logging.getLogger(__name__)


def write_obsidian_note(
    config: Config,
    article_text: str,
    ranked_articles: list[dict],
    notebook_id: str,
    public_url: str | None,
    audio_filename: str | None,
    date: datetime | None = None,
) -> Path:
    """Write the daily digest as an Obsidian note."""
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")
    day_str = date.strftime("%A, %B %-d, %Y")
    note_filename = f"AI Daily Digest - {date_str}.md"
    note_path = config.obsidian_notes_dir / note_filename

    # Build sources list
    sources = ""
    for a in ranked_articles:
        sources += f"- [{a['title']}]({a['url']}) — {a.get('one_line_summary', '')}\n"

    # Build frontmatter
    frontmatter = f"""---
date: {date_str}
tags: [AI-News, Daily-Digest]
notebook_id: {notebook_id}
public_link: {public_url or 'pending'}
---"""

    # Build podcast section
    podcast_section = ""
    if audio_filename:
        podcast_section = f"\n## Podcast\n![[{audio_filename}]]\n"
    if public_url:
        podcast_section += f"\n[Listen on NotebookLM]({public_url})\n"

    note_content = f"""{frontmatter}

# AI Daily Digest - {day_str}
{podcast_section}
{article_text}

## Sources
{sources}"""

    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note_content)
    logger.info("Obsidian note written to %s", note_path)
    return note_path


def send_email(
    config: Config,
    subject: str,
    html_body: str,
) -> bool:
    """Send the digest email via Resend API."""
    if not config.resend_api_key:
        logger.warning("No Resend API key configured, skipping email")
        return False

    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {config.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": config.email_from,
                "to": [config.email_to],
                "subject": subject,
                "html": html_body,
            },
            timeout=30,
        )
        response.raise_for_status()
        logger.info("Email sent successfully")
        return True
    except Exception:
        logger.exception("Failed to send email")
        return False


def send_discord(
    config: Config,
    title: str,
    top_headlines: list[str],
    article_url: str | None = None,
    podcast_url: str | None = None,
) -> bool:
    """Send a notification to Discord via webhook."""
    if not config.discord_webhook_url:
        logger.warning("No Discord webhook URL configured, skipping notification")
        return False

    # Build embed
    description = "\n".join(f"• {h}" for h in top_headlines[:5])

    fields = []
    if podcast_url:
        fields.append({"name": "Podcast", "value": f"[Listen]({podcast_url})", "inline": True})
    if article_url:
        fields.append({"name": "Full Article", "value": f"[Read]({article_url})", "inline": True})

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": 0x7C3AED,  # purple
                "fields": fields,
                "footer": {"text": "AI News Digest • Powered by Claude + NotebookLM"},
            }
        ]
    }

    try:
        response = httpx.post(
            config.discord_webhook_url,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        logger.info("Discord notification sent")
        return True
    except Exception:
        logger.exception("Failed to send Discord notification")
        return False


def markdown_to_html(markdown_text: str) -> str:
    """Simple markdown to HTML conversion for email."""
    import re

    html = markdown_text

    # Headers
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

    # Bullet points
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    # Paragraphs
    html = re.sub(r"\n\n", "</p><p>", html)
    html = f"<p>{html}</p>"

    # Wrap in basic email template
    return f"""
    <div style="max-width: 600px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
        {html}
        <hr style="border: none; border-top: 1px solid #eee; margin: 2em 0;">
        <p style="color: #999; font-size: 0.85em;">Generated by AI News Digest • Claude + NotebookLM</p>
    </div>
    """


def deliver_all(
    config: Config,
    article_text: str,
    ranked_articles: list[dict],
    notebook_id: str,
    public_url: str | None,
    audio_path: Path | None,
    date: datetime | None = None,
) -> dict[str, bool]:
    """Run all delivery channels."""
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")
    day_str = date.strftime("%A, %B %-d, %Y")
    audio_filename = audio_path.name if audio_path else None

    results: dict[str, bool] = {}

    # 1. Obsidian note
    try:
        write_obsidian_note(
            config, article_text, ranked_articles,
            notebook_id, public_url, audio_filename, date,
        )
        results["obsidian"] = True
    except Exception:
        logger.exception("Obsidian delivery failed")
        results["obsidian"] = False

    # 2. Email
    subject = f"AI Daily Digest - {day_str}"
    html_body = markdown_to_html(article_text)
    if public_url:
        html_body = f'<p><strong><a href="{public_url}">Listen to today\'s podcast</a></strong></p>' + html_body
    results["email"] = send_email(config, subject, html_body)

    # 3. Discord
    top_headlines = [a["title"] for a in ranked_articles[:5]]
    results["discord"] = send_discord(
        config,
        f"AI Daily Digest - {date_str}",
        top_headlines,
        podcast_url=public_url,
    )

    return results
