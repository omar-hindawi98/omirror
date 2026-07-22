import json
import threading
from datetime import datetime
from pathlib import Path

import requests

from omirror import config
from omirror.const import CACHED_DIR
from omirror.i18n import _

_CACHE = CACHED_DIR / "weather.json"
_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherStore:
    def __init__(self, cache_path: Path) -> None:
        self._cache = cache_path
        self.initialized = False
        self.api_key = ""
        self.city = ""
        self.country = "SE"
        # Stable list objects so module-level aliases always see current data.
        self.forecast: list[dict] = []
        self.sorted_forecast: list[dict] = []
        self._updated = False
        # Guards init() so _DataThread and _InfoThread cannot both run it concurrently.
        self._init_lock = threading.Lock()

    def init(self) -> None:
        """Initialise weather data. Safe to call from multiple threads."""
        if not self._init_lock.acquire(blocking=False):
            return
        try:
            self.api_key = config.get("weather_api", "")
            self.city = config.get("weather_city", "")
            self.country = config.get("weather_country", "SE")
            if not self.api_key or not self.city:
                return
            self.update_all()
            self._updated = True
            self.initialized = True
        except Exception:
            self.initialized = False
        finally:
            self._init_lock.release()

    def _get(self, url: str, params: dict) -> dict:
        params = {"appid": self.api_key, "units": "metric", **params}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def fetch_observation(self) -> None:
        """Re-read city/country from config and do a lightweight current-weather ping."""
        config.load()
        self.city = config.get("weather_city", "")
        self.country = config.get("weather_country", "SE")
        self._get(_CURRENT_URL, {"q": f"{self.city},{self.country}"})

    def get_city(self) -> str:
        return self.city

    def update_all(self) -> None:
        if not self.api_key or not self.city:
            return

        data = self._get(_FORECAST_URL, {"q": f"{self.city},{self.country}", "cnt": 40})
        current = self._get(_CURRENT_URL, {"q": f"{self.city},{self.country}"})

        sunrise = current.get("sys", {}).get("sunrise", 0)
        sunset = current.get("sys", {}).get("sunset", 0)
        sunrise_iso = datetime.fromtimestamp(sunrise).isoformat() if sunrise else ""
        sunset_iso = datetime.fromtimestamp(sunset).isoformat() if sunset else ""

        slots = _pick_slots(data["list"])

        new_forecast = []
        for i, w in enumerate(slots):
            main = w["main"]
            dt = datetime.fromtimestamp(w["dt"])
            entry = {
                "status": w["weather"][0]["id"],
                "temp": main["temp"],
                "temp_max": main["temp_max"],
                "temp_min": main["temp_min"],
                "sunrise": sunrise_iso,
                "sunset": sunset_iso,
                "day": dt.strftime("%A").capitalize(),
                "id": i,
            }
            try:
                if self.forecast[i] != entry:
                    self._updated = True
            except (IndexError, KeyError):
                pass
            new_forecast.append(entry)

        # Mutate in place to preserve external list-object references.
        self.forecast[:] = new_forecast
        self.sorted_forecast[:] = self.forecast
        self.save()

    def save(self) -> None:
        with open(self._cache, "w") as f:
            json.dump(self.forecast, f)

    def load(self) -> None:
        if not self._cache.exists():
            return
        try:
            with open(self._cache) as f:
                data = f.read()
                if data:
                    # Mutate in place to preserve external list-object references.
                    self.forecast[:] = list(json.loads(data))
                    self.sorted_forecast[:] = sorted(self.forecast, key=lambda k: k["id"])
        except (json.JSONDecodeError, KeyError):
            pass

    def is_updated(self) -> bool:
        if self._updated:
            self._updated = False
            return True
        return False


def _pick_slots(items: list[dict]) -> list[dict]:
    """Pick 8 representative forecast slots from the OWM 3-hour list.

    Slots 0-3: the next four 3-hour steps after now (near-term).
    Slots 4-7: the 14:00 entry for each of the next four calendar days
               (most representative daily temperature); falls back to any
               available future slot if 14:00 is missing near the end of
               the 5-day forecast window.
    """
    now = datetime.now()
    today = now.date()

    near = [w for w in items if datetime.fromtimestamp(w["dt"]) > now][:4]

    by_day = {}
    for w in items:
        d = datetime.fromtimestamp(w["dt"])
        if d.date() > today and d.date() not in by_day:
            by_day[d.date()] = None
        if d.date() > today and d.hour == 14:
            by_day[d.date()] = w

    afternoon = [v for v in list(by_day.values())[:4] if v is not None]

    if len(afternoon) < 4:
        all_future = [w for w in items if datetime.fromtimestamp(w["dt"]).date() > today]
        seen = {w["dt"] for w in afternoon}
        for w in all_future:
            if len(afternoon) >= 4:
                break
            if w["dt"] not in seen:
                afternoon.append(w)
                seen.add(w["dt"])

    return near + afternoon[:4]


# Maps OWM condition codes to translation message IDs.
_DESCRIPTION: dict[int | tuple, str] = {
    800: "Clear sky",
    801: "Few clouds",
    802: "Scattered clouds",
    (803, 804): "Cloudy",
    (300, 321): "Drizzle",
    (500, 502): "Light rain",
    (503, 531): "Rain",
    (200, 202): "Thunderstorm with rain",
    (210, 221): "Thunderstorm",
    (222, 232): "Thunderstorm with drizzle",
    (600, 622): "Snow",
    (701, 781): "Foggy",
}

_IMAGE_RANGES: list[tuple] = [
    ((803, 804), "4"),
    ((300, 502), "8"),
    ((503, 531), "7"),
    ((200, 232), "9"),
    ((600, 622), "5"),
    ((701, 781), "6"),
]


def weather_description(code: int) -> str:
    """Return a translated description for an OWM condition code."""
    for key, label in _DESCRIPTION.items():
        if isinstance(key, tuple):
            lo, hi = key
            if lo <= code <= hi:
                return _(label)
        elif key == code:
            return _(label)
    return _("Unknown")


def is_night() -> bool:
    h = datetime.now().hour
    return h >= 19 or h < 4


def get_image(big: int, code: int) -> str:
    """Return the image filename stem for the given OWM code."""
    for num, exact in ((800, "1"), (801, "2"), (802, "3")):
        if code == num:
            if big == 1:
                night = "_night" if exact in ("1", "2", "3") and is_night() else ""
                return f"weather_{exact}_big{night}"
            return f"weather_{exact}_small"
    suffix = "_big" if big == 1 else "_small"
    for (lo, hi), num in _IMAGE_RANGES:
        if lo <= code <= hi:
            return f"weather_{num}{suffix}"
    return "weather_1" + suffix


# Module-level singleton — app.py imports this as `weather as weather_data` and
# accesses .city, .country, .api_key, .initialized, and calls methods directly.
# display/widgets/weather.py uses `data.forecast` and module-level functions.
_store = WeatherStore(_CACHE)

# Expose forecast as a module-level alias (same object, in-place mutated by the store).
forecast = _store.forecast
sorted_forecast = _store.sorted_forecast


def get_city() -> str:
    return _store.get_city()


# Module __getattr__ / __setattr__ forwards attribute access for the names that
# app.py reads and writes directly on the module (city, country, api_key, initialized).
_FORWARDED = {"city", "country", "api_key", "initialized"}


def __getattr__(name: str):
    if name in _FORWARDED:
        return getattr(_store, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value):  # type: ignore[override]
    if name in _FORWARDED:
        setattr(_store, name, value)
    else:
        import sys

        sys.modules[__name__].__dict__[name] = value


def init() -> None:
    _store.init()


def fetch_observation() -> None:
    _store.fetch_observation()


def update_all() -> None:
    _store.update_all()


def save() -> None:
    _store.save()


def load() -> None:
    _store.load()


def is_updated() -> bool:
    return _store.is_updated()
