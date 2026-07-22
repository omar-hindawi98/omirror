import json
from datetime import datetime, timedelta

import pytest

from omirror.widgets.activities import ActivitiesStore
from omirror.const import ACTIVITY_DATE_FMT


@pytest.fixture
def store(tmp_path):
    return ActivitiesStore(tmp_path / "activities.json")


def _dt(offset_minutes=60):
    return datetime.now() + timedelta(minutes=offset_minutes)


def test_add_new(store):
    store.add(1, _dt(), "Buy milk")
    assert len(store.activities) == 1
    assert store.activities[0]["text"] == "Buy milk"
    assert len(store.sorted_activities) == 1


def test_add_updates_existing(store):
    store.add(1, _dt(), "Buy milk")
    store.add(1, _dt(120), "Buy bread")
    assert len(store.activities) == 1
    assert store.activities[0]["text"] == "Buy bread"


def test_add_different_ids_append(store):
    store.add(1, _dt(), "First")
    store.add(2, _dt(120), "Second")
    assert len(store.activities) == 2


def test_remove(store):
    store.add(1, _dt(), "Buy milk")
    assert len(store.activities) == 1
    stored_id = store.activities[0]["id"]
    store.remove(stored_id)
    assert len(store.activities) == 0


def test_remove_nonexistent_is_noop(store):
    store.add(1, _dt(), "Buy milk")
    store.remove(999)
    assert len(store.activities) == 1


def test_remove_past(store):
    past = datetime.now() - timedelta(minutes=5)
    store.add(1, past, "Expired task")
    store.add(2, _dt(), "Future task")
    store.remove_past()
    assert len(store.activities) == 1
    assert store.activities[0]["text"] == "Future task"


def test_is_updated_clears_flag(store):
    store.add(1, _dt(), "Task")
    assert store.is_updated() is True
    assert store.is_updated() is False


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "activities.json"
    s1 = ActivitiesStore(path)
    s1.add(1, _dt(), "Persisted")
    s1._updated = False  # reset after add

    s2 = ActivitiesStore(path)
    s2.load()
    assert len(s2.activities) == 1
    assert s2.activities[0]["text"] == "Persisted"


def test_sorted_activities_order(store):
    later = datetime.now() + timedelta(hours=2)
    sooner = datetime.now() + timedelta(hours=1)
    store.add(1, later, "Later task")
    store.add(2, sooner, "Sooner task")
    assert store.sorted_activities[0]["text"] == "Sooner task"
    assert store.sorted_activities[1]["text"] == "Later task"
