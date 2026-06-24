"""Content generation strategies for realistic-looking file modifications.

Each strategy returns a string to be appended to or used as the file content.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import List

# ---------------------------------------------------------------------------
# Activity-log style entries (timestamp + action phrase)
# ---------------------------------------------------------------------------

LOG_PHRASES: List[str] = [
    "system heartbeat check passed",
    "cache refresh completed",
    "background sync finished",
    "health check: all services nominal",
    "garbage collection cycle done",
    "index rebuild finished successfully",
    "daily backup verification: OK",
    "rate limiter counters reset",
    "job queue drained — 0 pending tasks",
    "configuration hot-reload applied",
    "SSL certificate validity confirmed",
    "API rate usage: 23% of limit",
    "dependency audit completed — no vulnerabilities",
    "database connection pool stats: 5/20 active",
    "scheduled maintenance window ended",
    "logging rotation triggered — 14 files archived",
    "feature flag evaluation cache warmed",
    "rate limit: 42 requests in last 60s",
    "scheduled task 'cleanup_tmp' completed",
    "webhook delivery retry queue empty",
    "session store TTL sweep done — 3 expired entries",
    "load average: 0.42 0.38 0.35",
    "disk usage: 67% (warning threshold: 80%)",
    "memcached hit ratio: 94.2%",
]

README_LINES: List[str] = [
    "> ⚡ Auto-synced at {timestamp}",
    "> 📅 Last updated: {timestamp}",
    "> 🕐 Activity heartbeat: {timestamp}",
    "> ✅ System operational as of {timestamp}",
]

EMOJI_POOL: List[str] = [
    "🔥", "💪", "🚀", "💡", "✨", "🎯", "🏆", "⭐",
    "🌟", "💎", "🎨", "⚡", "🔧", "📌", "✅", "📊",
    "🛡️", "🔍", "🌐", "📦",
]


# ---------------------------------------------------------------------------
# Footer helpers (shared across Markdown strategies)
# ---------------------------------------------------------------------------


def _extract_footer_prefixes() -> List[str]:
    """Return the static prefix of each README template (before ``{timestamp}``)."""
    return [tpl.split("{")[0].rstrip() for tpl in README_LINES]


FOOTER_PREFIXES: List[str] = _extract_footer_prefixes()


def _replace_or_append_footer(
    original_content: str,
    new_line: str,
) -> str:
    """Replace an existing footer line with *new_line*, or append it.

    Detection uses line-by-line prefix matching — only the beginning of each
    line is checked, so mentions inside code blocks or inline text are not
    falsely matched.
    """
    lines = original_content.splitlines()
    replaced = False
    updated: List[str] = []

    for line in lines:
        stripped = line.strip()
        matched = False
        for prefix in FOOTER_PREFIXES:
            if stripped.startswith(prefix):
                updated.append(new_line.strip())
                matched = True
                replaced = True
                break
        if not matched:
            updated.append(line)

    if replaced:
        return "\n".join(updated) + "\n"

    # No existing footer — append one, ensuring exactly one blank line
    # separator between the last content line and the new footer.
    result = original_content
    if result and not result.endswith("\n"):
        result += "\n"
    # If the content already ends with one or more blank lines, add just
    # one more newline before the footer.
    # Otherwise (no trailing blanks), add two newlines for separation.
    trailing_blanks = len(result) - len(result.rstrip("\n"))
    if trailing_blanks >= 2:
        sep = "\n"  # already has blank-line separation
    elif trailing_blanks == 1:
        sep = "\n"  # one more gives a blank line
    else:
        sep = "\n\n"
    return result + sep + new_line + "\n"


# ---------------------------------------------------------------------------
# Public generators
# ---------------------------------------------------------------------------


def generate_log_entry() -> str:
    """Generate a realistic log line with a timestamp and random phrase.

    Returns:
        A single log-line string ending with a newline, e.g.:
        ``[2026-06-24 14:32:07 UTC] system heartbeat check passed``
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    phrase = random.choice(LOG_PHRASES)
    return f"[{now}] {phrase}\n"


def generate_readme_footer(original_content: str) -> str:
    """Update or append a 'last updated' footer line in a README / Markdown file.

    Args:
        original_content: The current file content as a string.

    Returns:
        The updated content as a string (original content preserved).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    new_line = random.choice(README_LINES).format(timestamp=now)
    return _replace_or_append_footer(original_content, new_line)


def generate_emoji_line() -> str:
    """Generate a single line with random emoji and a short note.

    Used as a fallback strategy for non-standard file types.

    Returns:
        A string like ``"🎯 focus checkpoint\\n"``
    """
    emoji = random.choice(EMOJI_POOL)
    phrase = random.choice(LOG_PHRASES)
    return f"{emoji} {phrase}\n"


# ---------------------------------------------------------------------------
# Strategy dispatcher
# ---------------------------------------------------------------------------


def generate_content(filename: str, existing_content: str = "") -> str:
    """Pick an appropriate content-generation strategy based on the file name.

    Strategies by file type:

    ====================== ===================================================
    Pattern                 Strategy
    ====================== ===================================================
    ``README.md``           Full-content footer replacement.
    ``*.md``                Full-content footer replacement.
    ``*.log`` / log files   Append a timestamped log line.
    ``*.txt``               Append a timestamped log line.
    anything else           Append a random-emoji + phrase line.
    ====================== ===================================================

    Args:
        filename: The target file name (stem + extension).
        existing_content: The current file content as a string.

    Returns:
        New content — for Markdown files this is the **full updated file**;
        for all other types it is the **text to append**.
    """
    name_lower = filename.lower()

    if name_lower == "readme.md" or name_lower.endswith(".md"):
        return generate_readme_footer(existing_content)

    if name_lower.endswith(".log") or name_lower == "activity.log" or name_lower.endswith(".txt"):
        return generate_log_entry()

    # Fallback: emoji + phrase (keeps any file type looking alive)
    return generate_emoji_line()
