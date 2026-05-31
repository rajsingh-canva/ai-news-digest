from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class NotebookResult:
    notebook_id: str
    report_text: str
    audio_path: Path | None
    public_url: str | None


def _run_cli(config: Config, *args: str, timeout: int = 300) -> dict | str:
    """Run a notebooklm CLI command and return parsed JSON or raw output."""
    cmd = [config.notebooklm_cli, *args]
    logger.debug("Running: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        logger.error("CLI error (exit %d): %s", result.returncode, result.stderr)
        raise RuntimeError(f"notebooklm CLI failed: {result.stderr}")

    output = result.stdout.strip()
    if "--json" in args:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            logger.warning("Could not parse JSON output: %s", output[:200])
            return output
    return output


def health_check(config: Config) -> bool:
    """Check if NotebookLM CLI is authenticated and working."""
    try:
        _run_cli(config, "list", "--json", timeout=30)
        logger.info("NotebookLM health check passed")
        return True
    except Exception:
        logger.exception("NotebookLM health check failed")
        return False


def create_notebook(config: Config, title: str) -> str:
    """Create a new notebook and return its ID."""
    result = _run_cli(config, "create", title, "--json")
    if isinstance(result, dict):
        notebook_id = result.get("id") or result.get("notebook_id", "")
    else:
        notebook_id = result
    logger.info("Created notebook: %s (ID: %s)", title, notebook_id)
    return notebook_id


def add_source(config: Config, notebook_id: str, url: str) -> str | None:
    """Add a URL source to a notebook."""
    try:
        result = _run_cli(
            config, "source", "add", url,
            "--notebook", notebook_id,
            "--json",
            timeout=120,
        )
        source_id = None
        if isinstance(result, dict):
            source_id = result.get("id") or result.get("source_id")
        logger.info("Added source: %s", url)
        return source_id
    except Exception:
        logger.warning("Failed to add source: %s", url)
        return None


def wait_for_sources(config: Config, notebook_id: str) -> None:
    """Wait for all sources in a notebook to finish processing."""
    try:
        _run_cli(
            config, "source", "wait",
            "--notebook", notebook_id,
            "--json",
            timeout=180,
        )
        logger.info("All sources processed for notebook %s", notebook_id)
    except Exception:
        logger.warning("Timeout waiting for sources, proceeding anyway")


def generate_report(config: Config, notebook_id: str, description: str = "") -> str:
    """Generate a report and return the text content."""
    args = [
        "generate", "report",
        "--notebook", notebook_id,
        "--wait",
        "--json",
    ]
    if description:
        args.append(description)

    result = _run_cli(config, *args, timeout=300)
    if isinstance(result, dict):
        return result.get("content", result.get("text", str(result)))
    return str(result)


def generate_audio(config: Config, notebook_id: str, output_path: Path) -> Path | None:
    """Generate podcast audio and download it."""
    # Generate
    args = [
        "generate", "audio",
        "--notebook", notebook_id,
        "--format", config.audio_format,
        "--length", config.audio_length,
        "--wait",
        "--json",
    ]

    try:
        result = _run_cli(config, *args, timeout=600)
        logger.info("Audio generation complete")
    except Exception:
        logger.exception("Audio generation failed")
        return None

    # Download the audio
    try:
        download_args = [
            "download", "audio",
            "--notebook", notebook_id,
            "--output", str(output_path),
            "--json",
        ]
        _run_cli(config, *download_args, timeout=120)
        if output_path.exists():
            logger.info("Audio downloaded to %s", output_path)
            return output_path
        logger.warning("Audio file not found at %s after download", output_path)
        return None
    except Exception:
        logger.exception("Audio download failed")
        return None


def enable_sharing(config: Config, notebook_id: str) -> str | None:
    """Enable public sharing and return the share URL."""
    try:
        result = _run_cli(
            config, "share", "public", "--enable",
            "--notebook", notebook_id,
            "--json",
            timeout=30,
        )
        if isinstance(result, dict):
            url = result.get("url") or result.get("share_url")
            logger.info("Public share enabled: %s", url)
            return url
        return None
    except Exception:
        logger.warning("Could not enable sharing for notebook %s", notebook_id)
        return None


def run_notebook_pipeline(
    config: Config,
    title: str,
    article_urls: list[str],
    audio_output_path: Path,
) -> NotebookResult:
    """Full NotebookLM pipeline: create notebook, add sources, generate report + audio."""
    # Create notebook
    notebook_id = create_notebook(config, title)

    # Add sources (top articles)
    for url in article_urls:
        add_source(config, notebook_id, url)

    # Wait for processing
    wait_for_sources(config, notebook_id)

    # Generate report
    report_text = generate_report(
        config, notebook_id,
        "Create a concise daily AI news briefing. Focus on the most impactful developments. "
        "Write for a technical audience who wants to stay informed.",
    )

    # Generate audio
    audio_path = generate_audio(config, notebook_id, audio_output_path)

    # Enable sharing
    public_url = enable_sharing(config, notebook_id)

    return NotebookResult(
        notebook_id=notebook_id,
        report_text=report_text,
        audio_path=audio_path,
        public_url=public_url,
    )
