import argparse
import logging

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
import lgpio

try:
    from gi.repository import GObject
except ImportError:
    import gobject as GObject

from omirror.bluetooth import advertising, gatt

log = logging.getLogger(__name__)

GPIO_BLUETOOTH = 26
_chip = None


def main():
    global _chip
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    _chip = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_output(_chip, GPIO_BLUETOOTH)

    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--adapter-name", type=str, default="")
    args = parser.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    mainloop = GObject.MainLoop()

    advertising.advertising_main(mainloop, bus, args.adapter_name)
    gatt.gatt_server_main(mainloop, bus, args.adapter_name)

    lgpio.gpio_write(_chip, GPIO_BLUETOOTH, 1)
    try:
        mainloop.run()
    finally:
        lgpio.gpio_write(_chip, GPIO_BLUETOOTH, 0)
        lgpio.gpiochip_close(_chip)


if __name__ == "__main__":
    main()
