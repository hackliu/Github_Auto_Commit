"""Configuration loader — reads config.yaml and .env, returns typed config objects."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

import yaml
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GitConfig:
    """Git-specific configuration."""

    repo_url: str
    branch: str = "main"
    token_env_var: str = "GIT_AUTO_COMMIT_TOKEN"


@dataclass
class CommitConfig:
    """Commit behaviour configuration."""

    min_daily: int = 0
    max_daily: int = 8
    min_interval_minutes: int = 30
    max_interval_minutes: int = 180
    messages: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=lambda: ["activity.log"])
    user_name: str = "auto-commit-bot"
    user_email: str = "auto-commit-bot@users.noreply.github.com"


@dataclass
class AppConfig:
    """Top-level application configuration."""

    git: GitConfig
    commit: CommitConfig
    working_dir: str = "./repo"
    log_level: str = "INFO"
    active_hours: Tuple[int, int] = (8, 23)
    skip_weekends: bool = False


# ---------------------------------------------------------------------------
# Default messages (used when config.yaml has no messages list)
# ---------------------------------------------------------------------------

DEFAULT_MESSAGES: List[str] = [
    "📝 update activity log",
    "🔧 minor tweaks and improvements",
    "📊 refresh analytics data",
    "🔄 auto-sync: update records",
    "✅ complete daily checkpoint",
    "🐛 fix typo in documentation",
    "💡 add new idea to notes",
    "📌 pin progress update",
    "🎨 format code style",
    "⚡ performance optimization",
    "📚 update documentation",
    "🔒 security maintenance",
    "🌐 update dependencies",
    "✨ add small feature",
    "🗑️ cleanup deprecated code",
]

DEFAULT_FILES: List[str] = ["activity.log"]

# Maximum length for commit messages (git recommends 72-char subject, but
# we're lenient and allow multi-line style messages up to 256 chars).
MAX_MESSAGE_LENGTH = 256
MAX_FILENAME_LENGTH = 255


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_config(cfg: AppConfig) -> None:
    """Validate configuration values and exit early on fatal problems."""
    errors: List[str] = []
    warnings: List[str] = []

    # --- git.repo_url ---
    if not cfg.git.repo_url:
        errors.append("git.repo_url must not be empty")
    elif not cfg.git.repo_url.lower().startswith("https://"):
        errors.append(
            "git.repo_url must use HTTPS (e.g. https://github.com/...). "
            "SSH is not supported."
        )
    elif not cfg.git.repo_url.rstrip("/").endswith(".git"):
        # GitHub now creates repos without the .git suffix by default.
        # This is a warning, not a hard error, because the URL still works.
        warnings.append(
            "git.repo_url does not end with '.git' — this is fine for "
            "GitHub, but verify the URL is correct."
        )

    # --- git.branch ---
    if ".." in (cfg.git.branch or ""):
        errors.append("git.branch contains '..' which is not allowed")

    # --- commit frequency ---
    if cfg.commit.min_daily < 0:
        errors.append("commit.min_daily must be >= 0")
    if cfg.commit.max_daily < cfg.commit.min_daily:
        errors.append("commit.max_daily must be >= commit.min_daily")
    if cfg.commit.min_interval_minutes < 1:
        errors.append("commit.min_interval_minutes must be >= 1")
    if cfg.commit.max_interval_minutes < cfg.commit.min_interval_minutes:
        errors.append(
            "commit.max_interval_minutes must be >= commit.min_interval_minutes"
        )

    # --- commit files ---
    if not cfg.commit.files:
        errors.append("commit.files must contain at least one file name")

    # All entries lowercase — comparison is done with .lower()
    dangerous_basenames = {
        ".env", ".git", ".gitignore", ".gitmodules",
        "config.yaml", "config.yml", "docker-compose.yml", "dockerfile",
        "makefile",
    }

    for fname in cfg.commit.files:
        if not fname or not fname.strip():
            errors.append("commit.files contains an empty or blank entry")
            break
        if len(fname) > MAX_FILENAME_LENGTH:
            errors.append(
                f"commit.files: '{fname[:40]}…' exceeds {MAX_FILENAME_LENGTH} chars"
            )
        if fname.startswith("/") or fname.startswith("\\"):
            errors.append(
                f"commit.files: '{fname}' is an absolute path — only "
                f"relative paths (e.g. 'activity.log') are allowed"
            )
        if ".." in fname:
            errors.append(
                f"commit.files: '{fname}' contains '..' which is not "
                f"allowed (path traversal)"
            )
        # Extract basename (last component regardless of separator style)
        base = re.split(r"[/\\]", fname)[-1]
        if base.lower() in dangerous_basenames:
            errors.append(
                f"commit.files: '{fname}' points to a sensitive file. "
                f"Modifying this file could compromise the repository."
            )

    # --- commit messages ---
    if cfg.commit.messages:
        for i, msg in enumerate(cfg.commit.messages):
            if len(msg) > MAX_MESSAGE_LENGTH:
                errors.append(
                    f"commit.messages[{i}]: message exceeds "
                    f"{MAX_MESSAGE_LENGTH} characters"
                )
            if "\x00" in msg:
                errors.append(
                    f"commit.messages[{i}]: message contains null byte"
                )

    # --- active hours ---
    if cfg.active_hours[0] < 0 or cfg.active_hours[1] > 24:
        errors.append("active_hours values must be in [0, 24]")
    if cfg.active_hours[0] >= cfg.active_hours[1]:
        errors.append("active_hours[0] must be < active_hours[1]")

    # --- working_dir sanity ---
    working = os.path.abspath(cfg.working_dir)
    home = os.path.expanduser("~")
    if working == home or working == os.path.join(home, "Desktop"):
        warnings.append(
            f"working_dir points to '{working}' — this seems unsafe. "
            f"Consider using a dedicated sub-directory like './repo'."
        )

    # Print warnings first
    if warnings:
        print("⚠️  Configuration warnings:", file=sys.stderr)
        for w in warnings:
            print(f"   • {w}", file=sys.stderr)

    # Then errors (and exit)
    if errors:
        print("❌ Configuration errors:", file=sys.stderr)
        for e in errors:
            print(f"   • {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """Load and validate configuration from a YAML file and .env.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        A fully-populated, validated ``AppConfig`` instance.
    """
    # Load .env so tokens are available early.  Search relative to the
    # config file directory so the script works regardless of CWD.
    config_dir = Path(config_path).resolve().parent
    dotenv_path = config_dir / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
    else:
        # Fall back to default search (CWD and parents)
        load_dotenv()

    # Read YAML
    yaml_path = Path(config_path)
    if not yaml_path.exists():
        print(
            f"❌ Configuration file not found: {yaml_path.absolute()}",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(yaml_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if data is None:
        print(
            f"❌ Configuration file is empty: {yaml_path.absolute()}",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Git section ---
    git_raw = data.get("git", {})
    git = GitConfig(
        repo_url=git_raw.get("repo_url", ""),
        branch=git_raw.get("branch", "main"),
        token_env_var=git_raw.get("token_env_var", "GIT_AUTO_COMMIT_TOKEN"),
    )

    # --- Commit section ---
    commit_raw = data.get("commit", {})

    # Distinguish "key missing" from "empty list explicitly provided"
    messages = commit_raw.get("messages")
    if messages is None:
        messages = DEFAULT_MESSAGES
    files = commit_raw.get("files")
    if files is None:
        files = DEFAULT_FILES

    commit = CommitConfig(
        min_daily=int(commit_raw.get("min_daily", 0)),
        max_daily=int(commit_raw.get("max_daily", 8)),
        min_interval_minutes=int(commit_raw.get("min_interval_minutes", 30)),
        max_interval_minutes=int(commit_raw.get("max_interval_minutes", 180)),
        messages=list(messages),
        files=list(files),
        user_name=str(commit_raw.get("user_name", "auto-commit-bot")),
        user_email=str(commit_raw.get("user_email", "auto-commit-bot@users.noreply.github.com")),
    )

    # --- Top-level ---
    active_hours_raw = data.get("active_hours", [8, 23])
    active_hours: Tuple[int, int] = (
        int(active_hours_raw[0]),
        int(active_hours_raw[1]),
    )

    cfg = AppConfig(
        git=git,
        commit=commit,
        working_dir=str(data.get("working_dir", "./repo")),
        log_level=str(data.get("log_level", "INFO")).upper(),
        active_hours=active_hours,
        skip_weekends=bool(data.get("skip_weekends", False)),
    )

    _validate_config(cfg)
    return cfg


def get_token(cfg: AppConfig) -> str:
    """Retrieve the GitHub token from the environment.

    Args:
        cfg: Application configuration.

    Returns:
        The token string.

    Raises:
        SystemExit: If the token environment variable is missing or empty.
    """
    token = os.getenv(cfg.git.token_env_var)
    if not token:
        print(
            f"❌ Environment variable '{cfg.git.token_env_var}' is not set.\n"
            f"   Create a .env file (see .env.example) or export the variable.",
            file=sys.stderr,
        )
        sys.exit(1)
    # Basic sanity check — classic tokens start with "ghp_", fine-grained
    # tokens start with "github_pat_".  Warn if it looks wrong but don't
    # reject (GitHub may add new prefixes).
    if not (
        token.startswith("ghp_")
        or token.startswith("github_pat_")
        or token.startswith("gho_")
    ):
        print(
            "⚠️  WARNING: Token does not match known GitHub PAT formats.\n"
            "   Expected 'ghp_…' (classic) or 'github_pat_…' (fine-grained).\n"
            "   If this is intentional, ignore this warning.",
            file=sys.stderr,
        )
    return token


def build_auth_url(cfg: AppConfig, token: str) -> str:
    """Embed the token into the HTTPS repo URL for authentication.

    Handles any capitalisation of ``https://`` in the configured URL.

    Example:
        https://github.com/user/repo.git  →
        https://<token>@github.com/user/repo.git

    Security note:
        The resulting URL is passed as a command-line argument to ``git`` and
        may be visible in system process lists (``/proc/<pid>/cmdline`` on
        Linux, ``ps`` on macOS).  On a single-user machine this is an
        acceptable trade-off.  In high-security environments, consider using
        SSH keys or git's credential-helper system instead.
    """
    url = cfg.git.repo_url
    if re.match(r"^https://", url, re.IGNORECASE):
        # Only replace the scheme portion — the rest of the URL is left intact
        scheme = url[: url.index("://") + 3]
        return scheme + token + "@" + url[len(scheme) :]
    return url
