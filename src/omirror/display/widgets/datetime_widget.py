import time

import pygame

from omirror.display.renderer import text_surface
from omirror.display.widgets.base import Widget


class DateTimeWidget(Widget):
    def __init__(self, alpha=0):
        super().__init__(alpha)
        self._last_time_str = ""

    def update(self):
        current = time.strftime("%A %B %d %Y %H:%M:%S")
        if current == self._last_time_str and not self._dirty:
            self._active.set_alpha(self.alpha)
            return
        self._last_time_str = current
        self._dirty = True

        s = pygame.Surface((550, 300))
        BLACK = (0, 0, 0)
        s.fill(BLACK)

        w = s.get_width()
        y = 0

        day = text_surface(time.strftime("%A").capitalize(), "Ultralight", 60, 255)
        s.blit(day, (w - day.get_width(), y))
        y += day.get_height()

        date = text_surface(
            time.strftime("%B").capitalize()[:3] + time.strftime(" %d, %Y"), "Thin", 60, 255
        )
        s.blit(date, (w - date.get_width(), y))
        y += date.get_height()

        seconds = text_surface(time.strftime("%S"), "Ultralight", 52, 180)
        s.blit(seconds, (w - seconds.get_width(), y))

        clock = text_surface(time.strftime("%H:%M"), "Ultralight", 95, 255)
        s.blit(clock, (w - 58 - clock.get_width(), y - 10))

        s.set_alpha(self.alpha)
        self._base = s
        self._rotate()
