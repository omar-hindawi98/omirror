"""Application logic: background threads, data checking, button handling, main loop."""

import contextlib
import dataclasses
import datetime
import glob
import logging
import socket
import threading
import time
from typing import Any

import pygame

from omirror import config
from omirror.const import ACTIVITY_DATE_FMT, BLACK, IMAGES_DIR, SCREEN_SIZE, in_time_window
from omirror.display import centered_text
from omirror.display.renderer import Fader
from omirror.display.widgets.activities import ActivitiesWidget
from omirror.display.widgets.datetime_widget import DateTimeWidget
from omirror.display.widgets.loading import LoadingWidget
from omirror.display.widgets.name_display import NameDisplayWidget
from omirror.display.widgets.news import NewsWidget
from omirror.display.widgets.overlay_text import OverlayTextWidget
from omirror.display.widgets.quote import QuoteWidget
from omirror.display.widgets.weather import WeatherWidget
from omirror.hardware import rgb
from omirror.i18n import _
from omirror.i18n import setup as i18n_setup
from omirror.widgets import activities, news, quotes
from omirror.widgets import weather as weather_data

log = logging.getLogger(__name__)


@dataclasses.dataclass
class AppState:
    running: bool = True
    internet: bool = False

    name: str = ""
    rotation: int = 0
    rotated: bool = False
    rotation_btn_pressed: bool = True

    autosleep_enabled: bool = False
    autoslept: bool = False
    autosleeping: bool = False

    quote_delay: int = 15
    name_delay: int = 8

    quote_timestamp: datetime.datetime | None = None
    name_timestamp: datetime.datetime | None = None

    pota_quote_show: int = 0

    # Check_data compares these to skip expensive split-and-parse when unchanged.
    _cached_rgb_single_str: str = ""
    _cached_flash_seq_str: str = ""

    # Set by _setup() after pygame is initialised.
    screen: Any = None
    fader: Any = None
    image_cache: dict = dataclasses.field(default_factory=dict)

    # Widget instances set by _setup().
    weather_widget: Any = None
    overlay_widget: Any = None
    name_widget: Any = None
    datetime_widget: Any = None
    quote_widget: Any = None
    news_widget: Any = None
    activities_widget: Any = None
    loading_widget: Any = None

    # True while BUTTON is held — used to detect the release edge.
    _btn_pressed: bool = False


# --- helpers ---


def check_connection() -> bool:
    try:
        socket.create_connection(("www.google.com", 80), timeout=3)
        return True
    except OSError:
        return False


def _time_until(date: datetime.datetime) -> str:
    delta = date - datetime.datetime.now()
    s = int(delta.total_seconds())
    m = int(s / 60)
    h = int(s / 3600)
    d = int(s / 86400)
    w = int(s / 604800)
    mo = int(s / 2592000)
    yr = int(s / 31104000)
    if yr > 0:
        return _("In {n}y").format(n=yr)
    if mo > 0:
        return _("In {n}mo").format(n=mo)
    if w > 0:
        return _("In {n}w").format(n=w)
    if d > 0:
        return _("In {n}d").format(n=d)
    if h > 0:
        return _("In {n}h").format(n=h)
    if m > 0:
        return _("In {n}m").format(n=m)
    if s > 0:
        return _("In {n}s").format(n=s)
    return _("Now")


def _time_since(date_str: str) -> str:
    try:
        date = _parse_news_date(date_str)
    except Exception:
        return date_str
    delta = datetime.datetime.now() - date
    s = int(delta.total_seconds())
    m = int(s / 60)
    h = int(s / 3600)
    d = int(s / 86400)
    w = int(s / 604800)
    mo = int(s / 2592000)
    yr = int(s / 31104000)
    if yr > 0:
        return _("{n}y ago").format(n=yr)
    if mo > 0:
        return _("{n}mo ago").format(n=mo)
    if w > 0:
        return _("{n}w ago").format(n=w)
    if d > 0:
        return _("{n}d ago").format(n=d)
    if h > 0:
        return _("{n}h ago").format(n=h)
    if m > 0:
        return _("{n}m ago").format(n=m)
    if s > 0:
        return _("{n}s ago").format(n=s)
    return _("Just now")


def _parse_news_date(string: str) -> datetime.datetime:
    """Parse RSS date string like 'Mon, 22 Jul 2026 14:30:00 +0000'."""
    date = string.split(" ", 1)[1].rsplit(" ", 1)[0]
    parts = date.split(" ")
    date_str = f"{parts[0]} {parts[1]} {parts[2]} {parts[3]}"
    return datetime.datetime.strptime(date_str, "%d %b %Y %H:%M:%S")


def _time_until_str(date_str: str) -> str:
    try:
        date = datetime.datetime.strptime(date_str, ACTIVITY_DATE_FMT)
        return _time_until(date)
    except Exception:
        return date_str


# --- image cache ---


def load_image_cache(state: AppState) -> None:
    for path in glob.glob(str(IMAGES_DIR / "*.png")):
        key = path.split("/")[-1].rsplit(".", 1)[0]
        state.image_cache[key] = pygame.image.load(path).convert()


# --- data check (runs in data thread) ---


def check_data(state: AppState) -> None:
    """Apply config values to hardware and app state.

    Called by _DataThread on every tick. RGB colour strings are compared to a
    cached copy so the expensive split-and-parse only runs when a value changes.
    """
    try:
        rgb_single_str = config.get("rgb_single", "255,255,255")
        if rgb_single_str != state._cached_rgb_single_str:
            state._cached_rgb_single_str = rgb_single_str
            cc = rgb_single_str.split(",")
            rgb.colour = (int(cc[0]), int(cc[1]), int(cc[2]))

        flash_seq_str = config.get("rgb_flash_sequence", "255,255,255")
        if flash_seq_str != state._cached_flash_seq_str:
            state._cached_flash_seq_str = flash_seq_str
            rgb.flash_sequence = [list(map(int, c.split(","))) for c in flash_seq_str.split(":")]

        rgb.flash_delay = float(config.get("rgb_flash_delay", 0.5))
        rgb.mode = int(config.get("rgb_mode", 0))
        rgb.fade_delay = int(config.get("rgb_fade_delay", 5))

        state.rotation = int(config.get("rotation", 0))

        new_city = config.get("weather_city", "")
        new_country = config.get("weather_country", "SE")
        if weather_data.city != new_city or weather_data.country != new_country:
            weather_data.city = new_city
            weather_data.country = new_country
            weather_data.fetch_observation()
            weather_data.update_all()
        weather_data.api_key = config.get("weather_api", "")

        state.name = config.get("name", "")
        state.name_delay = int(config.get("pota_delay", 8))
        state.quote_delay = int(config.get("quote_delay", 15))

        state.pota_quote_show = int(config.get("pota_quote_show", 0))
        if state.pota_quote_show == 2:
            _show_name(state)
            config.set("pota_quote_show", 0)
        elif state.pota_quote_show == 1:
            _show_quote(state)
            config.set("pota_quote_show", 0)

        state.autosleep_enabled = int(config.get("autosleep", 0)) != 0

        if not state.autosleep_enabled:
            state.autosleeping = False
            state.autoslept = False
        else:
            parts = config.get("autosleep_time", "22:00,07:00").split(",")
            t1 = [int(x) for x in parts[0].split(":")]
            t2 = [int(x) for x in parts[1].split(":")]
            now = datetime.datetime.now()

            if in_time_window(now, t1, t2):
                if not state.autoslept:
                    state.autosleeping = True
                    state.autoslept = True
            else:
                state.autoslept = False
                state.autosleeping = False
    except (KeyError, ValueError):
        pass


# --- quote / name display helpers ---


def _show_quote(state: AppState) -> None:
    state.quote_widget.set_quote()
    state.quote_timestamp = datetime.datetime.now() + datetime.timedelta(seconds=state.quote_delay)
    state.fader.add(False, state.quote_widget, 50)


def show_quote(state: AppState) -> None:
    with contextlib.suppress(Exception):
        if state.quote_widget.get_alpha() == 0:
            if state.name_widget.get_alpha() >= 255 or state.fader.is_fading(state.name_widget):
                state.fader.stop(state.name_widget)
                state.fader.add(True, state.name_widget, 50, lambda: _show_quote(state))
            else:
                _show_quote(state)


def _show_name(state: AppState) -> None:
    state.name_widget.get_info(state.name)
    state.fader.add(False, state.name_widget, 50)
    state.name_timestamp = datetime.datetime.now() + datetime.timedelta(seconds=state.name_delay)


def show_name(state: AppState) -> None:
    with contextlib.suppress(Exception):
        if state.name_widget.get_alpha() == 0:
            if state.quote_widget.get_alpha() >= 255 or state.fader.is_fading(state.quote_widget):
                state.fader.stop(state.quote_widget)
                state.fader.add(True, state.quote_widget, 50, lambda: _show_name(state))
            else:
                _show_name(state)


# --- background threads ---


class _DataThread(threading.Thread):
    """Reads config and checks network connectivity every tick.

    Runs at ~2 Hz. Responsible for: reloading settings, applying RGB/weather
    changes, driving autosleep, and fading overlay/quote/name widgets in and out.
    Kept separate from _InfoThread so slow network calls never stall config reads.
    """

    def __init__(self, state: AppState) -> None:
        super().__init__(daemon=True)
        self._state = state

    def run(self) -> None:
        state = self._state
        while state.running:
            config.load()
            check_data(state)

            state.internet = check_connection()
            if state.internet:
                rgb.wifi_led(1)
                if not weather_data.initialized:
                    weather_data.init()
            else:
                rgb.wifi_led(0)

            # overlay text
            active_text = centered_text.get_active_text()
            if active_text:
                if not state.overlay_widget.matches(active_text):
                    if state.fader.is_fading(state.overlay_widget):
                        pass
                    else:
                        with contextlib.suppress(Exception):
                            if state.overlay_widget.get_alpha() >= 255:
                                state.fader.add(True, state.overlay_widget, 50)
                            else:
                                state.overlay_widget.refresh()
                                state.fader.add(False, state.overlay_widget, 50)
            else:
                with contextlib.suppress(Exception):
                    if state.overlay_widget.get_alpha() >= 255:
                        state.fader.add(True, state.overlay_widget, 50)

            if state.quote_timestamp and datetime.datetime.now() > state.quote_timestamp:
                state.quote_timestamp = None
                state.fader.add(True, state.quote_widget, 50)

            if state.name_timestamp and datetime.datetime.now() > state.name_timestamp:
                state.name_timestamp = None
                state.fader.add(True, state.name_widget, 50)

            time.sleep(0.5)


class _InfoThread(threading.Thread):
    """Fetches remote data (RSS, weather, quotes) and refreshes widget surfaces.

    Runs at ~1 Hz. Falls back to cached data when offline so widgets stay
    populated across network outages. Activities are always loaded from disk
    since they come from BLE writes, not the network.
    """

    def __init__(self, state: AppState) -> None:
        super().__init__(daemon=True)
        self._state = state

    def run(self) -> None:
        state = self._state
        while state.running:
            if not weather_data.initialized:
                weather_data.init()

            if state.internet:
                with contextlib.suppress(Exception):
                    quotes.fetch()
                with contextlib.suppress(Exception):
                    news.parse()
                with contextlib.suppress(Exception):
                    weather_data.update_all()
            else:
                news.load()
                weather_data.load()

            activities.load()
            quotes.load()
            centered_text.load()

            state.weather_widget.get_info(state.image_cache)
            state.news_widget.get_info()
            state.activities_widget.get_info()
            activities.remove_past()

            time.sleep(1)


# --- button handling ---


def handle_buttons(state: AppState) -> None:
    """Poll both hardware buttons and act on edge transitions.

    BUTTON (active-low, pulled up): held blanks the screen and turns off LEDs;
    releasing it cancels any manual sleep override.

    BUTTON_2 (active-high, pulled down): cycles the display rotation by 90°
    on the rising edge and persists the new value to config.
    """
    if not rgb.button_pressed(rgb.GPIO_BUTTON):
        if state._btn_pressed:
            state.autosleeping = False
            state._btn_pressed = False
        rgb.RGB_off() if state.autosleeping else rgb.RGB_on()
    else:
        if not state._btn_pressed:
            state.autosleeping = False
            state._btn_pressed = True
        state.screen.fill(BLACK)
        rgb.RGB_off()

    if not rgb.button_pressed(rgb.GPIO_BUTTON_2):
        if not state.rotation_btn_pressed:
            state.rotation = (state.rotation + 1) % 4
            config.set("rotation", state.rotation)
            state.rotated = True
        state.rotation_btn_pressed = True
    else:
        state.rotation_btn_pressed = False


# --- main loop ---


def _setup() -> tuple["AppState", pygame.time.Clock]:
    """Initialise pygame, hardware, widgets and background threads.

    Returns the app state and clock so the caller can tick the clock in the
    main loop.
    """
    import faulthandler
    import locale
    import os

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    os.environ["SDL_AUDIODRIVER"] = "dsp"
    faulthandler.enable()

    config.load()
    i18n_setup(config.get("language", "en"))
    news.set_rss(config.get("news_rss", news.rss_url))
    news.set_max(int(config.get("news_max", news.max_items)))

    pygame.init()
    pygame.font.init()
    locale.setlocale(locale.LC_TIME, "en_US.utf8")

    screen = pygame.display.set_mode(SCREEN_SIZE)
    pygame.display.set_caption("OMirror")
    pygame.mouse.set_visible(False)

    icon_path = IMAGES_DIR / "icon.png"
    if icon_path.exists():
        pygame.display.set_icon(pygame.image.load(str(icon_path)).convert())

    sw, sh = screen.get_size()
    fader = Fader()

    state = AppState(
        screen=screen,
        fader=fader,
        weather_widget=WeatherWidget(0),
        overlay_widget=OverlayTextWidget(0, sw, sh),
        name_widget=NameDisplayWidget(0, sw, sh),
        datetime_widget=DateTimeWidget(255),
        quote_widget=QuoteWidget(0, sw, sh),
        news_widget=NewsWidget(0, _time_since),
        activities_widget=ActivitiesWidget(0, _time_until_str),
        loading_widget=LoadingWidget(255, sw, sh),
    )

    screen.fill(BLACK)
    state.loading_widget.update()
    screen.blit(state.loading_widget.get_surface(), state.loading_widget.get_pos())
    pygame.display.update()

    load_image_cache(state)
    weather_data.init()
    rgb.init()

    _DataThread(state).start()
    _InfoThread(state).start()

    screen.fill(BLACK)
    state.loading_widget.set_message(_("Loading data..."))
    state.loading_widget.update()
    screen.blit(state.loading_widget.get_surface(), state.loading_widget.get_pos())
    pygame.display.update()

    weather_data.load()
    news.load()
    activities.load()
    centered_text.load()
    quotes.load()

    state.weather_widget.get_info(state.image_cache)
    state.news_widget.get_info()
    state.activities_widget.get_info()
    state.name_widget.get_info(state.name)
    state.quote_widget.set_quote()

    for w in (
        state.weather_widget,
        state.overlay_widget,
        state.datetime_widget,
        state.news_widget,
        state.activities_widget,
    ):
        fader.add(False, w, 25)

    screen.fill(BLACK)
    clock = pygame.time.Clock()
    return state, clock


def _main_loop(state: AppState, clock: pygame.time.Clock) -> None:
    sw, sh = state.screen.get_size()
    all_widgets = [
        state.datetime_widget,
        state.name_widget,
        state.quote_widget,
        state.overlay_widget,
        state.weather_widget,
        state.news_widget,
        state.activities_widget,
    ]

    while state.running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                state.running = False

        state.screen.fill(BLACK)

        for w in all_widgets:
            w.set_rotation(state.rotation)
            w.update()

        _draw(state, sw, sh)

        if state.autosleeping:
            state.screen.fill(BLACK)

        handle_buttons(state)
        state.fader.update()
        pygame.display.update()
        clock.tick(60)


def run() -> None:
    state, clock = _setup()
    try:
        _main_loop(state, clock)
    finally:
        rgb.RGB_off()
        rgb.cleanup()
        pygame.quit()


def _draw(state: AppState, sw: int, sh: int) -> None:
    def blit(w, x, y):
        state.screen.blit(w.get_surface(), (x, y))

    ws = {
        "dt": state.datetime_widget,
        "wx": state.weather_widget,
        "name": state.name_widget,
        "qte": state.quote_widget,
        "ovl": state.overlay_widget,
        "news": state.news_widget,
        "act": state.activities_widget,
    }

    dt_w = ws["dt"].get_surface()
    wx_w = ws["wx"].get_surface()
    nw_w = ws["news"].get_surface()
    ac_w = ws["act"].get_surface()

    if state.rotation == 0:
        blit(ws["dt"], sw - dt_w.get_width() - 25, 25)
        blit(ws["wx"], 25, 25)
        state.screen.blit(ws["name"].get_surface(), ws["name"].get_pos())
        state.screen.blit(ws["qte"].get_surface(), ws["qte"].get_pos())
        state.screen.blit(ws["ovl"].get_surface(), ws["ovl"].get_pos())
        blit(ws["news"], sw - nw_w.get_width() - 25, sh - nw_w.get_height() - 25)
        blit(ws["act"], sw - ac_w.get_width() - 25, sh - nw_w.get_height() - ac_w.get_height() - 25)

    elif state.rotation == 1:
        blit(ws["dt"], 25, 25)
        blit(ws["wx"], 25, sh - wx_w.get_height() - 25)
        blit(
            ws["name"],
            sw / 2 - ws["name"].get_surface().get_width() / 2,
            sh / 2 - ws["name"].get_surface().get_height() / 2,
        )
        blit(
            ws["qte"],
            sw / 2 - ws["qte"].get_surface().get_width(),
            sh / 2 - ws["qte"].get_surface().get_height() / 2,
        )
        blit(
            ws["ovl"],
            sw - ws["ovl"].get_surface().get_width(),
            sh / 2 - ws["ovl"].get_surface().get_height() / 2,
        )
        blit(ws["news"], sw - nw_w.get_width() - 25, 25)
        blit(ws["act"], sw - nw_w.get_width() - ac_w.get_width() - 25, 25)

    elif state.rotation == 2:
        blit(ws["dt"], 25, sh - dt_w.get_height() - 25)
        blit(ws["wx"], sw - wx_w.get_width() - 25, sh - wx_w.get_height() - 25)
        state.screen.blit(ws["name"].get_surface(), ws["name"].get_pos())
        state.screen.blit(ws["qte"].get_surface(), ws["qte"].get_pos())
        blit(
            ws["ovl"],
            sw / 2 - ws["ovl"].get_surface().get_width() / 2,
            ws["ovl"].get_surface().get_height() / 2,
        )
        blit(ws["news"], 25, 25)
        blit(ws["act"], 25, 25 + nw_w.get_height())

    elif state.rotation == 3:
        blit(ws["dt"], sw - dt_w.get_width() - 25, sh - dt_w.get_height() - 25)
        blit(ws["wx"], sw - wx_w.get_width() - 25, 25)
        blit(
            ws["name"],
            sw / 2 - ws["name"].get_surface().get_width() / 2,
            sh / 2 - ws["name"].get_surface().get_height() / 2,
        )
        blit(
            ws["qte"],
            sw / 2 - ws["qte"].get_surface().get_width() / 2,
            sh / 2 - ws["qte"].get_surface().get_height() / 2,
        )
        blit(
            ws["ovl"],
            ws["ovl"].get_surface().get_width(),
            sh / 2 - ws["ovl"].get_surface().get_height() / 2,
        )
        blit(ws["news"], 25, sh - 25 - nw_w.get_height())
        blit(ws["act"], 25 + nw_w.get_width(), sh - 25 - ac_w.get_height())
