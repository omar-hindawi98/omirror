import datetime
from importlib.resources import files
from pathlib import Path

# Repo root — settings.json and cached/ live here
BASE_DIR = Path(__file__).parent.parent.parent

SETTINGS_FILE = BASE_DIR / "settings.json"
SETTINGS_LOCAL_FILE = BASE_DIR / "settings.local.json"
CACHED_DIR = BASE_DIR / "cached"

# Package assets — resolved via importlib so they work after install too
_assets = files("omirror.assets")
IMAGES_DIR = Path(str(_assets.joinpath("images")))
FONTS_DIR = Path(str(_assets.joinpath("fonts")))

# Ensure runtime directories exist on import
CACHED_DIR.mkdir(exist_ok=True)

# --- display ---

SCREEN_SIZE = (1200, 1000)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Shared by NewsWidget and ActivitiesWidget
LIST_WIDGET_SIZE = (250, 160)
LIST_ITEM_COUNT = 5
LIST_ITEM_ALPHAS = (255, 200, 150, 100, 50)
LIST_ITEM_TRUNCATE = 35  # characters before "…"

# --- data formats ---

ACTIVITY_DATE_FMT = "%Y-%m-%d %H:%M"
TIME_FMT = "%H:%M"

# --- bluetooth ---

BLE_SERVICE_UUID = "57c6fe8d-4dae-4978-b886-3dabf74c7c00"

# --- time utils ---


def in_time_window(
    now: datetime.datetime,
    t1: list[int],
    t2: list[int],
) -> bool:
    """Return True if *now* falls inside the [t1, t2] time window.

    t1 and t2 are [hour, minute] pairs. Handles both same-day (t1 <= t2)
    and overnight (t1 > t2) ranges — e.g. [22, 0] to [7, 0] wraps midnight.
    """

    def _after(t: list[int]) -> bool:
        return now.hour > t[0] or (now.hour == t[0] and now.minute >= t[1])

    def _before(t: list[int]) -> bool:
        return now.hour < t[0] or (now.hour == t[0] and now.minute <= t[1])

    if t1[0] < t2[0] or (t1[0] == t2[0] and t1[1] <= t2[1]):
        return _after(t1) and _before(t2)
    return _after(t1) or _before(t2)
