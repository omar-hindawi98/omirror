import logging
import subprocess
import threading
import time

import lgpio
import pigpio

log = logging.getLogger(__name__)

# Broadcom pin numbers
GPIO_R = 17
GPIO_G = 27
GPIO_B = 22

GPIO_BUTTON = 18
GPIO_BUTTON_2 = 23

GPIO_WIFI_R = 5
GPIO_WIFI_G = 6
GPIO_WIFI_B = 13


class _RGB_Cycle(threading.Thread):
    """Smoothly rotates the LED hue through R → G → B → R.

    Three passes of 255 steps each: each pass decrements one channel and
    increments the next, producing a continuous colour wheel animation.
    """

    def __init__(self, ctrl: "RGBController") -> None:
        super().__init__(daemon=True)
        self._ctrl = ctrl

    def run(self) -> None:
        c = self._ctrl
        start = [255, 0, 0]
        c._cycle_active = True
        for dec in range(3):
            if not c._rgb_active or not c._cycle_active:
                break
            inc = (dec + 1) % 3
            for _ in range(255):
                if not c._rgb_active or not c._cycle_active:
                    break
                start[dec] -= 1
                start[inc] += 1
                c.set_lights(GPIO_R, start[0])
                c.set_lights(GPIO_G, start[1])
                c.set_lights(GPIO_B, start[2])
                time.sleep(0.02 + c.fade_delay / 1000)
        c._cycle_active = False


class _RGB_Flash(threading.Thread):
    def __init__(self, ctrl: "RGBController") -> None:
        super().__init__(daemon=True)
        self._ctrl = ctrl

    def run(self) -> None:
        c = self._ctrl
        c._flash_active = True
        while c._rgb_active and c._flash_active:
            for colour in c.flash_sequence:
                if not c._rgb_active or not c._flash_active:
                    break
                c.set_lights(GPIO_R, colour[0])
                c.set_lights(GPIO_G, colour[1])
                c.set_lights(GPIO_B, colour[2])
                time.sleep(c.flash_delay / 1000)
        c._flash_active = False


class RGBController:
    def __init__(self) -> None:
        self.pi = None
        self._chip = None
        self.bright = 255
        # Mode 0 = One color, Mode 1 = Flash, Mode 2 = Cycle
        self.mode = 2
        self.colour = (255, 0, 0)
        self.flash_sequence = ((255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255))
        self.flash_delay = 1000
        self.fade_delay = 0
        self._rgb_active = False
        self._flash_active = False
        self._cycle_active = False
        self._thread_flash: _RGB_Flash | None = None
        self._thread_cycle: _RGB_Cycle | None = None

    def init(self) -> None:
        """Start the pigpio daemon and open the GPIO chip.

        pigpio is used for the RGB LEDs because its hardware-timed PWM produces
        flicker-free output that lgpio's software PWM cannot match.
        lgpio handles all digital I/O (buttons, WiFi LED) without needing a daemon
        and is the recommended replacement for the deprecated RPi.GPIO on modern kernels.
        """
        # CalledProcessError means pigpiod is already running, which is fine.
        try:
            subprocess.run(["sudo", "pigpiod"], check=True, timeout=5)
        except subprocess.CalledProcessError:
            pass
        except Exception:
            log.exception("Failed to start pigpiod")
        time.sleep(1)
        self.pi = pigpio.pi()

        self._chip = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_input(self._chip, GPIO_BUTTON, lgpio.SET_PULL_UP)
        lgpio.gpio_claim_input(self._chip, GPIO_BUTTON_2, lgpio.SET_PULL_DOWN)
        lgpio.gpio_claim_output(self._chip, GPIO_WIFI_R)
        lgpio.gpio_claim_output(self._chip, GPIO_WIFI_G)
        lgpio.gpio_claim_output(self._chip, GPIO_WIFI_B)

    def set_lights(self, pin: int, brightness: int) -> None:
        """Set PWM duty cycle on *pin*, scaled by the global brightness dimmer.

        All animation code passes raw 0-255 values; this function applies the
        global `bright` factor so a single setting controls overall LED intensity
        without every caller needing to know about it.
        """
        real = int(brightness * (self.bright / 255.0))
        self.pi.set_PWM_dutycycle(pin, real)

    def RGB_Single(self) -> None:
        self.set_lights(GPIO_R, self.colour[0])
        self.set_lights(GPIO_G, self.colour[1])
        self.set_lights(GPIO_B, self.colour[2])

    def RGB_off(self) -> None:
        self._rgb_active = False
        self._cycle_active = False
        self._flash_active = False
        self.set_lights(GPIO_R, 0)
        self.set_lights(GPIO_G, 0)
        self.set_lights(GPIO_B, 0)

    def RGB_on(self) -> None:
        """Activate the LEDs in the current mode (single / flash / cycle).

        Thread.start() raises RuntimeError if the thread has already been started
        and finished. When that happens and the animation is no longer active,
        a fresh thread is created so the LED restarts cleanly.
        """
        self._rgb_active = True
        if self.mode == 0:
            self._cycle_active = False
            self._flash_active = False
            self.RGB_Single()
        elif self.mode == 1:
            time.sleep(0.01)
            self._cycle_active = False
            try:
                self._thread_flash.start()
            except (RuntimeError, AttributeError):
                if not self._flash_active:
                    self._thread_flash = _RGB_Flash(self)
                    self._thread_flash.start()
        elif self.mode == 2:
            time.sleep(0.01)
            self._flash_active = False
            try:
                self._thread_cycle.start()
            except (RuntimeError, AttributeError):
                if not self._cycle_active:
                    self._thread_cycle = _RGB_Cycle(self)
                    self._thread_cycle.start()

    def button_pressed(self, pin: int) -> bool:
        return lgpio.gpio_read(self._chip, pin) == 0

    def wifi_led(self, val: int) -> None:
        if val:
            lgpio.gpio_write(self._chip, GPIO_WIFI_R, 0)
            lgpio.gpio_write(self._chip, GPIO_WIFI_G, 1)
            lgpio.gpio_write(self._chip, GPIO_WIFI_B, 0)
        else:
            lgpio.gpio_write(self._chip, GPIO_WIFI_R, 1)
            lgpio.gpio_write(self._chip, GPIO_WIFI_G, 0)
            lgpio.gpio_write(self._chip, GPIO_WIFI_B, 0)

    def cleanup(self) -> None:
        if self.pi:
            self.pi.stop()
        if self._chip is not None:
            lgpio.gpiochip_close(self._chip)


# Module-level singleton — preserves the call-site API used in app.py and gatt.py.
_ctrl = RGBController()

# app.py reads/writes these as `rgb.mode`, `rgb.colour`, etc.
# Forward attribute access for the names that callers set directly.
_FORWARDED = {"mode", "colour", "bright", "flash_sequence", "flash_delay", "fade_delay"}


def __getattr__(name: str):
    if name in _FORWARDED:
        return getattr(_ctrl, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value):  # type: ignore[override]
    if name in _FORWARDED:
        setattr(_ctrl, name, value)
    else:
        import sys

        sys.modules[__name__].__dict__[name] = value


def init() -> None:
    _ctrl.init()


def set_lights(pin: int, brightness: int) -> None:
    _ctrl.set_lights(pin, brightness)


def RGB_Single() -> None:
    _ctrl.RGB_Single()


def RGB_off() -> None:
    _ctrl.RGB_off()


def RGB_on() -> None:
    _ctrl.RGB_on()


def button_pressed(pin: int) -> bool:
    return _ctrl.button_pressed(pin)


def wifi_led(val: int) -> None:
    _ctrl.wifi_led(val)


def cleanup() -> None:
    _ctrl.cleanup()
