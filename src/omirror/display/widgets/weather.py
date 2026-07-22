import pygame

from omirror.display.renderer import text_surface
from omirror.display.widgets.base import Widget
from omirror.widgets import weather as data


class WeatherWidget(Widget):
    def __init__(self, alpha=0):
        super().__init__(alpha)
        self._info_version = -1
        # Pre-assign so update() is safe before first get_info()
        self.status_img = pygame.Surface((0, 0))
        self.status_text = text_surface("-", "Regular", 30, 255)
        self.location = text_surface("-", "Ultralight", 60, 255)
        self.temp = text_surface("-", "Light", 74, 255)
        self.max = [text_surface("-", "Light", 28, 255)] * 4
        self.min = [text_surface("-", "Thin", 28, 255)] * 4
        self.splitter = pygame.Surface((0, 0))
        self.line2 = pygame.Surface((0, 0))
        self.day_names = [text_surface("-", "Regular", 28, 255)] * 4
        self.day_imgs = [pygame.Surface((0, 0))] * 4
        self.day_maxes = [text_surface("-", "Light", 28, 255)] * 4

    def get_info(self, image_cache):
        self._cache = image_cache
        if data.forecast:
            f = data.forecast
            self.status_img = image_cache[data.get_image(1, f[0]["status"])]
            self.status_text = text_surface(
                data.weather_description(f[0]["status"]), "Regular", 30, 255
            )
            self.location = text_surface(data.get_city(), "Ultralight", 60, 255)
            self.temp = text_surface(f"{f[0]['temp']:.1f}°", "Light", 74, 255)
            self.max = [
                text_surface(f"{f[i]['temp_max']:.1f}°", "Light", 28, 255) for i in range(4)
            ]
            self.min = [text_surface(f"{f[i]['temp_min']:.1f}°", "Thin", 28, 255) for i in range(4)]
            self.splitter = image_cache["divider_1"]
            self.line2 = image_cache["line_2"]
            self.day_names = [
                text_surface(f[i]["day"][:3], "Regular", 28, 255) for i in range(4, 8)
            ]
            self.day_imgs = [image_cache[data.get_image(0, f[i]["status"])] for i in range(4, 8)]
            self.day_maxes = [
                text_surface(f"{f[i]['temp_max']:.1f}°", "Light", 28, 255) for i in range(4, 8)
            ]
        else:
            self.splitter = image_cache["divider_1"]
            self.line2 = image_cache["line_2"]
        self._dirty = True

    def update(self):
        if not self._dirty:
            self._active.set_alpha(self.alpha)
            return

        s = pygame.Surface((600, 480))
        s.blit(self.status_img, (0, 0))
        s.blit(self.status_text, (125 - self.status_text.get_width() / 2, 235))

        # hourly temp columns
        x = 255
        gap = 10
        for i in range(4):
            s.blit(self.max[i], (x, 145))
            s.blit(self.min[i], (x, 176))
            col_w = max(self.max[i].get_width(), self.min[i].get_width())
            if i < 3:
                s.blit(self.splitter, (x + col_w + gap, 145))
            x += col_w + gap * 2

        total_w = x - 255
        s.blit(self.temp, (255 + total_w / 2 - self.temp.get_width() / 2, 60))
        s.blit(self.location, (255 + total_w / 2 - self.location.get_width() / 2, -5))

        # forecast days
        y = 250 + self.status_text.get_height()
        for i in range(4):
            s.blit(self.day_names[i], (0, y))
            s.blit(self.day_imgs[i], (150 - self.day_imgs[i].get_width() / 2, y))
            s.blit(self.day_maxes[i], (300 - self.day_maxes[i].get_width(), y))
            y += self.day_names[i].get_height() + 3
            if i < 3:
                s.blit(self.line2, (0, y))
                y += 3

        s.set_alpha(self.alpha)
        self._base = s
        self._rotate()
