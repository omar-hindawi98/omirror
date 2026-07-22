"""Low-level rendering primitives shared by all widgets."""

import pygame

from omirror.const import BLACK, FONTS_DIR, WHITE

_FONT_PATH = {
    "Ultralight": FONTS_DIR / "sf_ultrathin.ttf",
    "Light": FONTS_DIR / "sf_light.ttf",
    "Thin": FONTS_DIR / "sf_thin.ttf",
    "Semibold": FONTS_DIR / "sf_semibold.ttf",
    "Medium": FONTS_DIR / "sf_medium.ttf",
    "Heavy": FONTS_DIR / "sf_heavy.ttf",
    "Bold": FONTS_DIR / "sf_bold.ttf",
    "Black": FONTS_DIR / "sf_black.ttf",
    "Regular": FONTS_DIR / "sf_regular.ttf",
}

# Keyed by (weight, size) — loaded once, reused forever.
_font_cache: dict[tuple, pygame.font.Font] = {}


def _font(weight: str, size: int) -> pygame.font.Font:
    key = (weight, size)
    if key not in _font_cache:
        path = _FONT_PATH.get(weight, _FONT_PATH["Regular"])
        _font_cache[key] = pygame.font.Font(str(path), size)
    return _font_cache[key]


def text_surface(text: str, weight: str, size: int, alpha: int) -> pygame.Surface:
    """Render text to a surface with the given font weight, size and alpha.

    The text is blitted onto a BLACK background surface so that alpha
    compositing produces a fade-to-black effect rather than fade-to-transparent.
    """
    font = _font(weight, size)
    surf = font.render(text, True, WHITE)
    result = pygame.Surface((surf.get_width(), surf.get_height()))
    result.fill(BLACK)
    result.blit(surf, (0, 0))
    result.set_alpha(alpha)
    return result


class BoxContainer:
    """Vertical or horizontal surface container with alignment and anchoring."""

    LEFT = 0
    CENTER = 1
    RIGHT = 2

    NW, N, NE = 0, 1, 2
    W, C, E = 3, 4, 5
    SW, S, SE = 6, 7, 8

    def __init__(self, vertical, x, y):
        self._items = []
        self.x = x
        self.y = y
        self._surface = pygame.Surface((0, 0))
        self.vertical = vertical
        self.height = 0
        self.width = 0
        self.justify = self.LEFT
        self.anchor = self.NW
        self.alpha = 255
        self.padding_x = 0
        self.padding_y = 0

    def add(self, surface):
        self._items.append(surface)

    def move(self, x, y):
        self.x = x
        self.y = y

    def set_justify(self, justify):
        self.justify = justify

    def set_anchor(self, anchor):
        self.anchor = anchor

    def set_alpha(self, alpha):
        self.alpha = alpha

    def get_alpha(self):
        return self.alpha

    def set_padding(self, x, y):
        self.padding_x = x
        self.padding_y = y

    def draw(self):
        """Composite all children onto a single surface and return (surface, pos).

        The anchor constant controls where (x, y) is treated as the origin:
        N/NW/NE anchors place y at the top edge; S/SW/SE at the bottom edge;
        W/C/E at the vertical centre. The same logic applies horizontally.
        """
        self.height = 0
        self.width = 0

        resolved = []
        for item in self._items:
            if isinstance(item, BoxContainer):
                s, _ = item.draw()
                resolved.append(s)
            else:
                resolved.append(item)

        for surf in resolved:
            if self.vertical:
                self.height += surf.get_height()
                self.width = max(self.width, surf.get_width())
            else:
                self.width += surf.get_width()
                self.height = max(self.height, surf.get_height())

        self._surface = pygame.Surface((self.width, self.height))

        cx = cy = 0
        for surf in resolved:
            if self.vertical:
                if self.justify == self.LEFT:
                    bx = cx
                elif self.justify == self.CENTER:
                    bx = self.width / 2 - surf.get_width() / 2
                else:
                    bx = self.width - surf.get_width()
                self._surface.blit(surf, (bx, cy))
                cy += surf.get_height()
                self.width = max(self.width, surf.get_width())
            else:
                self._surface.blit(surf, (cx, cy))
                cx += surf.get_width()
                self.height = max(self.height, surf.get_height())

        if self.anchor in (self.N, self.NW, self.NE):
            py = self.y + self.padding_y
        elif self.anchor in (self.W, self.C, self.E):
            py = self.y - self.height / 2
        else:
            py = self.y - self.height - self.padding_y

        if self.anchor in (self.NW, self.W, self.SW):
            px = self.x + self.padding_x
        elif self.anchor in (self.N, self.C, self.S):
            px = self.x - self.width / 2
        else:
            px = self.x - self.width - self.padding_x

        self._surface.set_alpha(self.alpha)
        return self._surface, (px, py, 0, 0)


class Fader:
    """Manages concurrent fade-in / fade-out animations for widget objects."""

    def __init__(self):
        self._queue = []

    def add(self, fade_out, obj, speed, callback=None):
        """Queue a fade. fade_out=True fades out, False fades in."""
        if not self.is_fading(obj):
            self._queue.append(
                {"object": obj, "speed": speed, "callback": callback, "out": fade_out}
            )

    def stop(self, obj):
        self._queue = [item for item in self._queue if item["object"] is not obj]

    def is_fading(self, obj):
        return any(item["object"] is obj for item in self._queue)

    def update(self):
        for item in list(self._queue):
            obj = item["object"]
            if item["out"]:
                obj.set_alpha(obj.get_alpha() - item["speed"])
                if obj.get_alpha() <= 0:
                    self.stop(obj)
                    if item["callback"]:
                        item["callback"]()
            else:
                obj.set_alpha(obj.get_alpha() + item["speed"])
                if obj.get_alpha() >= 255:
                    self.stop(obj)
                    if item["callback"]:
                        item["callback"]()
