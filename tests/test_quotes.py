import json

import pytest

from omirror.widgets.quotes import QuoteStore, _BUILTIN


@pytest.fixture
def store(tmp_path):
    return QuoteStore(tmp_path / "quotes.json")


def test_load_uses_builtin_when_no_cache(store):
    store.load()
    assert store.quote_list == _BUILTIN


def test_load_from_valid_cache(tmp_path):
    path = tmp_path / "quotes.json"
    quotes = [{"quote": "Test quote", "author": "Tester"}]
    path.write_text(json.dumps(quotes))

    s = QuoteStore(path)
    s.load()
    assert s.quote_list == quotes


def test_load_corrupted_cache_falls_back_to_builtin(tmp_path):
    path = tmp_path / "quotes.json"
    path.write_text("not valid json{{{")

    s = QuoteStore(path)
    s.load()
    assert s.quote_list == _BUILTIN


def test_load_empty_list_falls_back_to_builtin(tmp_path):
    path = tmp_path / "quotes.json"
    path.write_text("[]")

    s = QuoteStore(path)
    s.load()
    assert s.quote_list == _BUILTIN


def test_random_quote_returns_dict_with_required_keys(store):
    store.load()
    q = store.random_quote()
    assert "quote" in q
    assert "author" in q


def test_random_quote_uses_builtin_when_list_empty(store):
    store.quote_list = []
    q = store.random_quote()
    assert q in _BUILTIN


def test_save_persists_to_disk(tmp_path):
    path = tmp_path / "quotes.json"
    s = QuoteStore(path)
    quotes = [{"quote": "Hello", "author": "World"}]
    s.save(quotes)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data == quotes


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "quotes.json"
    s = QuoteStore(path)
    quotes = [{"quote": "A", "author": "B"}, {"quote": "C", "author": "D"}]
    s.save(quotes)
    s.load()
    assert s.quote_list == quotes
