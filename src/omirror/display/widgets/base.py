import pygame

from omirror.const import BLACK, LIST_WIDGET_SIZE


class Widget:
    """Base class for all mirror widgets.

    Maintains a dirty flag so subclasses can skip surface reconstruction on
    frames where their data has not changed — only an alpha update is needed
    to support smooth fade-in/fade-out animations.
    """

    def __init__(self, alpha: int = 0) -> None:
        self.alpha = alpha
        self._base = pygame.Surface((0, 0))
        self._active = pygame.Surface((0, 0))
        self._rotation = 0
        self._dirty = True

    def set_alpha(self, alpha: int) -> None:
        self.alpha = max(0, min(255, alpha))

    def get_alpha(self) -> int:
        return self.alpha

    def set_rotation(self, rotation: int) -> None:
        if rotation != self._rotation:
            self._rotation = rotation
            self._dirty = True

    def _rotate(self) -> None:
        self._active = pygame.transform.rotate(self._base, self._rotation * 90)
        self._dirty = False

    def get_surface(self) -> pygame.Surface:
        return self._active

    def update(self) -> None:
        pass

    def get_pos(self) -> tuple[int, int]:
        return (0, 0)


class ListWidget(Widget):
    """Base for News and Activities widgets — identical surface layout, different data."""

    def __init__(self, alpha: int, format_date_fn) -> None:
        super().__init__(alpha)
        self._format_date = format_date_fn
        self._base = pygame.Surface(LIST_WIDGET_SIZE)
        self.header: pygame.Surface = pygame.Surface((0, 0))
        self.items: list[tuple[pygame.Surface, pygame.Surface]] = []

    def get_info(self) -> None:
        """Subclasses override to populate self.header and self.items, then set self._dirty = True."""
        raise NotImplementedError

    def update(self) -> None:
        """Rebuild the widget surface if dirty, otherwise just update alpha."""
        if not self._dirty:
            self._active.set_alpha(self.alpha)
            return

        w, _ = LIST_WIDGET_SIZE
        s = pygame.Surface(LIST_WIDGET_SIZE)
        s.blit(self.header, (w - self.header.get_width(), 0))
        y = self.header.get_height() + 6

        holder = pygame.Surface(LIST_WIDGET_SIZE)
        holder.fill(BLACK)
        hy = 0
        for time_surf, text_surf in self.items:
            holder.blit(time_surf, (0, hy))
            tx = w - text_surf.get_width() if text_surf.get_width() < 175 else 75
            holder.blit(text_surf, (tx, hy))
            hy += text_surf.get_height() + 3

        s.blit(holder, (0, y))
        s.set_alpha(self.alpha)
        self._base = s
        self._rotate()
