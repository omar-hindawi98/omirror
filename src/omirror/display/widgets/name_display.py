from omirror.display.renderer import BoxContainer, text_surface
from omirror.display.widgets.base import Widget


class NameDisplayWidget(Widget):
    def __init__(self, alpha, screen_w, screen_h):
        super().__init__(alpha)
        self._sw = screen_w
        self._sh = screen_h
        self._pos = None
        self._name_surf = text_surface("-", "Thin", 82, 255)

    def get_info(self, name):
        self._name_surf = text_surface(name if name else "-", "Thin", 82, 255)

    def update(self):
        box = BoxContainer(True, self._sw / 2, self._sh / 2)
        box.add(self._name_surf)
        box.set_anchor(BoxContainer.C)
        surf, pos = box.draw()
        surf.set_alpha(self.alpha)
        self._base = surf
        self._pos = pos
        self._rotate()

    def get_pos(self):
        return self._pos
