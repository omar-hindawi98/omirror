"""Tests for the BLE multi-packet protocol logic in gatt.py characteristics.

dbus is a Pi-only dependency, so the entire dbus namespace is mocked before
any omirror.bluetooth.gatt import occurs. The test instances are minimal stubs
that exercise only the protocol assembly/validation logic.
"""

import datetime
import sys
import types
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Mock the dbus module tree before gatt.py is imported
# ---------------------------------------------------------------------------

def _make_dbus_mock():
    dbus = types.ModuleType("dbus")

    class Byte(int):
        pass

    dbus.Byte = Byte
    dbus.String = str
    dbus.Boolean = bool
    dbus.Array = list
    dbus.Dictionary = dict
    dbus.ObjectPath = str
    dbus.Interface = MagicMock()

    service_mod = types.ModuleType("dbus.service")
    service_mod.Object = object

    def method(*a, **kw):
        def decorator(fn):
            return fn
        return decorator

    def signal(*a, **kw):
        def decorator(fn):
            return fn
        return decorator

    service_mod.method = method
    service_mod.signal = signal

    exceptions_mod = types.ModuleType("dbus.exceptions")
    exceptions_mod.DBusException = Exception
    # Must be accessible as both dbus.exceptions.X and via sys.modules
    dbus.exceptions = exceptions_mod
    dbus.service = service_mod

    mainloop_mod = types.ModuleType("dbus.mainloop")
    glib_mod = types.ModuleType("dbus.mainloop.glib")
    glib_mod.DBusGMainLoop = MagicMock()

    sys.modules["dbus"] = dbus
    sys.modules["dbus.service"] = service_mod
    sys.modules["dbus.exceptions"] = exceptions_mod
    sys.modules["dbus.mainloop"] = mainloop_mod
    sys.modules["dbus.mainloop.glib"] = glib_mod
    return dbus


dbus = _make_dbus_mock()

# Also stub out Pi-only hardware deps that gatt.py's imports pull in
for _mod in ("lgpio", "pigpio"):
    sys.modules[_mod] = MagicMock()

# Stub omirror.updater so gatt.py doesn't fail on import
sys.modules.setdefault("omirror.updater", MagicMock())

import omirror.bluetooth.gatt as gatt  # noqa: E402 — must come after mocks


# ---------------------------------------------------------------------------
# Minimal bus / service stubs for constructing characteristics
# ---------------------------------------------------------------------------

class _FakeBus:
    def add_signal_receiver(self, *a, **kw):
        pass

    def get_object(self, *a, **kw):
        return MagicMock()


class _FakeService:
    path = "/org/bluez/example/service0"

    def get_path(self):
        return self.path


_bus = _FakeBus()
_svc = _FakeService()


def _bytes(*ints):
    """Convenience: list of dbus.Byte values."""
    return [dbus.Byte(i) for i in ints]


# ---------------------------------------------------------------------------
# AktSetData protocol tests
# ---------------------------------------------------------------------------

class TestAktSetData:
    def _char(self):
        c = gatt.AktSetData.__new__(gatt.AktSetData)
        c._akt_id = 0
        c._akt_date = None
        c._akt_string = ""
        return c

    def _type1_packet(self, id_=1, year=2026, month=7, day=22, hour=10, minute=30, text=""):
        return _bytes(
            1,                          # type
            id_,                        # id
            (year >> 8) & 0xFF,         # year high
            year & 0xFF,                # year low
            month, day, hour, minute,   # date parts
            *[ord(c) for c in text],
        )

    def test_type1_sets_buffer(self):
        c = self._char()
        c.WriteValue(self._type1_packet(id_=5, year=2026, month=7, day=22, hour=9, minute=0, text="Hi"), {})
        assert c._akt_id == 5
        assert c._akt_date == datetime.datetime(2026, 7, 22, 9, 0)
        assert c._akt_string == "Hi"

    def test_type2_appends_text(self):
        c = self._char()
        c.WriteValue(self._type1_packet(text="Hello"), {})
        c.WriteValue(_bytes(2, *[ord(ch) for ch in " world"]), {})
        assert c._akt_string == "Hello world"

    def test_type255_commit_calls_activities_add(self):
        c = self._char()
        c.WriteValue(self._type1_packet(id_=3, year=2026, month=8, day=1, hour=12, minute=0, text="Task"), {})
        with patch("omirror.bluetooth.gatt.activities") as mock_activities:
            c.WriteValue(_bytes(255), {})
            mock_activities.add.assert_called_once_with(
                3, datetime.datetime(2026, 8, 1, 12, 0), "Task"
            )

    def test_type255_without_prior_type1_is_ignored(self):
        c = self._char()
        with patch("omirror.bluetooth.gatt.activities") as mock_activities:
            c.WriteValue(_bytes(255), {})
            mock_activities.add.assert_not_called()

    def test_empty_packet_is_ignored(self):
        c = self._char()
        c.WriteValue([], {})  # should not raise
        assert c._akt_date is None

    def test_type1_too_short_is_rejected(self):
        # Only 3 bytes after the type byte — minimum is 7
        c = self._char()
        c.WriteValue(_bytes(1, 1, 0), {})
        assert c._akt_date is None

    def test_invalid_date_is_rejected(self):
        # month=13 is invalid
        c = self._char()
        c.WriteValue(self._type1_packet(month=13), {})
        assert c._akt_date is None

    def test_commit_after_bad_date_is_ignored(self):
        c = self._char()
        c.WriteValue(self._type1_packet(month=13), {})
        with patch("omirror.bluetooth.gatt.activities") as mock_activities:
            c.WriteValue(_bytes(255), {})
            mock_activities.add.assert_not_called()

    def test_second_type1_resets_buffer(self):
        c = self._char()
        c.WriteValue(self._type1_packet(id_=1, text="Old"), {})
        c.WriteValue(self._type1_packet(id_=2, year=2027, month=1, day=1, hour=0, minute=0, text="New"), {})
        assert c._akt_id == 2
        assert c._akt_string == "New"
        assert c._akt_date.year == 2027


# ---------------------------------------------------------------------------
# WifiConnectChar protocol tests
# ---------------------------------------------------------------------------

class TestWifiConnectChar:
    def _char(self):
        c = gatt.WifiConnectChar.__new__(gatt.WifiConnectChar)
        c.notifying = False
        c._field = 0
        c._ssid = ""
        c._password = ""
        return c

    def test_type1_field1_sets_ssid(self):
        c = self._char()
        c.WriteValue(_bytes(1, 1, *[ord(ch) for ch in "MyNet"]), {})
        assert c._ssid == "MyNet"
        assert c._field == 1

    def test_type1_field2_sets_password(self):
        c = self._char()
        c.WriteValue(_bytes(1, 2, *[ord(ch) for ch in "secret"]), {})
        assert c._password == "secret"
        assert c._field == 2

    def test_continuation_appends_to_active_field(self):
        c = self._char()
        c.WriteValue(_bytes(1, 1, *[ord(ch) for ch in "Net"]), {})
        c.WriteValue(_bytes(2, *[ord(ch) for ch in "work"]), {})
        assert c._ssid == "Network"

    def test_continuation_appends_to_password_field(self):
        c = self._char()
        c.WriteValue(_bytes(1, 2, *[ord(ch) for ch in "pass"]), {})
        c.WriteValue(_bytes(2, *[ord(ch) for ch in "word"]), {})
        assert c._password == "password"

    def test_empty_packet_is_ignored(self):
        c = self._char()
        c.WriteValue([], {})  # should not raise
        assert c._ssid == ""

    def test_type255_spawns_connect_thread(self):
        c = self._char()
        c._ssid = "MyNet"
        c._password = "secret"
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            c.WriteValue(_bytes(255), {})
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()

    def test_second_type1_resets_ssid(self):
        c = self._char()
        c.WriteValue(_bytes(1, 1, *[ord(ch) for ch in "OldNet"]), {})
        c.WriteValue(_bytes(1, 1, *[ord(ch) for ch in "NewNet"]), {})
        assert c._ssid == "NewNet"


# ---------------------------------------------------------------------------
# RGBFlashDelayChar WriteValue guard
# ---------------------------------------------------------------------------

class TestRGBFlashDelayChar:
    def _char(self):
        c = gatt.RGBFlashDelayChar.__new__(gatt.RGBFlashDelayChar)
        c.value = []
        return c

    def test_two_bytes_sets_config(self):
        c = self._char()
        with patch("omirror.bluetooth.gatt.config") as mock_config:
            # 500 ms = 0x01F4 → high=1, low=244
            c.WriteValue(_bytes(1, 244), {})
            mock_config.set.assert_called_once_with("rgb_flash_delay", 500)

    def test_one_byte_is_rejected(self):
        c = self._char()
        with patch("omirror.bluetooth.gatt.config") as mock_config:
            c.WriteValue(_bytes(1), {})
            mock_config.set.assert_not_called()

    def test_zero_bytes_is_rejected(self):
        c = self._char()
        with patch("omirror.bluetooth.gatt.config") as mock_config:
            c.WriteValue([], {})
            mock_config.set.assert_not_called()
