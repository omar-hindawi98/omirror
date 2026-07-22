import functools
import logging
import threading
from datetime import datetime

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service

from omirror import config, updater
from omirror.bluetooth.adapters import (
    BLUEZ_SERVICE_NAME,
    DBUS_OM_IFACE,
    DBUS_PROP_IFACE,
    GATT_CHRC_IFACE,
    GATT_DESC_IFACE,
    GATT_MANAGER_IFACE,
    GATT_SERVICE_IFACE,
    find_adapter,
)
from omirror.bluetooth.exceptions import InvalidArgsException, NotSupportedException
from omirror.const import ACTIVITY_DATE_FMT, BLE_SERVICE_UUID
from omirror.display import centered_text
from omirror.hardware import wifi
from omirror.i18n import setup as i18n_setup
from omirror.widgets import activities

log = logging.getLogger(__name__)


class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = "/"
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)
        self.add_service(OMirrorService(bus, 0))

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        log.debug("GetManagedObjects")
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for chrc in service.get_characteristics():
                response[chrc.get_path()] = chrc.get_properties()
                for desc in chrc.get_descriptors():
                    response[desc.get_path()] = desc.get_properties()
        return response


class Service(dbus.service.Object):
    PATH_BASE = "/org/bluez/example/service"

    def __init__(self, bus, index, uuid, primary):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                "UUID": self.uuid,
                "Primary": self.primary,
                "Characteristics": dbus.Array(self.get_characteristic_paths(), signature="o"),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristic_paths(self):
        return [chrc.get_path() for chrc in self.characteristics]

    def get_characteristics(self):
        return self.characteristics

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_SERVICE_IFACE]


class Characteristic(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + "/char" + str(index)
        self.bus = bus
        self.uuid = uuid
        self.service = service
        self.flags = flags
        self.descriptors = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                "Service": self.service.get_path(),
                "UUID": self.uuid,
                "Flags": self.flags,
                "Descriptors": dbus.Array(self.get_descriptor_paths(), signature="o"),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_descriptor(self, descriptor):
        self.descriptors.append(descriptor)

    def get_descriptor_paths(self):
        return [desc.get_path() for desc in self.descriptors]

    def get_descriptors(self):
        return self.descriptors

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        log.debug("Default ReadValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        log.debug("Default WriteValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        log.debug("Default StartNotify called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        log.debug("Default StopNotify called, returning error")
        raise NotSupportedException()

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class Descriptor(dbus.service.Object):
    def __init__(self, bus, index, uuid, flags, characteristic):
        self.path = characteristic.path + "/desc" + str(index)
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.chrc = characteristic
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_DESC_IFACE: {
                "Characteristic": self.chrc.get_path(),
                "UUID": self.uuid,
                "Flags": self.flags,
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_DESC_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[GATT_DESC_IFACE]

    @dbus.service.method(GATT_DESC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        log.debug("Default ReadValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_DESC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        log.debug("Default WriteValue called, returning error")
        raise NotSupportedException()


class OMirrorService(Service):
    def __init__(self, bus, index):
        Service.__init__(self, bus, index, BLE_SERVICE_UUID, True)
        self.add_characteristic(ShowChar(bus, 0, self))
        self.add_characteristic(PotaDelayChar(bus, 1, self))
        self.add_characteristic(QuoteDelayChar(bus, 2, self))
        self.add_characteristic(NameChar(bus, 3, self))
        self.add_characteristic(AutosleepChar(bus, 4, self))
        self.add_characteristic(AutosleepTimerChar(bus, 5, self))
        self.add_characteristic(CityChar(bus, 6, self))
        self.add_characteristic(RGBModeChar(bus, 7, self))
        self.add_characteristic(RGBSingleChar(bus, 8, self))
        self.add_characteristic(RGBFlashSeqChar(bus, 9, self))
        self.add_characteristic(RGBFlashDelayChar(bus, 10, self))
        self.add_characteristic(RGBFadeDelayChar(bus, 11, self))
        self.add_characteristic(WifiScanChar(bus, 12, self))
        self.add_characteristic(WifiConnectChar(bus, 13, self))
        self.add_characteristic(AktGetData(bus, 14, self))
        self.add_characteristic(AktSetData(bus, 15, self))
        self.add_characteristic(AktDeleteData(bus, 16, self))
        self.add_characteristic(CentralGetData(bus, 17, self))
        self.add_characteristic(CentralDeleteData(bus, 19, self))
        self.add_characteristic(UpdateApp(bus, 20, self))
        self.add_characteristic(LanguageChar(bus, 21, self))
        self.add_characteristic(DeviceNameChar(bus, 22, self))
        self.add_characteristic(WeatherApiChar(bus, 23, self))
        self.add_characteristic(WeatherCountryChar(bus, 24, self))
        self.add_characteristic(NewsRssChar(bus, 25, self))
        self.add_characteristic(NewsMaxChar(bus, 26, self))


class ShowChar(Characteristic):
    CHRC_UUID = "2844"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write"], service)
        self.value = []

    def WriteValue(self, value, options):
        self.value = value
        config.set("pota_quote_show", int(self.value[0]))


class PotaDelayChar(Characteristic):
    CHRC_UUID = "2845"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        return [dbus.Byte(int(config.get("pota_delay", 8)))]

    def WriteValue(self, value, options):
        self.value = value
        config.set("pota_delay", int(self.value[0]))


class QuoteDelayChar(Characteristic):
    CHRC_UUID = "2846"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        return [dbus.Byte(int(config.get("quote_delay", 15)))]

    def WriteValue(self, value, options):
        self.value = value
        config.set("quote_delay", int(self.value[0]))


_MAX_NAME_LEN = 64
_MAX_CITY_LEN = 64
_MAX_COUNTRY_LEN = 2
_MAX_API_KEY_LEN = 64
_MAX_RSS_URL_LEN = 256


class NameChar(Characteristic):
    CHRC_UUID = "2847"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        return [dbus.Byte(ord(c)) for c in config.get("name", "")]

    def WriteValue(self, value, options):
        self.value = value
        chars = [chr(byte) for byte in self.value if isinstance(byte, dbus.Byte)]
        name = "".join(chars)[:_MAX_NAME_LEN]
        config.set("name", name)


class AutosleepChar(Characteristic):
    CHRC_UUID = "2848"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        return [dbus.Byte(int(config.get("autosleep", 0)))]

    def WriteValue(self, value, options):
        self.value = value
        config.set("autosleep", int(self.value[0]))


class AutosleepTimerChar(Characteristic):
    CHRC_UUID = "2849"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        string = config.get("autosleep_time", "22:00,07:00").split(",")
        time1 = string[0].split(":")
        time2 = string[1].split(":")
        return [
            dbus.Byte(int(time1[0])),
            dbus.Byte(int(time1[1])),
            dbus.Byte(int(time2[0])),
            dbus.Byte(int(time2[1])),
        ]

    def WriteValue(self, value, options):
        self.value = value
        if len(self.value) < 4:
            log.warning("AutosleepTimer: expected 4 bytes, got %d", len(self.value))
            return
        h1, m1, h2, m2 = (int(b) for b in self.value[:4])
        if not (0 <= h1 <= 23 and 0 <= m1 <= 59 and 0 <= h2 <= 23 and 0 <= m2 <= 59):
            log.warning("AutosleepTimer: out-of-range values %d:%d, %d:%d", h1, m1, h2, m2)
            return
        config.set("autosleep_time", f"{h1}:{m1},{h2}:{m2}")


class CityChar(Characteristic):
    CHRC_UUID = "2850"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        return [dbus.Byte(ord(c)) for c in config.get("weather_city", "")]

    def WriteValue(self, value, options):
        self.value = value
        chars = [chr(byte) for byte in self.value if isinstance(byte, dbus.Byte)]
        config.set("weather_city", "".join(chars)[:_MAX_CITY_LEN])


class RGBModeChar(Characteristic):
    CHRC_UUID = "2851"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        return [dbus.Byte(int(config.get("rgb_mode", 0)))]

    def WriteValue(self, value, options):
        self.value = value
        config.set("rgb_mode", int(self.value[0]))


class RGBSingleChar(Characteristic):
    CHRC_UUID = "2852"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        parts = config.get("rgb_single", "255,255,255").split(",")
        return [dbus.Byte(int(parts[0])), dbus.Byte(int(parts[1])), dbus.Byte(int(parts[2]))]

    def WriteValue(self, value, options):
        self.value = value
        if len(self.value) < 3:
            log.warning("RGBSingle: expected 3 bytes, got %d", len(self.value))
            return
        r, g, b = (int(v) for v in self.value[:3])
        if not all(0 <= c <= 255 for c in (r, g, b)):
            log.warning("RGBSingle: channel value out of range (%d, %d, %d)", r, g, b)
            return
        config.set("rgb_single", f"{r},{g},{b}")


class RGBFlashSeqChar(Characteristic):
    CHRC_UUID = "2853"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        databyte = []
        for s in config.get("rgb_flash_sequence", "255,255,255").split(":"):
            parts = s.split(",")
            databyte += [
                dbus.Byte(int(parts[0])),
                dbus.Byte(int(parts[1])),
                dbus.Byte(int(parts[2])),
            ]
        return databyte

    def WriteValue(self, value, options):
        self.value = value
        parts = []
        buf = []
        for byte in self.value:
            if isinstance(byte, dbus.Byte):
                buf.append(str(int(byte)))
                if len(buf) == 3:
                    parts.append(",".join(buf))
                    buf = []
        config.set("rgb_flash_sequence", ":".join(parts))


class RGBFlashDelayChar(Characteristic):
    CHRC_UUID = "2854"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        """Return flash_delay as two bytes (high, low) — value exceeds 255 ms."""
        value = int(config.get("rgb_flash_delay", 500))
        return [dbus.Byte((value >> 8) & 0xFF), dbus.Byte(value & 0xFF)]

    def WriteValue(self, value, options):
        self.value = value
        if len(self.value) < 2:
            log.warning("RGBFlashDelay: expected 2 bytes, got %d", len(self.value))
            return
        combined = (int(self.value[0]) << 8) | int(self.value[1])
        config.set("rgb_flash_delay", combined)


class RGBFadeDelayChar(Characteristic):
    CHRC_UUID = "2855"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self.value = []

    def ReadValue(self, options):
        return [dbus.Byte(int(config.get("rgb_fade_delay", 5)))]

    def WriteValue(self, value, options):
        self.value = value
        config.set("rgb_fade_delay", int(self.value[0]))


class WifiScanChar(Characteristic):
    """Stream visible SSIDs to the client via notifications.

    The client writes any byte to trigger a scan. SSIDs are streamed back
    using the same packet protocol as AktGetData:
      - type 1: first packet, contains start of SSID text (up to 19 chars)
      - type 2-253: continuation chunks (up to 19 chars each)
      - type 255: end-of-stream sentinel

    Each SSID is sent as a separate sequence of packets.
    """

    CHRC_UUID = "2856"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write", "notify"], service)
        self.notifying = False

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False

    def WriteValue(self, value, options):
        """Scan for Wi-Fi networks and stream SSIDs back as notifications."""
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        self.StartNotify()
        ssids = wifi.scan()
        for ssid in ssids:
            text = ssid
            data = [dbus.Byte(1), *[dbus.Byte(ord(c)) for c in text[:19]]]
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": data}, [])
            if len(text) > 19:
                chunks = [text[19:][i : i + 19] for i in range(0, len(text[19:]), 19)]
                for idx, chunk in enumerate(chunks, start=2):
                    if idx > 253:
                        break
                    data2 = [dbus.Byte(idx), *[dbus.Byte(ord(c)) for c in chunk]]
                    self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": data2}, [])
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": [dbus.Byte(255)]}, [])
        self.StopNotify()


class WifiConnectChar(Characteristic):
    """Receive SSID + password from the client and connect to Wi-Fi.

    Uses the same multi-packet write protocol as AktSetData:
      - type 1: first packet — first byte is field selector (1=SSID, 2=password),
                remaining bytes are the start of the string
      - type 2-254: continuation chunks appended to the active field
      - type 255: commit — call wifi.connect(ssid, password) in a daemon thread
                  and send back a result byte (1=success, 0=failure)
    """

    CHRC_UUID = "2857"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write", "notify"], service)
        self.notifying = False
        self._field = 0  # 1 = writing SSID, 2 = writing password
        # Per-instance assembly buffers — safe if multiple clients write concurrently.
        self._ssid = ""
        self._password = ""

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False

    def WriteValue(self, value, options):
        if not value:
            return
        value = list(value)
        type_ = int(value.pop(0))
        chars = [chr(b) for b in value if isinstance(b, dbus.Byte)]
        text = "".join(chars)

        if type_ == 1:
            # First packet: next byte is the field selector.
            self._field = int(value[0]) if value else 0
            text = "".join([chr(b) for b in value[1:] if isinstance(b, dbus.Byte)])
            if self._field == 1:
                self._ssid = text
            elif self._field == 2:
                self._password = text
        elif type_ < 255:
            if self._field == 1:
                self._ssid += text
            elif self._field == 2:
                self._password += text
        elif type_ == 255:
            threading.Thread(target=self._run_connect, daemon=True).start()

    def _run_connect(self):
        """Connect in a background thread; BLE notification reports the result."""
        self.StartNotify()
        ok = wifi.connect(self._ssid, self._password)
        result_byte = dbus.Byte(1) if ok else dbus.Byte(0)
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": [result_byte]}, [])
        self.StopNotify()


class AktGetData(Characteristic):
    CHRC_UUID = "2858"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write", "notify"], service)
        self.value = []
        self.notifying = False

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False

    def WriteValue(self, value, options):
        """Stream all stored activities back to the client via notifications.

        Each activity is sent as one or more packets:
          - type 1: header (id, year×2, month, day, hour, minute) + first 13 chars
          - type 2-253: continuation chunks of up to 19 chars
          - type 255: end-of-stream sentinel (sent once after all activities)

        Year is split across two bytes (high, low) because it exceeds 255.
        """
        self.value = value
        self.StartNotify()
        activities.load()

        for item in activities.activities:
            date = datetime.strptime(item["date"], ACTIVITY_DATE_FMT)
            year_1 = (date.year >> 8) & 0xFF
            year_2 = date.year & 0xFF
            text = item["text"]

            data = [
                dbus.Byte(1),
                dbus.Byte(year_1),
                dbus.Byte(year_2),
                dbus.Byte(date.month),
                dbus.Byte(date.day),
                dbus.Byte(date.hour),
                dbus.Byte(date.minute),
                *[dbus.Byte(ord(c)) for c in text[:13]],
            ]
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": data}, [])

            if len(text) > 13:
                chunks = [text[13:][i : i + 19] for i in range(0, len(text[13:]), 19)]
                for idx, chunk in enumerate(chunks, start=2):
                    data2 = [dbus.Byte(idx), *[dbus.Byte(ord(c)) for c in chunk]]
                    self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": data2}, [])
                    if idx == 253:
                        break

        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": [dbus.Byte(255)]}, [])
        self.StopNotify()


class AktSetData(Characteristic):
    """Receives a new or updated activity from the BLE client.

    Uses a multi-packet protocol because BLE MTU caps each write at ~20 bytes:
      - type 1: id + date header + first text chunk  → resets the buffer
      - type 2-254: continuation text chunks          → appended to buffer
      - type 255: commit                              → saves the assembled activity
    """

    CHRC_UUID = "2859"

    # Minimum bytes in a type-1 packet: type(1) + id(1) + year×2(2) + month(1) + day(1) + hour(1) + minute(1) = 8
    _TYPE1_MIN_LEN = 8

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write"], service)
        # Per-instance assembly buffers — safe across retransmissions and reconnects.
        self._akt_id = 0
        self._akt_date = None
        self._akt_string = ""

    def WriteValue(self, value, options):
        value = list(value)
        if not value:
            return

        type_ = int(value.pop(0))
        if type_ == 1:
            if len(value) < self._TYPE1_MIN_LEN - 1:  # -1 because type byte was already popped
                log.warning("AktSetData: type-1 packet too short (%d bytes), dropping", len(value))
                return
            self._akt_id = int(value.pop(0))
            year_1 = int(value.pop(0))
            year_2 = int(value.pop(0))
            year = (year_1 << 8) | year_2
            month = int(value.pop(0))
            day = int(value.pop(0))
            hour = int(value.pop(0))
            minute = int(value.pop(0))
            try:
                self._akt_date = datetime(year, month, day, hour, minute)
            except ValueError:
                log.warning(
                    "AktSetData: invalid date %04d-%02d-%02d %02d:%02d, dropping packet",
                    year,
                    month,
                    day,
                    hour,
                    minute,
                )
                self._akt_date = None
                return
            self._akt_string = "".join(chr(b) for b in value if isinstance(b, dbus.Byte))
        elif type_ < 255:
            self._akt_string += "".join(chr(b) for b in value if isinstance(b, dbus.Byte))
        elif type_ == 255:
            if self._akt_date is None:
                log.warning("AktSetData: commit received but no valid date buffered, ignoring")
                return
            activities.add(self._akt_id, self._akt_date, self._akt_string)


class AktDeleteData(Characteristic):
    CHRC_UUID = "2860"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write"], service)
        self.value = []

    def WriteValue(self, value, options):
        self.value = value
        activities.remove(int(self.value[0]))


class CentralGetData(Characteristic):
    CHRC_UUID = "2861"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write", "notify"], service)
        self.value = []
        self.notifying = False

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False

    def WriteValue(self, value, options):
        self.value = value
        self.StartNotify()
        centered_text.load()

        for item in centered_text.entries:
            ts_h, ts_m = item["time_start"].split(":")
            te_h, te_m = item["time_end"].split(":")
            text = item["text"]

            data = [
                dbus.Byte(1),
                dbus.Byte(int(ts_h)),
                dbus.Byte(int(ts_m)),
                dbus.Byte(int(te_h)),
                dbus.Byte(int(te_m)),
                *[dbus.Byte(ord(c)) for c in text[:15]],
            ]
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": data}, [])

            if len(text) > 15:
                chunks = [text[15:][i : i + 19] for i in range(0, len(text[15:]), 19)]
                for idx, chunk in enumerate(chunks, start=2):
                    data2 = [dbus.Byte(idx), *[dbus.Byte(ord(c)) for c in chunk]]
                    self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": data2}, [])
                    if idx == 253:
                        break

        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": [dbus.Byte(255)]}, [])
        self.StopNotify()


class CentralDeleteData(Characteristic):
    CHRC_UUID = "2863"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write"], service)
        self.value = []

    def WriteValue(self, value, options):
        self.value = value
        centered_text.remove(int(self.value[0]))


class UpdateApp(Characteristic):
    CHRC_UUID = "2864"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["write"], service)
        self.value = []

    def WriteValue(self, value, options):
        """Trigger an OTA update in a background thread.

        The install takes 30-120 seconds, so it runs in a daemon thread to
        avoid blocking the dbus/GLib event loop.
        """
        self.value = value
        threading.Thread(target=self._run_update, daemon=True).start()

    def _run_update(self):
        result = updater.update()
        log.info(
            "Update result: %s (current=%s, latest=%s)",
            result.status.name,
            result.current_version,
            result.latest_version,
        )
        if result.error:
            log.error("Update error: %s", result.error)


class LanguageChar(Characteristic):
    """Read or set the display language (e.g. 'en', 'sv').

    The value is a UTF-8 string written/read as individual char bytes.
    Writing a new language code updates config and reloads the translation
    catalogue immediately — no restart needed.
    """

    CHRC_UUID = "2865"
    _SUPPORTED = {"en", "sv"}

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)

    def ReadValue(self, options):
        lang = config.get("language", "en")
        return [dbus.Byte(ord(c)) for c in lang]

    def WriteValue(self, value, options):
        lang = "".join(chr(b) for b in value if isinstance(b, dbus.Byte)).strip().lower()
        if lang not in self._SUPPORTED:
            log.warning(
                "LanguageChar: unsupported language %r (supported: %s)", lang, self._SUPPORTED
            )
            return
        config.set("language", lang)
        i18n_setup(lang)
        log.info("Language changed to %r", lang)


class DeviceNameChar(Characteristic):
    """Read or set the BLE advertised device name (e.g. 'OMirror - Kitchen').

    The name is persisted to config so it survives restarts and is broadcast
    in the BLE advertisement, letting the companion app tell multiple mirrors apart.
    Changes take effect on the next BLE server restart.
    """

    CHRC_UUID = "2866"
    _MAX_LEN = 32

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)

    def ReadValue(self, options):
        name = config.get("device_name", "OMirror")
        return [dbus.Byte(ord(c)) for c in name]

    def WriteValue(self, value, options):
        name = "".join(chr(b) for b in value if isinstance(b, dbus.Byte)).strip()
        if not name:
            log.warning("DeviceNameChar: received empty name, ignoring")
            return
        config.set("device_name", name[: self._MAX_LEN])
        log.info("Device name changed to %r (restart BLE server to advertise)", name)


class WeatherApiChar(Characteristic):
    """Read or set the OpenWeatherMap API key.

    Uses the multi-packet write protocol because API keys exceed the 20-byte BLE MTU:
      - type 1: start of key
      - type 2-254: continuation
      - type 255: commit
    """

    CHRC_UUID = "2867"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self._buf = ""

    def ReadValue(self, options):
        return [dbus.Byte(ord(c)) for c in config.get("weather_api", "")]

    def WriteValue(self, value, options):
        value = list(value)
        if not value:
            return
        type_ = int(value.pop(0))
        text = "".join(chr(b) for b in value if isinstance(b, dbus.Byte))
        if type_ == 1:
            self._buf = text
        elif type_ < 255:
            self._buf += text
        elif type_ == 255:
            if not self._buf:
                log.warning("WeatherApiChar: commit with empty buffer, ignoring")
                return
            config.set("weather_api", self._buf[:_MAX_API_KEY_LEN])
            self._buf = ""


class WeatherCountryChar(Characteristic):
    """Read or set the two-letter ISO country code for weather lookups (e.g. 'GB', 'SE')."""

    CHRC_UUID = "2868"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)

    def ReadValue(self, options):
        return [dbus.Byte(ord(c)) for c in config.get("weather_country", "")]

    def WriteValue(self, value, options):
        country = "".join(chr(b) for b in value if isinstance(b, dbus.Byte)).strip().upper()
        if len(country) != _MAX_COUNTRY_LEN or not country.isalpha():
            log.warning("WeatherCountryChar: invalid country code %r, ignoring", country)
            return
        config.set("weather_country", country)


class NewsRssChar(Characteristic):
    """Read or set the RSS feed URL.

    Uses the multi-packet write protocol because URLs routinely exceed 20 bytes:
      - type 1: start of URL
      - type 2-254: continuation
      - type 255: commit
    """

    CHRC_UUID = "2869"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)
        self._buf = ""

    def ReadValue(self, options):
        return [dbus.Byte(ord(c)) for c in config.get("news_rss", "")]

    def WriteValue(self, value, options):
        value = list(value)
        if not value:
            return
        type_ = int(value.pop(0))
        text = "".join(chr(b) for b in value if isinstance(b, dbus.Byte))
        if type_ == 1:
            self._buf = text
        elif type_ < 255:
            self._buf += text
        elif type_ == 255:
            if not self._buf:
                log.warning("NewsRssChar: commit with empty buffer, ignoring")
                return
            config.set("news_rss", self._buf[:_MAX_RSS_URL_LEN])
            self._buf = ""


class NewsMaxChar(Characteristic):
    """Read or set the maximum number of news items to display."""

    CHRC_UUID = "2870"

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.CHRC_UUID, ["read", "write"], service)

    def ReadValue(self, options):
        return [dbus.Byte(int(config.get("news_max", 5)))]

    def WriteValue(self, value, options):
        if not value:
            return
        n = int(value[0])
        if n < 1 or n > 20:
            log.warning("NewsMaxChar: value %d out of range [1, 20], ignoring", n)
            return
        config.set("news_max", n)


def register_app_cb():
    log.info("GATT application registered")


def register_app_error_cb(mainloop, error):
    log.error("Failed to register application: %s", error)
    mainloop.quit()


def gatt_server_main(mainloop, bus, adapter_name):
    config.load()

    adapter = find_adapter(bus, GATT_MANAGER_IFACE, adapter_name)
    if not adapter:
        raise Exception("GattManager1 interface not found")

    service_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter), GATT_MANAGER_IFACE
    )

    app = Application(bus)
    log.info("Registering GATT application...")
    service_manager.RegisterApplication(
        app.get_path(),
        {},
        reply_handler=register_app_cb,
        error_handler=functools.partial(register_app_error_cb, mainloop),
    )
