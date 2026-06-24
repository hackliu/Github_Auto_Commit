"""Git operations — clone, pull, commit, push — with retry logic."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("git-auto-commit")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 5  # seconds — actual delay = base * (2 ** (attempt-1))

# Known git lock files that can prevent operations after a crash
_LOCK_FILES = ["index.lock", "HEAD.lock", "config.lock"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(
    args: list[str],
    cwd: Optional[Path] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run a git command and return the completed process.

    Args:
        args: Command-line tokens (e.g. ``["git", "status"]``).
        cwd: Working directory for the subprocess.
        timeout: Hard timeout in seconds.

    Returns:
        The ``CompletedProcess`` on success.

    Raises:
        subprocess.CalledProcessError: On non-zero exit.
    """
    logger.debug("Running: %s  (cwd=%s)", " ".join(args), cwd)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )


def _clean_stale_locks(repo_dir: Path) -> None:
    """Remove stale git lock files left by a previous crashed operation.

    These ``.git/*.lock`` files prevent further git commands from running.
    We check that each lock file is truly stale by looking at the PID in the
    file (when applicable).  For ``index.lock``, if the file is older than
    5 minutes, it's almost certainly stale.
    """
    git_dir = repo_dir / ".git"
    if not git_dir.is_dir():
        return

    for lock_name in _LOCK_FILES:
        lock_path = git_dir / lock_name
        if not lock_path.is_file():
            continue
        try:
            mtime = lock_path.stat().st_mtime
            age = time.time() - mtime
            if age > 300:  # 5 minutes
                logger.warning(
                    "🧹 Removing stale lock file (%.0fs old): %s",
                    age,
                    lock_path,
                )
                lock_path.unlink()
            else:
                logger.debug(
                    "Lock file %s is recent (%.0fs) — leaving in place",
                    lock_path,
                    age,
                )
        except OSError as exc:
            logger.debug("Could not inspect/remove lock %s: %s", lock_path, exc)


def _retry_git_op(
    operation_name: str,
    args: list[str],
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """Execute a git command with retry / exponential-backoff on failure.

    Before the first attempt, stale lock files in ``.git/`` are cleaned up
    so that a previous crash does not block future operations.

    Args:
        operation_name: Human-readable label for logging.
        args: Command-line tokens.
        cwd: Working directory.

    Returns:
        The ``CompletedProcess`` result.

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    if cwd is not None:
        _clean_stale_locks(cwd)

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = _run(args, cwd=cwd)
            if attempt > 1:
                logger.info("✅ %s succeeded on attempt %d", operation_name, attempt)
            return result
        except subprocess.CalledProcessError as exc:
            last_error = exc
            logger.warning(
                "⚠️  %s failed (attempt %d/%d): %s\n    stderr: %s",
                operation_name,
                attempt,
                MAX_RETRIES,
                exc,
                exc.stderr.strip() if exc.stderr else "(none)",
            )
            if attempt < MAX_RETRIES:
                delay = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.info("   Retrying in %ds …", delay)
                time.sleep(delay)
        except subprocess.TimeoutExpired as exc:
            last_error = exc
            logger.warning(
                "⚠️  %s timed out (attempt %d/%d)",
                operation_name,
                attempt,
                MAX_RETRIES,
            )
            if attempt < MAX_RETRIES:
                delay = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                time.sleep(delay)

    raise RuntimeError(
        f"❌ {operation_name} failed after {MAX_RETRIES} attempts"
    ) from last_error


# ---------------------------------------------------------------------------
# Repository safety checks
# ---------------------------------------------------------------------------


def _get_remote_url(repo_dir: Path) -> Optional[str]:
    """Return the 'origin' remote URL of a git repository, or None."""
    try:
        result = _run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_dir,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def _normalise_repo_url(url: str) -> str:
    """Normalise a git remote URL for comparison.

    Strips the protocol, optional ``user:token@`` prefix, ``.git`` suffix,
    and trailing slashes.  Handles both HTTPS and SSH-style URLs.
    """
    u = url.strip()

    # HTTPS:  https://<token>@github.com/user/repo.git
    # SSH:    git@github.com:user/repo.git
    if "://" in u:
        _, u = u.split("://", 1)
    if "@" in u:
        _, u = u.split("@", 1)
    # Normalise SSH colon separator to slash
    if ":" in u and "/" not in u.split(":")[0]:
        # Looks like SSH host:path — replace first colon with slash
        u = u.replace(":", "/", 1)
    # Strip trailing slash BEFORE checking .git suffix
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u.lower()


def _verify_remote_matches(
    repo_dir: Path,
    expected_url: str,
) -> bool:
    """Check that an existing git repo's remote matches the configured URL.

    Returns ``False`` (causing the caller to abort) when:
    - The directory is not a git repo at all.
    - The remote URL cannot be determined.
    - The remote URL does *not* point to the same host + path as the
      configured ``repo_url`` (this prevents accidentally force-resetting
      an unrelated project).
    """
    git_dir = repo_dir / ".git"
    if not git_dir.exists():
        logger.warning(
            "⚠️  %s exists but is NOT a git repository. "
            "Skipping to avoid data loss.",
            repo_dir,
        )
        return False

    remote = _get_remote_url(repo_dir)
    if remote is None:
        logger.warning("⚠️  Could not determine remote URL of %s", repo_dir)
        return False

    norm_expected = _normalise_repo_url(expected_url)
    norm_actual = _normalise_repo_url(remote)

    if norm_expected != norm_actual:
        logger.error(
            "❌ SAFETY CHECK FAILED\n"
            "   The directory %s is already a git repository, but its\n"
            "   remote URL does not match the configured repo_url.\n"
            "   \n"
            "   Configured:  %s\n"
            "   Actual:      %s\n"
            "   \n"
            "   To avoid damaging an unrelated project, the script will now exit.\n"
            "   Set 'working_dir' to a different path in config.yaml.",
            repo_dir,
            _safe_url_display(expected_url),
            _safe_url_display(remote),
        )
        return False

    return True


def _safe_url_display(url: str) -> str:
    """Return a safe-for-logging version of a repo URL (no token)."""
    u = url.strip()
    if "@" in u and "://" in u:
        proto, rest = u.split("://", 1)
        _user_token, host_path = rest.split("@", 1)
        return f"{proto}://<token>@{host_path}"
    return u


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clone_or_pull(cfg, token: str) -> Path:
    """Ensure the target repository is available locally.

    - If ``working_dir`` does not exist → clone from remote.
    - If it exists AND is the correct repo → ``git fetch`` + ``git reset --hard``.
    - If it exists but is an unrelated repo → **refuse** to touch it.

    Args:
        cfg: ``AppConfig`` instance.
        token: GitHub Personal Access Token.

    Returns:
        The ``Path`` to the local repository directory.
    """
    from src.config import build_auth_url

    repo_dir = Path(cfg.working_dir).resolve()
    auth_url = build_auth_url(cfg, token)
    branch = cfg.git.branch

    if not repo_dir.exists():
        logger.info("📥 Cloning repository …")
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        _retry_git_op(
            "clone",
            [
                "git", "clone",
                "--branch", branch,
                "--single-branch",
                auth_url,
                str(repo_dir),
            ],
        )
        logger.info("✅ Repository cloned to %s", repo_dir)
    else:
        # Safety: verify the existing repo matches the configured URL
        if not _verify_remote_matches(repo_dir, cfg.git.repo_url):
            print(
                "❌ Aborting — working_dir contains a different repository.\n"
                "   Move or delete it, or change 'working_dir' in config.yaml.",
                file=sys.stderr,
            )
            sys.exit(1)

        logger.info("📂 Repository already exists at %s — fetching latest …", repo_dir)
        _retry_git_op("fetch", ["git", "fetch", "origin", branch], cwd=repo_dir)
        _retry_git_op(
            "reset",
            ["git", "reset", "--hard", f"origin/{branch}"],
            cwd=repo_dir,
        )
        logger.info("✅ Reset to origin/%s", branch)

    return repo_dir


def commit_and_push(
    repo_dir: Path,
    commit_message: str,
    files: list[str],
    branch: str = "main",
) -> bool:
    """Stage changes, commit, and push to the remote.

    If the push is rejected (non-fast-forward), a ``git pull --rebase`` is
    performed before retrying.

    Args:
        repo_dir: Local repository path.
        commit_message: The commit message to use.
        files: List of file paths (relative to repo root) that were modified.
        branch: Target branch name.

    Returns:
        ``True`` if a commit was created and pushed; ``False`` if there were
        no changes to commit (nothing to do).
    """
    # Stage only the files we touched
    staged = False
    for f in files:
        file_path = repo_dir / f
        if file_path.exists():
            _retry_git_op(f"add {f}", ["git", "add", f], cwd=repo_dir)
            staged = True
        else:
            logger.warning("⚠️  File not found, skipping add: %s", file_path)

    if not staged:
        logger.warning("⚠️  No files could be staged — nothing to do.")
        return False

    # Check if there is anything to commit
    try:
        status = _run(["git", "status", "--porcelain"], cwd=repo_dir)
    except subprocess.CalledProcessError:
        logger.error("❌ Failed to check git status")
        return False

    if not status.stdout.strip():
        logger.info("ℹ️  No changes detected — nothing to commit.")
        return False

    logger.debug("Changes:\n%s", status.stdout)

    # Commit
    _retry_git_op(
        "commit",
        ["git", "commit", "-m", commit_message],
        cwd=repo_dir,
    )

    # Push with non-fast-forward handling
    _push_with_rebase(repo_dir, branch)

    logger.info("🚀 Pushed: %s", commit_message)
    return True


def _push_with_rebase(repo_dir: Path, branch: str) -> None:
    """Push to origin, with pull--rebase fallback on rejection.

    Tries a normal push first.  If it fails with a non-fast-forward rejection
    (exit code 1 and stderr mentioning ``non-fast-forward``, ``rejected``, or
    ``fetch first``), pulls with rebase and retries the push.

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _run(["git", "push", "origin", branch], cwd=repo_dir)
            if attempt > 1:
                logger.info("✅ push succeeded on attempt %d", attempt)
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            stderr_lower = (exc.stderr or "").lower()
            is_rejection = any(
                kw in stderr_lower
                for kw in ("non-fast-forward", "rejected", "fetch first")
            )

            if is_rejection and attempt < MAX_RETRIES:
                logger.warning(
                    "⚠️  Push rejected (non-fast-forward) — pulling with rebase …"
                )
                try:
                    _run(
                        ["git", "pull", "--rebase", "origin", branch],
                        cwd=repo_dir,
                    )
                except subprocess.CalledProcessError as rebase_err:
                    logger.error(
                        "❌ Rebase failed: %s",
                        rebase_err.stderr.strip() if rebase_err.stderr else rebase_err,
                    )
                    # Abort the rebase if possible (ignore errors — there
                    # may not be a rebase in progress to abort).
                    try:
                        _run(
                            ["git", "rebase", "--abort"],
                            cwd=repo_dir,
                        )
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                        pass
                    raise RuntimeError(
                        "Push rebase failed — manual intervention may be needed"
                    ) from rebase_err
                continue
            elif attempt < MAX_RETRIES:
                delay = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "⚠️  push failed (attempt %d/%d): %s",
                    attempt,
                    MAX_RETRIES,
                    exc.stderr.strip() if exc.stderr else exc,
                )
                logger.info("   Retrying in %ds …", delay)
                time.sleep(delay)

    raise RuntimeError(
        f"❌ push failed after {MAX_RETRIES} attempts"
    ) from last_error


def configure_git_user(
    repo_dir: Path,
    name: str = "auto-commit-bot",
    email: str = "auto-commit-bot@users.noreply.github.com",
) -> None:
    """Set local git user.name and user.email for the repository.

    These settings only affect the local repo (no ``--global``), so they will
    not interfere with the user's personal git configuration.
    """
    _run(["git", "config", "user.name", name], cwd=repo_dir)
    _run(["git", "config", "user.email", email], cwd=repo_dir)
    logger.debug("Git user configured: %s <%s>", name, email)
