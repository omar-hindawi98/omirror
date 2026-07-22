from omirror.display.renderer import BoxContainer, text_surface
from omirror.display.text_utils import split_words
from omirror.display.widgets.base import Widget
from omirror.widgets import quotes as data


class QuoteWidget(Widget):
    def __init__(self, alpha, screen_w, screen_h):
        super().__init__(alpha)
        self._sw = screen_w
        self._sh = screen_h
        self._pos = None
        self._lines = []
        self._text = ""

    def set_quote(self):
        q = data.random_quote()
        self._text = q["quote"]
        self._lines = [text_surface(line, "Thin", 35, 255) for line in split_words(self._text, 30)]
        self._lines.append(text_surface(f"- {q['author']}", "Light", 24, 175))

    def matches(self, quote_text):
        return self._text == quote_text

    def update(self):
        box = BoxContainer(True, self._sw / 2, self._sh / 2)
        for line in self._lines:
            box.add(line)
        box.set_anchor(BoxContainer.C)
        box.set_justify(BoxContainer.CENTER)
        surf, pos = box.draw()
        surf.set_alpha(self.alpha)
        self._base = surf
        self._pos = pos
        self._rotate()

    def get_pos(self):
        return self._pos
