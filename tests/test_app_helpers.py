"""Tests for pure helper functions in app.py.

These functions have no pygame or hardware dependencies and can run on any platform.
lgpio and pigpio are Pi-only and must be stubbed before any omirror.hardware import.
"""

import datetime
import sys
from unittest.mock import MagicMock, patch

import pytest

# Stub Pi-only hardware deps before app.py is imported
for _m in ("lgpio", "pigpio"):
    sys.modules.setdefault(_m, MagicMock())

from omirror.app import _parse_news_date, _time_since, _time_until, _time_until_str  # noqa: E402
from omirror.const import ACTIVITY_DATE_FMT  # noqa: E402


# --- _parse_news_date ---

def test_parse_news_date_standard():
    s = "Mon, 22 Jul 2026 14:30:00 +0000"
    dt = _parse_news_date(s)
    assert dt == datetime.datetime(2026, 7, 22, 14, 30, 0)


def test_parse_news_date_single_digit_day():
    s = "Wed, 05 Jan 2025 09:00:00 +0000"
    dt = _parse_news_date(s)
    assert dt == datetime.datetime(2025, 1, 5, 9, 0, 0)


def test_parse_news_date_different_tz_offset():
    # Timezone offset is stripped; the time component is kept as-is
    s = "Fri, 01 Mar 2024 23:59:59 +0200"
    dt = _parse_news_date(s)
    assert dt == datetime.datetime(2024, 3, 1, 23, 59, 59)


def test_parse_news_date_invalid_raises():
    with pytest.raises(Exception):
        _parse_news_date("not a date at all")


def test_parse_news_date_missing_weekday_prefix_raises():
    with pytest.raises(Exception):
        _parse_news_date("22 Jul 2026 14:30:00 +0000")


# --- _time_until ---

def _future(seconds=0, minutes=0, hours=0, days=0, weeks=0):
    delta = datetime.timedelta(
        seconds=seconds, minutes=minutes, hours=hours, days=days, weeks=weeks
    )
    return datetime.datetime.now() + delta


def test_time_until_seconds():
    # 45s is firmly in the seconds bucket (< 60s threshold)
    result = _time_until(_future(seconds=45))
    assert result.startswith("In ") and result.endswith("s")


def test_time_until_minutes():
    # 10m of headroom; int division of ~9m58s / 60 still gives >=9
    result = _time_until(_future(minutes=10))
    assert result.startswith("In ") and result.endswith("m")


def test_time_until_hours():
    # 5h headroom; stays well within the hours bucket
    result = _time_until(_future(hours=5))
    assert result.startswith("In ") and result.endswith("h")


def test_time_until_days():
    # 4d headroom
    result = _time_until(_future(days=4))
    assert result.startswith("In ") and result.endswith("d")


def test_time_until_weeks():
    # 4w headroom
    result = _time_until(_future(weeks=4))
    assert result.startswith("In ") and result.endswith("w")


def test_time_until_months():
    # 3 months = ~90 days — well clear of the week threshold
    result = _time_until(_future(days=90))
    assert result.startswith("In ") and result.endswith("mo")


def test_time_until_years():
    result = _time_until(_future(days=400))
    assert result.startswith("In ") and result.endswith("y")


def test_time_until_now():
    # A date in the past returns "Now"
    past = datetime.datetime.now() - datetime.timedelta(seconds=5)
    assert _time_until(past) == "Now"


# --- _time_since ---

def _past_rss_str(seconds=0, minutes=0, hours=0, days=0, weeks=0):
    delta = datetime.timedelta(
        seconds=seconds, minutes=minutes, hours=hours, days=days, weeks=weeks
    )
    dt = datetime.datetime.now() - delta
    return dt.strftime("Mon, %d %b %Y %H:%M:%S +0000")


def test_time_since_seconds():
    assert _time_since(_past_rss_str(seconds=30)) == "30s ago"


def test_time_since_minutes():
    assert _time_since(_past_rss_str(minutes=10)) == "10m ago"


def test_time_since_hours():
    assert _time_since(_past_rss_str(hours=4)) == "4h ago"


def test_time_since_days():
    assert _time_since(_past_rss_str(days=3)) == "3d ago"


def test_time_since_weeks():
    assert _time_since(_past_rss_str(weeks=2)) == "2w ago"


def test_time_since_months():
    assert _time_since(_past_rss_str(days=62)) == "2mo ago"


def test_time_since_years():
    assert _time_since(_past_rss_str(days=400)) == "1y ago"


def test_time_since_just_now():
    # A future date (clock skew) returns "Just now"
    future = (datetime.datetime.now() + datetime.timedelta(seconds=5)).strftime(
        "Mon, %d %b %Y %H:%M:%S +0000"
    )
    assert _time_since(future) == "Just now"


def test_time_since_invalid_string_passthrough():
    # Unparseable date returns the original string unchanged
    assert _time_since("garbage") == "garbage"


# --- _time_until_str ---

def test_time_until_str_valid():
    future = (datetime.datetime.now() + datetime.timedelta(hours=5)).strftime(ACTIVITY_DATE_FMT)
    result = _time_until_str(future)
    assert result.startswith("In ") and result.endswith("h")


def test_time_until_str_invalid_passthrough():
    assert _time_until_str("not-a-date") == "not-a-date"
