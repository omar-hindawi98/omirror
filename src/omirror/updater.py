"""Over-the-air update via GitHub Releases.

Usage:
    from omirror import updater
    result = updater.update()   # returns UpdateResult

The updater:
1. Fetches the latest release tag from the GitHub API.
2. Compares it against the currently installed version.
3. If newer, runs `uv pip install` from the git tag and restarts the
   omirror systemd service.

"""

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum, auto

import requests

from omirror import __version__

log = logging.getLogger(__name__)

# --- configuration ---

# Replace with your actual GitHub repo, e.g. "omhi/omirror"
GITHUB_REPO = "omar-hindawi98/omirror"

_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_TIMEOUT = 10  # seconds


# --- result type ---


class Status(Enum):
    ALREADY_LATEST = auto()
    UPDATED = auto()
    FETCH_FAILED = auto()
    INSTALL_FAILED = auto()
    RESTART_FAILED = auto()


@dataclass
class UpdateResult:
    status: Status
    current_version: str
    latest_version: str | None = None
    error: str | None = None


# --- public API ---


def check_latest() -> str | None:
    """Return the latest release tag (e.g. 'v1.2.3'), or None on failure."""
    try:
        resp = requests.get(_RELEASES_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        tag = resp.json().get("tag_name", "")
        return tag if tag else None
    except Exception as exc:
        log.warning("Failed to fetch latest release: %s", exc)
        return None


def _tag_to_version(tag: str) -> str:
    """Strip leading 'v' from a tag for comparison."""
    return tag.lstrip("v")


def _version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


def update() -> UpdateResult:
    """Check for an update and install it if one is available."""
    current = __version__
    latest_tag = check_latest()

    if latest_tag is None:
        return UpdateResult(
            status=Status.FETCH_FAILED,
            current_version=current,
            error="Could not reach GitHub API",
        )

    latest = _tag_to_version(latest_tag)

    if _version_tuple(latest) <= _version_tuple(current):
        log.info("Already on latest version %s", current)
        return UpdateResult(
            status=Status.ALREADY_LATEST,
            current_version=current,
            latest_version=latest,
        )

    log.info("Updating %s → %s", current, latest)

    # Prefer uv if available, fall back to the pip bundled with this Python.
    uv = shutil.which("uv")
    if uv:
        cmd = [
            uv,
            "pip",
            "install",
            "--system",
            f"git+https://github.com/{GITHUB_REPO}.git@{latest_tag}",
        ]
    else:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            f"git+https://github.com/{GITHUB_REPO}.git@{latest_tag}",
        ]

    try:
        subprocess.run(cmd, check=True, timeout=120)
        log.info("Install succeeded")
    except subprocess.CalledProcessError as exc:
        log.error("Install failed: %s", exc)
        return UpdateResult(
            status=Status.INSTALL_FAILED,
            current_version=current,
            latest_version=latest,
            error=str(exc),
        )

    # Restart the systemd service so the new code takes effect.
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", "omirror"],
            check=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as exc:
        log.error("Service restart failed: %s", exc)
        return UpdateResult(
            status=Status.RESTART_FAILED,
            current_version=current,
            latest_version=latest,
            error=str(exc),
        )

    return UpdateResult(
        status=Status.UPDATED,
        current_version=current,
        latest_version=latest,
    )
