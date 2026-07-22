import json
import logging
from pathlib import Path

import feedparser

from omirror.const import CACHED_DIR

log = logging.getLogger(__name__)


class NewsStore:
    def __init__(self, cache_path: Path) -> None:
        self._cache = cache_path
        self.rss_url = "http://www.aftonbladet.se/nyheter/rss.xml"
        self.max_items = 5
        self._updated = False
        # Stable list objects so module-level aliases always see current data.
        self.articles: list[dict] = []
        self.sorted_articles: list[dict] = []

    def set_rss(self, url: str) -> None:
        self.rss_url = url

    def set_max(self, count: int) -> None:
        self.max_items = count

    def parse(self) -> None:
        """Fetch and parse the RSS feed, updating the article cache on success."""
        try:
            feed = feedparser.parse(self.rss_url)
        except Exception:
            log.exception("RSS parse raised an exception for %s", self.rss_url)
            return

        status = getattr(feed, "status", None)
        if feed.bozo and not feed.entries:
            log.warning(
                "RSS feed error for %s: %s",
                self.rss_url,
                feed.get("bozo_exception", "unknown"),
            )
            return
        if status is not None and status not in (200, 301, 302):
            log.warning("RSS feed returned HTTP %d for %s", status, self.rss_url)
            return

        self.load()
        previous = self.articles[:]
        new_articles = []
        for i, post in enumerate(feed.entries):
            if i >= self.max_items:
                break
            try:
                title = post.get("title", "")
                date = post.get("published", "")
            except Exception:
                continue
            try:
                if previous[i]["title"] != title:
                    self._updated = True
            except IndexError:
                pass
            new_articles.append({"id": i, "title": title, "date": date})

        if new_articles:
            self.articles[:] = new_articles
            self.sorted_articles[:] = sorted(self.articles, key=lambda k: k["id"])
            self.save()

    def save(self) -> None:
        try:
            with open(self._cache, "w") as f:
                json.dump(self.articles, f)
        except OSError:
            log.exception("Failed to save news cache")

    def load(self) -> None:
        if not self._cache.exists():
            return
        try:
            with open(self._cache) as f:
                data = f.read()
                if data:
                    # Mutate in place to preserve external list-object references.
                    self.articles[:] = list(json.loads(data))
                    self.sorted_articles[:] = sorted(self.articles, key=lambda k: k["id"])
        except (json.JSONDecodeError, KeyError):
            log.warning("News cache corrupted, skipping load")

    def is_updated(self) -> bool:
        if self._updated:
            self._updated = False
            return True
        return False


# Module-level singleton — preserves the call-site API used in app.py and
# display/widgets/news.py. `rss_url` and `max_items` are forwarded as
# module-level properties so `news.rss_url` reads still work.
_store = NewsStore(CACHED_DIR / "news.json")
articles = _store.articles
sorted_articles = _store.sorted_articles


# `app.py` reads `news.rss_url` and `news.max_items` as module attributes
# before passing them to set_rss/set_max — expose them as dynamic lookups.
def __getattr__(name: str):
    if name == "rss_url":
        return _store.rss_url
    if name == "max_items":
        return _store.max_items
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def set_rss(url: str) -> None:
    _store.set_rss(url)


def set_max(count: int) -> None:
    _store.set_max(count)


def parse() -> None:
    _store.parse()


def save() -> None:
    _store.save()


def load() -> None:
    _store.load()


def is_updated() -> bool:
    return _store.is_updated()
