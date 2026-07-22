import contextlib
import json
import logging
import threading

from omirror.const import SETTINGS_FILE, SETTINGS_LOCAL_FILE

log = logging.getLogger(__name__)

_data: dict = {}
# Single lock guards both _data reads and writes so background threads
# can call get() while the data thread calls load() without races.
_lock = threading.Lock()


def load():
    """Reload settings from disk into the in-memory cache.

    Reads settings.json first, then merges settings.local.json on top so
    local overrides (API keys, dev settings) win without being committed.
    """
    global _data
    if not SETTINGS_FILE.exists():
        return
    with _lock:
        try:
            with open(SETTINGS_FILE) as f:
                merged = json.load(f)
        except (json.JSONDecodeError, OSError):
            log.exception("Failed to load %s", SETTINGS_FILE)
            return

        if SETTINGS_LOCAL_FILE.exists():
            try:
                with open(SETTINGS_LOCAL_FILE) as f:
                    merged.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                log.exception("Failed to load %s", SETTINGS_LOCAL_FILE)

        _data = merged


def get(key, default=None):
    """Return the value for *key* from the in-memory cache, thread-safely."""
    with _lock:
        return _data.get(key, default)


def set(key, value):
    """Write *value* for *key* in-memory and persist to disk under the same lock."""
    with _lock:
        _data[key] = value
        _save()


def _save():
    """Persist the current in-memory state to settings.json. Must be called under _lock.

    Writes to a .tmp file first, then atomically renames it over the real file so a
    crash or full-disk mid-write never leaves settings.json truncated/corrupt.
    """
    import os

    tmp = SETTINGS_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(_data, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)
    except OSError:
        log.exception("Failed to save settings")
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
