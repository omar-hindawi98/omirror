import json
import logging
from datetime import datetime
from pathlib import Path

from omirror.const import ACTIVITY_DATE_FMT, CACHED_DIR

log = logging.getLogger(__name__)


class ActivitiesStore:
    def __init__(self, cache_path: Path) -> None:
        self._cache = cache_path
        # Use stable list objects so module-level aliases always see current data.
        self.activities: list[dict] = []
        self.sorted_activities: list[dict] = []
        self._updated = False

    def _next_id(self) -> int:
        if not self.activities:
            return 0
        return max(a["id"] for a in self.activities) + 1

    def _rebuild_sorted(self) -> None:
        self.sorted_activities[:] = sorted(
            self.activities,
            key=lambda k: datetime.strptime(k["date"], ACTIVITY_DATE_FMT),
        )

    def add(self, client_id: int, date: datetime, text: str) -> None:
        """Add or update an activity.

        The BLE client sends a client_id with each activity. If an entry with that
        id already exists it is updated in place; otherwise a new entry is appended
        with a server-generated id so gaps in client_id values never cause overwrites.
        """
        date_str = date.strftime(ACTIVITY_DATE_FMT)
        for entry in self.activities:
            if entry["id"] == client_id:
                entry["date"] = date_str
                entry["text"] = text
                self._updated = True
                self._rebuild_sorted()
                self.save()
                return
        self.activities.append({"id": client_id, "date": date_str, "text": text})
        self._updated = True
        self._rebuild_sorted()
        self.save()

    def remove(self, client_id: int) -> None:
        """Remove the activity whose id matches client_id."""
        before = len(self.activities)
        self.activities[:] = [a for a in self.activities if a["id"] != client_id]
        if len(self.activities) != before:
            self._updated = True
            self._rebuild_sorted()
            self.save()

    def remove_past(self) -> None:
        to_remove = [
            e
            for e in self.activities
            if datetime.now() >= datetime.strptime(e["date"], ACTIVITY_DATE_FMT)
        ]
        for e in to_remove:
            self.activities.remove(e)
        if to_remove:
            self._updated = True
            self._rebuild_sorted()
            self.save()

    def save(self) -> None:
        try:
            with open(self._cache, "w") as f:
                json.dump(self.activities, f)
        except OSError:
            log.exception("Failed to save activities cache")

    def load(self) -> None:
        if not self._cache.exists():
            return
        try:
            with open(self._cache) as f:
                data = f.read()
                if data:
                    new_activities = list(json.loads(data))
                    if new_activities != self.activities:
                        # Mutate in place to preserve external list-object references.
                        self.activities[:] = new_activities
                        self.sorted_activities[:] = sorted(
                            self.activities,
                            key=lambda k: datetime.strptime(k["date"], ACTIVITY_DATE_FMT),
                        )
                        self._updated = True
        except (json.JSONDecodeError, KeyError, ValueError):
            log.warning("Activities cache corrupted, skipping load")

    def is_updated(self) -> bool:
        if self._updated:
            self._updated = False
            return True
        return False


# Module-level singleton — preserves the call-site API used in app.py, gatt.py,
# and display/widgets/activities.py. The `activities` and `sorted_activities`
# names below stay as stable references to the store's own list objects.
_store = ActivitiesStore(CACHED_DIR / "activities.json")
activities = _store.activities
sorted_activities = _store.sorted_activities


def init() -> None:
    _store.load()


def add(client_id: int, date: datetime, text: str) -> None:
    _store.add(client_id, date, text)


def remove(client_id: int) -> None:
    _store.remove(client_id)


def remove_past() -> None:
    _store.remove_past()


def save() -> None:
    _store.save()


def load() -> None:
    _store.load()


def is_updated() -> bool:
    return _store.is_updated()
