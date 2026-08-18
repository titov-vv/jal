import pytest
from math import dist
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from jal.widgets.theme import (Theme, Meaning, contrast, _ANCHOR,
                               _MIN_CONTRAST, _MIN_CONTRAST_MUTED)


# The grounds a JAL user may actually have under the colours: the two obvious ones, a theme that is neither
# (sepia - the case that a light/dark table of hand-picked values can't serve), and the pathological maximum.
def _palette(base: QColor, text: QColor) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Window, base)
    palette.setColor(QPalette.WindowText, text)
    return palette


PALETTES = {
    'light': _palette(QColor(255, 255, 255), QColor(0, 0, 0)),
    'dark': _palette(QColor(30, 30, 30), QColor(224, 224, 224)),
    'sepia': _palette(QColor(244, 236, 216), QColor(60, 45, 30)),
    'contrast': _palette(QColor(0, 0, 0), QColor(255, 255, 255))
}
ROW_KINDS = [Meaning.SENT, Meaning.ARRIVED, Meaning.BRIDGE, Meaning.BASIS, Meaning.POISONING, Meaning.AIRDROP]


@pytest.fixture(params=list(PALETTES), ids=list(PALETTES))
def themed_app(request):
    app = QApplication.instance() if QApplication.instance() else QApplication([])
    original = app.palette()
    app.setPalette(PALETTES[request.param])
    yield app
    app.setPalette(original)


# Any colour meant to be drawn WITH has to be readable on the ground it is drawn on - that is the whole promise
# of the module, and the one that a retuned anchor could silently break.
def test_text_is_readable(themed_app):
    ground = themed_app.palette().base().color()
    for meaning in Meaning:
        minimum = _MIN_CONTRAST_MUTED if meaning == Meaning.MUTED else _MIN_CONTRAST
        assert contrast(Theme.text(meaning, ground), ground) >= minimum, f"{meaning.name} is not readable"


# ... and any colour meant to be drawn BEHIND text has to leave that text readable.
def test_fills_and_tints_keep_their_text_readable(themed_app):
    ink = themed_app.palette().text().color()
    for meaning in Meaning:
        for color in (Theme.fill(meaning), Theme.tint(meaning)):
            assert contrast(ink, color) >= _MIN_CONTRAST, f"text is not readable on {meaning.name}"


# The meaning lives in the hue, so the hue is the thing that must not be derived away. Text keeps it exactly;
# a fill or a tint is a mix, so each of its channels has to sit between the ground and the hue it was mixed with.
def test_hue_carries_the_meaning(themed_app):
    ground = themed_app.palette().base().color()
    for meaning in Meaning:
        if meaning == Meaning.MUTED:   # the one meaning that is achromatic on purpose
            continue
        hue, saturation = _ANCHOR[meaning]
        assert Theme.text(meaning, ground).hslHue() == hue
        anchor = QColor.fromHsl(hue, round(saturation * 255 / 100), 128)
        for color in (Theme.fill(meaning, ground), Theme.tint(meaning, ground)):
            for value, limit in zip(color.getRgb()[:3], zip(ground.getRgb()[:3], anchor.getRgb()[:3])):
                assert min(limit) - 1 <= value <= max(limit) + 1


# The pending-transfers report tells six kinds of unfinished leg apart by tint alone, so two of them landing on
# the same colour would lose information rather than just look wrong.
def test_row_tints_stay_distinguishable(themed_app):
    tints = [Theme.tint(kind) for kind in ROW_KINDS]
    for i, first in enumerate(tints):
        for second in tints[i + 1:]:
            assert dist(first.getRgb()[:3], second.getRgb()[:3]) >= 8


# A tint is a whisper and a fill is a statement: on any ground, the tint has to stay closer to that ground.
def test_tint_is_fainter_than_fill(themed_app):
    ground = themed_app.palette().base().color()
    for meaning in Meaning:
        if meaning == Meaning.MUTED:
            continue
        tint = dist(Theme.tint(meaning, ground).getRgb()[:3], ground.getRgb()[:3])
        fill = dist(Theme.fill(meaning, ground).getRgb()[:3], ground.getRgb()[:3])
        assert tint < fill


def test_separator_is_visible_but_not_content(themed_app):
    ground = themed_app.palette().base().color()
    separator = Theme.separator(ground)
    assert 1.1 < contrast(separator, ground) < _MIN_CONTRAST


# A system theme switch changes the palette, and everything derived from the old one has to go. This is the only
# invalidation the module has - if it stops working, the app keeps light-theme colours on a dark desktop.
def test_palette_change_invalidates_derived_colors():
    app = QApplication.instance() if QApplication.instance() else QApplication([])
    original = app.palette()
    try:
        app.setPalette(PALETTES['light'])
        light_text, light_tint, light_line = Theme.text(Meaning.POSITIVE), Theme.tint(Meaning.SENT), Theme.separator()
        app.setPalette(PALETTES['dark'])
        dark_text, dark_tint, dark_line = Theme.text(Meaning.POSITIVE), Theme.tint(Meaning.SENT), Theme.separator()
        # Ink moves away from the ground and backgrounds move with it, so the same three colours invert together
        assert light_text.lightness() < dark_text.lightness()
        assert light_tint.lightness() > dark_tint.lightness()
        assert light_line.lightness() > dark_line.lightness()
    finally:
        app.setPalette(original)


def test_contrast_ratio():
    assert contrast(QColor(0, 0, 0), QColor(255, 255, 255)) == pytest.approx(21.0)
    assert contrast(QColor(120, 120, 120), QColor(120, 120, 120)) == pytest.approx(1.0)


# Nothing may import the fixed-colour table this module replaced - re-introducing it would silently put an
# absolute colour back on a dark theme, which is exactly the defect S5 closes.
def test_no_absolute_color_table_remains():
    import os
    from jal import constants
    assert not hasattr(constants, 'CustomColor')
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    offenders = []
    for path, _dirs, files in os.walk(os.path.join(root, 'jal')):
        for name in [x for x in files if x.endswith('.py')]:
            with open(os.path.join(path, name), encoding='utf-8') as file:
                if 'CustomColor' in file.read():
                    offenders.append(os.path.join(path, name))
    assert offenders == []
