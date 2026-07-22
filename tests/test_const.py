from datetime import datetime

import pytest

from omirror.const import in_time_window


def _t(hour, minute):
    return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)


# --- same-day windows ---

def test_same_day_inside():
    assert in_time_window(_t(10, 30), [9, 0], [11, 0]) is True


def test_same_day_before_start():
    assert in_time_window(_t(8, 59), [9, 0], [11, 0]) is False


def test_same_day_after_end():
    assert in_time_window(_t(11, 1), [9, 0], [11, 0]) is False


def test_same_day_at_exact_start():
    assert in_time_window(_t(9, 0), [9, 0], [11, 0]) is True


def test_same_day_at_exact_end():
    assert in_time_window(_t(11, 0), [9, 0], [11, 0]) is True


# --- overnight windows (t1 > t2) ---

def test_overnight_evening_inside():
    assert in_time_window(_t(23, 0), [22, 0], [7, 0]) is True


def test_overnight_midnight():
    assert in_time_window(_t(0, 30), [22, 0], [7, 0]) is True


def test_overnight_morning_inside():
    assert in_time_window(_t(6, 0), [22, 0], [7, 0]) is True


def test_overnight_midday_outside():
    assert in_time_window(_t(12, 0), [22, 0], [7, 0]) is False


def test_overnight_at_exact_start():
    assert in_time_window(_t(22, 0), [22, 0], [7, 0]) is True


def test_overnight_at_exact_end():
    assert in_time_window(_t(7, 0), [22, 0], [7, 0]) is True


def test_overnight_just_before_start():
    assert in_time_window(_t(21, 59), [22, 0], [7, 0]) is False


def test_overnight_just_after_end():
    assert in_time_window(_t(7, 1), [22, 0], [7, 0]) is False


# --- edge: same hour different minute ---

def test_same_hour_boundary():
    # t1=[22,30] to t2=[22,0] is overnight; 22:15 is outside
    assert in_time_window(_t(22, 15), [22, 30], [22, 0]) is False


def test_same_hour_inside_overnight():
    # t1=[22,30] to t2=[22,0]; 22:45 is inside
    assert in_time_window(_t(22, 45), [22, 30], [22, 0]) is True
