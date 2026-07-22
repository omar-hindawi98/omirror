import json
from datetime import datetime
from pathlib import Path

from omirror.const import CACHED_DIR, TIME_FMT, in_time_window


class CenteredTextStore:
    def __init__(self, cache_path: Path) -> None:
        self._cache = cache_path
        # Stable list object so module-level `entries` alias stays valid.
        self.entries: list[dict] = []

    def init(self) -> None:
        self.load()

    def add(self, time_start: str, time_end: str, text: str) -> None:
        self.entries.append({"text": text, "time_start": time_start, "time_end": time_end})
        self.save()

    def remove(self, id: int) -> None:
        try:
            self.entries.pop(id)
            self.save()
        except IndexError:
            pass

    def get_active_text(self) -> str | None:
        """Return the text whose time range covers now, or None."""
        now = datetime.now()
        for e in self.entries:
            start = datetime.strptime(e["time_start"], TIME_FMT)
            end = datetime.strptime(e["time_end"], TIME_FMT)
            t1 = [start.hour, start.minute]
            t2 = [end.hour, end.minute]
            if in_time_window(now, t1, t2):
                return e["text"]
        return None

    def save(self) -> None:
        with open(self._cache, "w") as f:
            json.dump(self.entries, f)

    def load(self) -> None:
        if not self._cache.exists():
            return
        try:
            with open(self._cache) as f:
                data = f.read()
                if data:
                    # Mutate in place to preserve external list-object references.
                    self.entries[:] = list(json.loads(data))
        except (json.JSONDecodeError, KeyError):
            pass


# Module-level singleton. gatt.py reads `centered_text.entries` directly,
# so `entries` is a stable alias to the store's own list object.
_store = CenteredTextStore(CACHED_DIR / "centered_text.json")
entries = _store.entries


def init() -> None:
    _store.init()


def add(time_start: str, time_end: str, text: str) -> None:
    _store.add(time_start, time_end, text)


def remove(id: int) -> None:
    _store.remove(id)


def get_active_text() -> str | None:
    return _store.get_active_text()


def save() -> None:
    _store.save()


def load() -> None:
    _store.load()
