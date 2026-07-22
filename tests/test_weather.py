import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from omirror.widgets.weather import WeatherStore, weather_description, get_image, _pick_slots


@pytest.fixture
def store(tmp_path):
    return WeatherStore(tmp_path / "weather.json")


# --- weather_description ---

def test_description_exact_code_clear():
    assert weather_description(800) == "Clear sky"


def test_description_exact_code_few_clouds():
    assert weather_description(801) == "Few clouds"


def test_description_range_light_rain():
    assert weather_description(500) == "Light rain"


def test_description_range_drizzle():
    assert weather_description(310) == "Drizzle"


def test_description_range_snow():
    assert weather_description(610) == "Snow"


def test_description_unknown_code():
    assert weather_description(999) == "Unknown"


# --- get_image ---

def test_get_image_clear_sky_day_big():
    with patch("omirror.widgets.weather.is_night", return_value=False):
        assert get_image(1, 800) == "weather_1_big"


def test_get_image_clear_sky_night_big():
    with patch("omirror.widgets.weather.is_night", return_value=True):
        assert get_image(1, 800) == "weather_1_big_night"


def test_get_image_clear_sky_small():
    assert get_image(0, 800) == "weather_1_small"


def test_get_image_cloudy_big():
    with patch("omirror.widgets.weather.is_night", return_value=False):
        assert get_image(1, 803) == "weather_4_big"


def test_get_image_rain_small():
    assert get_image(0, 501) == "weather_8_small"


def test_get_image_unknown_code_fallback():
    assert get_image(0, 999) == "weather_1_small"


# --- _pick_slots ---

def _make_items(n, base_offset_hours=1):
    """Create n forecast items starting base_offset_hours from now."""
    now = datetime.now()
    items = []
    for i in range(n):
        dt = now + timedelta(hours=base_offset_hours + i * 3)
        items.append({"dt": int(dt.timestamp()), "main": {}, "weather": [{"id": 800}]})
    return items


def test_pick_slots_returns_up_to_8(store):
    items = _make_items(20)
    result = _pick_slots(items)
    assert len(result) <= 8


def test_pick_slots_near_term_first_4(store):
    now = datetime.now()
    items = []
    # 4 near-future items (next 12 hours)
    for i in range(4):
        dt = now + timedelta(hours=i + 1)
        items.append({"dt": int(dt.timestamp()), "main": {}, "weather": [{"id": 800}]})
    # Fill up to 40 items in the future (daily forecast slots)
    for i in range(4, 40):
        dt = now + timedelta(hours=i + 1)
        items.append({"dt": int(dt.timestamp()), "main": {}, "weather": [{"id": 800}]})
    result = _pick_slots(items)
    # First 4 slots should be the immediately-upcoming ones
    for i, slot in enumerate(result[:4]):
        expected_dt = now + timedelta(hours=i + 1)
        assert abs(slot["dt"] - int(expected_dt.timestamp())) < 60


# --- save/load roundtrip ---

def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "weather.json"
    s1 = WeatherStore(path)
    s1.forecast[:] = [
        {
            "status": 800,
            "temp": 20.5,
            "temp_max": 22.0,
            "temp_min": 18.0,
            "sunrise": "",
            "sunset": "",
            "day": "Monday",
            "id": 0,
        }
    ]
    s1.save()

    s2 = WeatherStore(path)
    s2.load()
    assert len(s2.forecast) == 1
    assert s2.forecast[0]["temp"] == 20.5
    assert s2.forecast[0]["day"] == "Monday"


def test_load_missing_file_is_noop(store):
    store.load()
    assert store.forecast == []
