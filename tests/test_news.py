import json
from unittest.mock import MagicMock, patch

import pytest

from omirror.widgets.news import NewsStore


@pytest.fixture
def store(tmp_path):
    return NewsStore(tmp_path / "news.json")


def test_set_rss(store):
    store.set_rss("http://example.com/rss.xml")
    assert store.rss_url == "http://example.com/rss.xml"


def test_set_max(store):
    store.set_max(10)
    assert store.max_items == 10


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "news.json"
    s1 = NewsStore(path)
    s1.articles[:] = [{"id": 0, "title": "Hello", "date": "Mon, 01 Jan 2024 00:00:00 +0000"}]
    s1.save()

    s2 = NewsStore(path)
    s2.load()
    assert len(s2.articles) == 1
    assert s2.articles[0]["title"] == "Hello"


def test_load_missing_file_is_noop(store):
    store.load()
    assert store.articles == []


def test_parse_skips_bozo_feed_with_no_entries(store):
    fake_feed = MagicMock()
    fake_feed.bozo = True
    fake_feed.entries = []
    with patch("feedparser.parse", return_value=fake_feed):
        store.parse()
    assert store.articles == []


def test_parse_skips_bad_http_status(store):
    fake_feed = MagicMock()
    fake_feed.bozo = False
    fake_feed.status = 500
    fake_feed.entries = [MagicMock()]
    with patch("feedparser.parse", return_value=fake_feed):
        store.parse()
    assert store.articles == []


def test_parse_populates_articles(store):
    entry = MagicMock()
    entry.get = lambda k, d="": {"title": "Breaking news", "published": "2024-01-01"}.get(k, d)

    fake_feed = MagicMock()
    fake_feed.bozo = False
    fake_feed.status = 200
    fake_feed.entries = [entry]

    with patch("feedparser.parse", return_value=fake_feed):
        store.parse()

    assert len(store.articles) == 1
    assert store.articles[0]["title"] == "Breaking news"


def test_is_updated_clears_flag(store):
    store._updated = True
    assert store.is_updated() is True
    assert store.is_updated() is False


def test_sorted_articles_by_id(tmp_path):
    path = tmp_path / "news.json"
    s = NewsStore(path)
    s.articles[:] = [{"id": 2, "title": "C"}, {"id": 0, "title": "A"}, {"id": 1, "title": "B"}]
    s.sorted_articles[:] = sorted(s.articles, key=lambda k: k["id"])
    assert [a["title"] for a in s.sorted_articles] == ["A", "B", "C"]
