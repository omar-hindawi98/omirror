"""Wi-Fi management via NetworkManager (nmcli).

NetworkManager is the default on Raspberry Pi OS Bookworm (the current
recommended release). If nmcli is not found, both functions log a clear
error and return safe defaults rather than crashing.
"""

import logging
import shutil
import subprocess

log = logging.getLogger(__name__)


def _nmcli_available() -> bool:
    return shutil.which("nmcli") is not None


def scan() -> list[str]:
    """Return a deduplicated list of visible SSID strings.

    Triggers a fresh scan via nmcli so results reflect current conditions.
    Returns an empty list if nmcli is unavailable or the scan fails.
    """
    if not _nmcli_available():
        log.error("nmcli not found — is NetworkManager installed?")
        return []
    try:
        # --rescan yes forces a fresh scan rather than returning cached results.
        result = subprocess.run(
            ["nmcli", "--rescan", "yes", "-t", "-f", "SSID", "dev", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        ssids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return list(dict.fromkeys(ssids))  # deduplicate, preserve order
    except Exception:
        log.exception("Wi-Fi scan failed")
        return []


def connect(ssid: str, password: str) -> bool:
    """Connect to a Wi-Fi network. Returns True on success.

    If a connection profile for this SSID already exists, nmcli reuses it
    (updating the password). The call blocks until the connection succeeds or
    times out (~30 s).
    """
    if not _nmcli_available():
        log.error("nmcli not found — is NetworkManager installed?")
        return False
    if not ssid:
        log.warning("connect() called with empty SSID")
        return False
    try:
        result = subprocess.run(
            ["nmcli", "dev", "wifi", "connect", ssid, "password", password],
            capture_output=True,
            text=True,
            timeout=40,
        )
        if result.returncode == 0:
            log.info("Connected to %s", ssid)
            return True
        log.warning("nmcli connect failed (ssid=%r): %s", ssid, result.stderr.strip())
        return False
    except subprocess.TimeoutExpired:
        log.error("nmcli connect timed out for ssid=%r", ssid)
        return False
    except Exception:
        log.exception("Wi-Fi connect failed")
        return False
