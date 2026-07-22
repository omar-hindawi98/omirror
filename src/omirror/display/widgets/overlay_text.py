from omirror.display import centered_text
from omirror.display.renderer import BoxContainer, text_surface
from omirror.display.text_utils import split_words
from omirror.display.widgets.base import Widget


class OverlayTextWidget(Widget):
    def __init__(self, alpha, screen_w, screen_h):
        super().__init__(alpha)
        self._sw = screen_w
        self._sh = screen_h
        self._pos = None
        self._text = ""
        self._lines = []

    def refresh(self):
        text = centered_text.get_active_text() or ""
        self._text = text
        self._lines = [text_surface(line, "Thin", 60, 255) for line in split_words(text, 20)]

    def matches(self, text):
        return self._text == text

    def update(self):
        box = BoxContainer(True, self._sw / 2, self._sh)
        for line in self._lines:
            box.add(line)
        box.set_anchor(BoxContainer.S)
        box.set_padding(0, 25)
        box.set_justify(BoxContainer.CENTER)
        surf, pos = box.draw()
        surf.set_alpha(self.alpha)
        self._base = surf
        self._pos = pos
        self._rotate()

    def get_pos(self):
        return self._pos
