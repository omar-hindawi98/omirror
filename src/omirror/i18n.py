"""Internationalisation helpers.

Call ``setup(language)`` once at startup (or whenever the language setting
changes) to activate the right translation. All other modules import ``_``
from here and use it exactly like the built-in gettext ``_``.

Supported language codes: "en" (default), "sv".
Falls back to the English identity translation if a locale file is missing.
"""

import gettext
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Locale files live next to the package source so they are included in the
# installed wheel via the package-data entry in pyproject.toml.
_LOCALE_DIR = Path(__file__).parent / "locale"
_DOMAIN = "omirror"

_current_lang: str = "en"
_translation: gettext.NullTranslations = gettext.NullTranslations()


def setup(language: str) -> None:
    """Load the translation catalogue for *language* (e.g. 'en', 'sv')."""
    global _current_lang, _translation
    language = language.strip().lower()
    if language == _current_lang and not isinstance(_translation, gettext.NullTranslations):
        return
    try:
        _translation = gettext.translation(
            _DOMAIN,
            localedir=str(_LOCALE_DIR),
            languages=[language],
        )
        _current_lang = language
        log.info("Loaded translation for language %r", language)
    except FileNotFoundError:
        log.warning("No translation found for %r, falling back to English", language)
        _translation = gettext.NullTranslations()
        _current_lang = language


def _(message: str) -> str:
    """Translate *message* using the currently active language."""
    return _translation.gettext(message)
