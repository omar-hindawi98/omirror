from omirror.const import LIST_ITEM_ALPHAS, LIST_ITEM_COUNT, LIST_ITEM_TRUNCATE
from omirror.display.renderer import text_surface
from omirror.display.widgets.base import ListWidget
from omirror.widgets import news as data


class NewsWidget(ListWidget):
    def get_info(self) -> None:
        self.header = text_surface("News", "Thin", 32, 255)
        self.items = []
        for i in range(LIST_ITEM_COUNT):
            if len(data.sorted_articles) > i:
                art = data.sorted_articles[i]
                t = art["title"]
                self.items.append(
                    (
                        text_surface(
                            self._format_date(art["date"]), "Thin", 16, LIST_ITEM_ALPHAS[i] - 15
                        ),
                        text_surface(
                            (t[:LIST_ITEM_TRUNCATE] + "..") if len(t) > LIST_ITEM_TRUNCATE else t,
                            "Light",
                            16,
                            LIST_ITEM_ALPHAS[i],
                        ),
                    )
                )
            else:
                self.items.append(
                    (
                        text_surface("-", "Thin", 16, LIST_ITEM_ALPHAS[i] - 15),
                        text_surface("-", "Light", 16, LIST_ITEM_ALPHAS[i]),
                    )
                )
        self._dirty = True
