import functools
import logging

import dbus
import dbus.service

from omirror import config
from omirror.bluetooth.adapters import (
    BLUEZ_SERVICE_NAME,
    DBUS_PROP_IFACE,
    LE_ADVERTISEMENT_IFACE,
    LE_ADVERTISING_MANAGER_IFACE,
    find_adapter,
)
from omirror.bluetooth.exceptions import InvalidArgsException
from omirror.const import BLE_SERVICE_UUID

log = logging.getLogger(__name__)


class Advertisement(dbus.service.Object):
    PATH_BASE = "/org/bluez/example/advertisement"

    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = None
        self.manufacturer_data = None
        self.solicit_uuids = None
        self.service_data = None
        self.include_tx_power = None
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = {}
        properties["Type"] = self.ad_type
        if self.service_uuids is not None:
            properties["ServiceUUIDs"] = dbus.Array(self.service_uuids, signature="s")
        if self.solicit_uuids is not None:
            properties["SolicitUUIDs"] = dbus.Array(self.solicit_uuids, signature="s")
        if self.manufacturer_data is not None:
            properties["ManufacturerData"] = dbus.Dictionary(self.manufacturer_data, signature="qv")
        if self.service_data is not None:
            properties["ServiceData"] = dbus.Dictionary(self.service_data, signature="sv")
        if self.include_tx_power is not None:
            properties["IncludeTxPower"] = dbus.Boolean(self.include_tx_power)
        if getattr(self, "local_name", None):
            properties["LocalName"] = dbus.String(self.local_name)
        return {LE_ADVERTISEMENT_IFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service_uuid(self, uuid):
        if not self.service_uuids:
            self.service_uuids = []
        self.service_uuids.append(uuid)

    def add_solicit_uuid(self, uuid):
        if not self.solicit_uuids:
            self.solicit_uuids = []
        self.solicit_uuids.append(uuid)

    def add_manufacturer_data(self, manuf_code, data):
        if not self.manufacturer_data:
            self.manufacturer_data = dbus.Dictionary({}, signature="qv")
        self.manufacturer_data[manuf_code] = dbus.Array(data, signature="y")

    def add_service_data(self, uuid, data):
        if not self.service_data:
            self.service_data = dbus.Dictionary({}, signature="sv")
        self.service_data[uuid] = dbus.Array(data, signature="y")

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT_IFACE:
            raise InvalidArgsException()
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        log.debug("%s: Released", self.path)


class MirrorAdvertisement(Advertisement):
    def __init__(self, bus, index):
        Advertisement.__init__(self, bus, index, "peripheral")
        self.add_service_uuid(BLE_SERVICE_UUID)
        # Use the configured device_name so multiple mirrors are distinguishable
        # in the companion app's scan list. Falls back to "OMirror".
        device_name = config.get("device_name", "OMirror")
        self.local_name = device_name


def register_ad_cb():
    log.info("Advertisement registered")


def register_ad_error_cb(mainloop, error):
    log.error("Failed to register advertisement: %s", error)
    mainloop.quit()


def advertising_main(mainloop, bus, adapter_name):
    adapter = find_adapter(bus, LE_ADVERTISING_MANAGER_IFACE, adapter_name)
    if not adapter:
        raise Exception("LEAdvertisingManager1 interface not found")

    adapter_props = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter), "org.freedesktop.DBus.Properties"
    )
    adapter_props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))

    ad_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter), LE_ADVERTISING_MANAGER_IFACE
    )

    advertisement = MirrorAdvertisement(bus, 0)
    ad_manager.RegisterAdvertisement(
        advertisement.get_path(),
        {},
        reply_handler=register_ad_cb,
        error_handler=functools.partial(register_ad_error_cb, mainloop),
    )
