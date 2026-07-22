from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from omirror.display.centered_text import CenteredTextStore


@pytest.fixture
def store(tmp_path):
    return CenteredTextStore(tmp_path / "centered_text.json")


def _hhmm(dt):
    return dt.strftime("%H:%M")


def test_add_entry(store):
    start = _hhmm(datetime.now() - timedelta(minutes=5))
    end = _hhmm(datetime.now() + timedelta(minutes=5))
    store.add(start, end, "Hello world")
    assert len(store.entries) == 1
    assert store.entries[0]["text"] == "Hello world"


def test_get_active_text_inside_window(store):
    now = datetime.now()
    start = _hhmm(now - timedelta(minutes=5))
    end = _hhmm(now + timedelta(minutes=5))
    store.add(start, end, "Active message")
    assert store.get_active_text() == "Active message"


def test_get_active_text_outside_window(store):
    now = datetime.now()
    # Window already ended 10+ minutes ago
    start = _hhmm(now - timedelta(minutes=20))
    end = _hhmm(now - timedelta(minutes=10))
    store.add(start, end, "Expired message")
    assert store.get_active_text() is None


def test_get_active_text_no_entries(store):
    assert store.get_active_text() is None


def test_remove_by_index(store):
    now = datetime.now()
    start = _hhmm(now - timedelta(minutes=5))
    end = _hhmm(now + timedelta(minutes=5))
    store.add(start, end, "First")
    store.add(start, end, "Second")
    store.remove(0)
    assert len(store.entries) == 1
    assert store.entries[0]["text"] == "Second"


def test_remove_out_of_bounds_is_noop(store):
    now = datetime.now()
    store.add(_hhmm(now), _hhmm(now + timedelta(hours=1)), "Only entry")
    store.remove(99)
    assert len(store.entries) == 1


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "centered_text.json"
    s1 = CenteredTextStore(path)
    now = datetime.now()
    s1.add(_hhmm(now), _hhmm(now + timedelta(hours=1)), "Persisted")
    s1.load()

    s2 = CenteredTextStore(path)
    s2.load()
    assert len(s2.entries) == 1
    assert s2.entries[0]["text"] == "Persisted"


def test_load_missing_file_is_noop(store):
    store.load()
    assert store.entries == []
