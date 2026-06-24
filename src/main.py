"""Entry-point for the git-auto-commit system.

Supports two run modes:

``--once``
    Generate one commit and exit.  Ideal for cron / GitHub Actions / scheduled
    task triggers.

``--daemon`` *(default when no mode flag is passed)*
    Run continuously: at the start of each day the target commit count is
    randomised, commits are distributed across the active-hours window, and
    the process then sleeps until the next day.
"""

from __future__ import annotations

import argparse
import logging
import random
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from src.config import AppConfig, get_token, load_config
from src.content_gen import generate_content
from src.git_ops import clone_or_pull, commit_and_push, configure_git_user

# ---------------------------------------------------------------------------
# Module-level state (used for graceful shutdown)
# ---------------------------------------------------------------------------
_keep_running = True

logger = logging.getLogger("git-auto-commit")

# Maximum number of consecutive failed commit attempts before giving up
# for the day.  Protects against infinite loops when all files are missing
# or the remote is unreachable.
MAX_CONSECUTIVE_FAILURES = 5


def _setup_logging(level: str) -> None:
    """Configure the root logger so ALL modules' logs are visible."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()  # root logger — catches output from all sub-modules
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Remove any pre-existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)


def _setup_signal_handlers() -> None:
    """Register signal handlers for graceful shutdown (cross-platform).

    SIGTERM does not exist on Windows, so we guard against AttributeError.
    """
    for sig_name in ("SIGINT", "SIGTERM"):
        sig_num = getattr(signal, sig_name, None)
        if sig_num is not None:
            try:
                signal.signal(sig_num, _signal_handler)
            except (ValueError, OSError):
                # Signal may not be registerable in some environments
                # (e.g. inside a thread or sub-interpreter).
                logger.debug("Could not register handler for %s", sig_name)


def _signal_handler(signum: int, _frame: object) -> None:
    """Handle SIGINT / SIGTERM for clean shutdown."""
    global _keep_running
    name = signal.Signals(signum).name
    logger.info("Received %s — shutting down gracefully …", name)
    _keep_running = False


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _is_in_active_window(cfg: AppConfig) -> bool:
    """Return ``True`` if the current hour is within the configured window."""
    now = datetime.now()
    if cfg.skip_weekends and now.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    start, end = cfg.active_hours
    return start <= now.hour < end


def _seconds_until_next_window(cfg: AppConfig) -> float:
    """Return the number of seconds until the next active-hours window opens.

    Returns 0 if already inside the active window (defensive fallback).
    """
    now = datetime.now()
    start, _ = cfg.active_hours

    # Defensive: if already in the window, caller should not have invoked us.
    if _is_in_active_window(cfg):
        return 0.0

    # Build the next open time
    candidate = now.replace(hour=start, minute=0, second=0, microsecond=0)
    if now.hour >= start:
        candidate += timedelta(days=1)

    # If weekends are skipped, fast-forward past Saturday & Sunday
    while cfg.skip_weekends and candidate.weekday() >= 5:
        candidate += timedelta(days=1)

    delta = (candidate - now).total_seconds()
    return max(0.0, delta)


def _safe_sleep(seconds: float, *, check_active: bool = False, cfg: AppConfig | None = None) -> None:
    """Sleep for *seconds*, but remain responsive to shutdown signals.

    Sleeps in 10‑second chunks.  If ``check_active`` is True, also exits
    early when the active-hours window closes.

    Guards against negative sleep values (clock jumps, DST transitions).
    """
    remaining = max(0.0, seconds)
    while remaining > 0 and _keep_running:
        if check_active and cfg is not None:
            if not _is_in_active_window(cfg):
                break
        time.sleep(min(10.0, remaining))
        remaining -= 10.0


def _random_interval(cfg: AppConfig) -> float:
    """Return a randomised interval in seconds between two commits."""
    minutes = random.randint(
        cfg.commit.min_interval_minutes, cfg.commit.max_interval_minutes
    )
    # Add up to ±15 % jitter, clamped to a minimum of 10 s
    jitter = 1.0 + random.uniform(-0.15, 0.15)
    return max(10.0, minutes * 60.0 * jitter)


def _pick_random_file(cfg: AppConfig) -> str:
    """Pick one file from the configured file list at random."""
    return random.choice(cfg.commit.files)


def _pick_random_message(cfg: AppConfig) -> str:
    """Pick a random commit message from the configured list."""
    return random.choice(cfg.commit.messages)


# ---------------------------------------------------------------------------
# Single-commit cycle
# ---------------------------------------------------------------------------


def _execute_one_commit(cfg: AppConfig, repo_dir: Path) -> bool:
    """Run one full commit cycle: modify a file → stage → commit → push.

    Returns ``True`` if a commit was created and pushed successfully.
    """
    filename = _pick_random_file(cfg)
    file_path = repo_dir / filename

    # Read existing content (if the file exists)
    existing = ""
    if file_path.exists():
        try:
            existing = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError) as exc:
            logger.error("❌ Cannot read %s: %s", file_path, exc)
            return False

    # Generate new content
    new_content = generate_content(filename, existing)

    # Apply the change
    name_lower = filename.lower()
    try:
        if name_lower == "readme.md" or name_lower.endswith(".md"):
            # The README generator returns full updated content
            file_path.write_text(new_content, encoding="utf-8")
        else:
            # Append mode for .log and other files
            with open(file_path, "a", encoding="utf-8") as fh:
                fh.write(new_content)
    except (OSError, PermissionError) as exc:
        logger.error("❌ Cannot write %s: %s", file_path, exc)
        return False

    logger.info("✏️  Modified: %s", filename)

    # Git operations
    message = _pick_random_message(cfg)
    success = commit_and_push(repo_dir, message, [filename], branch=cfg.git.branch)

    if success:
        logger.info("✅ Commit cycle complete — %s", message[:60])
    return success


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def run_once(cfg: AppConfig, token: str) -> None:
    """Generate a single commit and exit (one-shot mode)."""
    repo_dir = clone_or_pull(cfg, token)
    configure_git_user(repo_dir)
    _execute_one_commit(cfg, repo_dir)


def run_daemon(cfg: AppConfig, token: str) -> None:
    """Run continuously, scheduling commits according to the configuration."""
    global _keep_running

    _setup_signal_handlers()

    repo_dir = clone_or_pull(cfg, token)
    configure_git_user(repo_dir)

    logger.info("🚀 Daemon started — press Ctrl+C to stop")

    while _keep_running:
        # ── Wait until we are in the active window ────────────────────────
        if not _is_in_active_window(cfg):
            wait = _seconds_until_next_window(cfg)
            logger.info(
                "⏳ Outside active window — sleeping for %s",
                str(timedelta(seconds=int(wait))),
            )
            _safe_sleep(wait)
            continue

        # ── Refresh repo at the start of each daily cycle ─────────────────
        # This ensures the local clone hasn't diverged after days of uptime.
        logger.info("🔄 Refreshing repository for today's cycle …")
        try:
            repo_dir = clone_or_pull(cfg, token)
        except RuntimeError as exc:
            logger.error("❌ Failed to refresh repository: %s", exc)
            # Sleep a bit then retry from the top
            _safe_sleep(300)
            continue

        # ── Determine today's commit target ───────────────────────────────
        target = random.randint(cfg.commit.min_daily, cfg.commit.max_daily)
        logger.info("📋 Today's commit target: %d", target)

        if target == 0:
            logger.info("😴 Zero commits scheduled today — sleeping until next window")
            wait = _seconds_until_next_window(cfg)
            _safe_sleep(wait)
            continue

        # ── Execute today's commits ───────────────────────────────────────
        commits_done = 0
        consecutive_failures = 0
        while commits_done < target and _keep_running:
            # Check we're still in the active window
            if not _is_in_active_window(cfg):
                logger.info(
                    "⏰ Active window ended (%d/%d commits done)",
                    commits_done,
                    target,
                )
                break

            if _execute_one_commit(cfg, repo_dir):
                commits_done += 1
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(
                        "❌ %d consecutive commit failures — aborting today's "
                        "cycle.  Check that the target files exist and the "
                        "remote is reachable.",
                        consecutive_failures,
                    )
                    break
                # Still wait a bit before retrying after a failure
                _safe_sleep(60.0)

            if commits_done >= target:
                break

            # Wait a random interval before the next commit
            interval = _random_interval(cfg)
            logger.debug("Next commit in %s", str(timedelta(seconds=int(interval))))
            _safe_sleep(interval, check_active=True, cfg=cfg)

        logger.info("🏁 Daily run complete — %d commits made", commits_done)

        # Sleep until the next day's window
        if _keep_running:
            wait = _seconds_until_next_window(cfg)
            logger.info(
                "💤 Sleeping %s until next active window",
                str(timedelta(seconds=int(wait))),
            )
            _safe_sleep(wait)

    logger.info("👋 Daemon stopped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate run mode."""
    parser = argparse.ArgumentParser(
        description="Git Auto Commit — 7×24 online auto-commit system",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single commit cycle and exit (for cron / GitHub Actions).",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously as a long-lived process.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file (default: config.yaml).",
    )
    args = parser.parse_args()

    # Default to daemon mode when no mode flag is given
    if not args.once and not args.daemon:
        args.daemon = True

    cfg: AppConfig = load_config(args.config)
    _setup_logging(cfg.log_level)
    token = get_token(cfg)

    if args.once:
        logger.info("🎯 One-shot mode")
        run_once(cfg, token)
    else:
        run_daemon(cfg, token)


if __name__ == "__main__":
    main()
