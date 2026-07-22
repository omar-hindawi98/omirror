import json
import logging
import random
from pathlib import Path

import requests

from omirror.const import CACHED_DIR

log = logging.getLogger(__name__)

_BUILTIN = [
    {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs"},
    {"quote": "In the middle of every difficulty lies opportunity.", "author": "Albert Einstein"},
    {
        "quote": "It does not matter how slowly you go as long as you do not stop.",
        "author": "Confucius",
    },
    {"quote": "Life is what happens when you're busy making other plans.", "author": "John Lennon"},
    {
        "quote": "The future belongs to those who believe in the beauty of their dreams.",
        "author": "Eleanor Roosevelt",
    },
    {"quote": "Spread love everywhere you go.", "author": "Mother Teresa"},
    {
        "quote": "When you reach the end of your rope, tie a knot in it and hang on.",
        "author": "Franklin D. Roosevelt",
    },
    {"quote": "Always remember that you are absolutely unique.", "author": "Margaret Mead"},
    {
        "quote": "Do not go where the path may lead; go instead where there is no path.",
        "author": "Ralph Waldo Emerson",
    },
    {
        "quote": "You will face many defeats in life, but never let yourself be defeated.",
        "author": "Maya Angelou",
    },
    {
        "quote": "The greatest glory in living lies not in never falling, but in rising every time we fall.",
        "author": "Nelson Mandela",
    },
    {
        "quote": "In the end, it's not the years in your life that count. It's the life in your years.",
        "author": "Abraham Lincoln",
    },
    {
        "quote": "Never let the fear of striking out keep you from playing the game.",
        "author": "Babe Ruth",
    },
    {"quote": "Life is either a daring adventure or nothing at all.", "author": "Helen Keller"},
    {
        "quote": "Many of life's failures are people who did not realize how close they were to success.",
        "author": "Thomas Edison",
    },
    {"quote": "You have brains in your head. You have feet in your shoes.", "author": "Dr. Seuss"},
    {
        "quote": "If life were predictable it would cease to be life and be without flavor.",
        "author": "Eleanor Roosevelt",
    },
    {
        "quote": "If you look at what you have in life, you'll always have more.",
        "author": "Oprah Winfrey",
    },
    {
        "quote": "If you want to live a happy life, tie it to a goal, not to people or things.",
        "author": "Albert Einstein",
    },
    {
        "quote": "The best time to plant a tree was 20 years ago. The second best time is now.",
        "author": "Chinese Proverb",
    },
]

_API_URL = "https://api.quotable.io/quotes/random"
_FETCH_COUNT = 50


class QuoteStore:
    def __init__(self, cache_path: Path) -> None:
        self._cache = cache_path
        self.quote_list: list[dict] = []

    def random_quote(self) -> dict[str, str]:
        pool = self.quote_list or _BUILTIN
        return random.choice(pool)

    def fetch(self) -> None:
        """Fetch fresh quotes from quotable.io and persist them to the cache.

        Falls back silently if the network is unavailable — the existing cache
        (or builtin list) continues to be used.
        """
        try:
            resp = requests.get(_API_URL, params={"limit": _FETCH_COUNT}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            fetched = [
                {"quote": item["content"], "author": item["author"]}
                for item in data
                if "content" in item and "author" in item
            ]
            if fetched:
                self.save(fetched)
                self.load()
                log.info("Fetched %d quotes from quotable.io", len(fetched))
        except requests.RequestException as exc:
            log.warning("Quote fetch failed: %s", exc)
        except Exception:
            log.exception("Unexpected error fetching quotes")

    def load(self) -> None:
        if not self._cache.exists():
            self.quote_list = list(_BUILTIN)
            return
        try:
            with open(self._cache) as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    self.quote_list = data
                    return
        except (json.JSONDecodeError, KeyError, ValueError):
            log.warning("Quote cache corrupted, falling back to builtin quotes")
        self.quote_list = list(_BUILTIN)

    def save(self, quotes: list[dict[str, str]]) -> None:
        """Persist a list of quote dicts with 'quote' and 'author' keys."""
        try:
            with open(self._cache, "w") as f:
                json.dump(quotes, f, indent=2)
        except OSError:
            log.exception("Failed to save quotes cache")


# Module-level singleton
_store = QuoteStore(CACHED_DIR / "quotes.json")


def random_quote() -> dict[str, str]:
    return _store.random_quote()


def fetch() -> None:
    _store.fetch()


def load() -> None:
    _store.load()


def save(quotes: list[dict[str, str]]) -> None:
    _store.save(quotes)
