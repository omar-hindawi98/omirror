import pygame

from omirror.const import IMAGES_DIR
from omirror.display.renderer import BoxContainer, text_surface
from omirror.display.widgets.base import Widget
from omirror.i18n import _


class LoadingWidget(Widget):
    def __init__(self, alpha, screen_w, screen_h):
        super().__init__(alpha)
        self._sw = screen_w
        self._sh = screen_h
        self._pos = None
        self._message = _("Initializing...")
        self._logo = pygame.image.load(str(IMAGES_DIR / "logo.png")).convert()

    def set_message(self, message):
        self._message = message

    def update(self):
        box = BoxContainer(True, self._sw / 2, self._sh / 2)
        box.add(self._logo)
        box.add(text_surface(self._message, "Thin", 36, 255))
        box.set_anchor(BoxContainer.C)
        box.set_justify(BoxContainer.CENTER)
        surf, pos = box.draw()
        surf.set_alpha(self.alpha)
        self._base = surf
        self._pos = pos
        self._rotate()

    def get_pos(self):
        return self._pos
