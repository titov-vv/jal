import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QColor, QPalette, QImage, QPainter
from PySide6.QtWidgets import QApplication

from tests.fixtures import project_root, data_path, prepare_db
from tests.test_theme_surfaces import THEMES
from jal.db.settings import JalSettings
from jal.widgets.icons import JalIcon, JalIconEngine, ICON_PREFIX
from jal.widgets.theme import Meaning, Theme, contrast

# Set JAL_SHOTS to a directory to also write out the icon sheet each palette produces - that is what the
# semantic table in JalIcon._icon_meanings is retuned against.
SHOTS = os.environ.get('JAL_SHOTS', '')
GLYPH_SIZE = 32


@pytest.fixture(params=list(THEMES), ids=list(THEMES))
def themed(request, prepare_db):
    app = QApplication.instance()
    original = app.palette()
    app.setPalette(THEMES[request.param])
    JalIcon()          # the class-level icon table is built once and outlives the palette it was built under
    yield request.param
    app.setPalette(original)


# Every pixel of a glyph that is opaque enough to read, and how often each colour of them occurs
def _opaque_colours(icon: QIcon, mode=QIcon.Mode.Normal, size=GLYPH_SIZE) -> dict:
    image = icon.pixmap(QSize(size, size), mode, QIcon.State.Off).toImage()
    counts = {}
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() > 200:
                counts[colour.rgb()] = counts.get(colour.rgb(), 0) + 1
    return counts


def _dominant(icon: QIcon, mode=QIcon.Mode.Normal) -> QColor:
    counts = _opaque_colours(icon, mode)
    assert counts, "the glyph rendered fully transparent"
    return QColor.fromRgb(max(counts, key=counts.get))


# The names of every glyph JalIcon knows: an icon id whose file is an .ico, which is what says "black shape,
# no colour of its own". The ids themselves are enum.auto() objects used as identity keys, never integers.
def _glyph_ids():
    names = [name for name in dir(JalIcon)
             if not name.startswith('_')
             and getattr(JalIcon, name) in JalIcon._icon_files
             and JalIcon._icon_files[getattr(JalIcon, name)].lower().endswith('.ico')]
    assert len(names) > 30, "the glyph list came out empty - the rest of this file would assert nothing"
    return names


# ----------------------------------------------------------------------------------------------------------------------
# A glyph carries a shape and no colour of its own, so on any ground it has to come out readable against it. This
# is the whole point of the change: on a dark palette these were black on black.
def test_every_glyph_is_readable_on_its_ground(themed):
    ground = QApplication.palette().color(QPalette.Window)
    unreadable = []
    for name in _glyph_ids():
        ink = _dominant(JalIcon[getattr(JalIcon, name)])
        if contrast(ink, ground) < 4.5:
            unreadable.append((name, ink.name(), round(contrast(ink, ground), 2)))
    assert not unreadable


# The application's own logo is a picture, not a glyph - it has colours that mean something and must survive
# every palette untouched.
def test_the_application_logo_is_never_recoloured(themed):
    logo = _opaque_colours(JalIcon[JalIcon.APP_MAIN])
    assert len(logo) > 8      # a tinted icon collapses to a single colour
    plain = _opaque_colours(QIcon(JalSettings.path(JalSettings.PATH_ICONS) + ICON_PREFIX + "jal.png"))
    assert logo == plain


# Flags and the logos of broker/blockchain modules are brands: recolouring them would be wrong in a different way.
def test_flags_are_never_recoloured(themed):
    flag = _opaque_colours(JalIcon.country_flag('pt'))
    assert len(flag) > 3


# A meaning is a hue kept across grounds, not a fixed value - the colour moves with the palette but stays the
# colour that meaning asked for.
@pytest.mark.parametrize('name, meaning', [('BUY', Meaning.POSITIVE), ('SELL', Meaning.NEGATIVE),
                                           ('WITH_CREDIT', Meaning.WARNING)])
def test_a_meaningful_glyph_takes_its_meaning_colour(themed, name, meaning):
    ground = QApplication.palette().color(QPalette.Active, QPalette.Window)
    assert _dominant(JalIcon[getattr(JalIcon, name)]).name() == Theme.text(meaning, ground).name()


def test_a_glyph_with_no_meaning_takes_the_palette_ink(themed):
    assert _dominant(JalIcon[JalIcon.COPY]).name() == QApplication.palette().color(QPalette.Active, QPalette.WindowText).name()


# The disabled state used to be a hardcoded 20% alpha painted over whatever the platform style would have drawn.
# It is now the palette's own disabled ink, so a platform that greys differently is followed rather than overruled.
def test_disabled_uses_the_palettes_own_disabled_ink(themed):
    palette = QApplication.palette()
    for name in ('BUY', 'SELL', 'COPY'):
        icon = JalIcon[getattr(JalIcon, name)]
        assert _dominant(icon, QIcon.Mode.Disabled).name() == palette.color(QPalette.Disabled, QPalette.WindowText).name()
        assert _dominant(icon, QIcon.Mode.Disabled).name() != _dominant(icon, QIcon.Mode.Normal).name()


# An icon on a highlighted row sits on Highlight, not on Base - a black glyph on a dark blue selection was
# unreadable on the light palette too, not only on dark.
def test_selected_glyphs_are_readable_on_the_highlight(themed):
    highlight = QApplication.palette().color(QPalette.Highlight)
    for name in ('BUY', 'COPY', 'SELL'):
        ink = _dominant(JalIcon[getattr(JalIcon, name)], QIcon.Mode.Selected)
        assert contrast(ink, highlight) >= 3.0, (name, ink.name())


# The cache is keyed by the palette's cacheKey(), so a theme switch has to invalidate it with no event delivered
# anywhere - that is what lets a widget keep the QIcon it was handed at start-up.
def test_a_palette_change_recolours_an_already_rendered_glyph(prepare_db):
    app = QApplication.instance()
    original = app.palette()
    try:
        JalIcon()
        app.setPalette(THEMES['light'])
        on_light = _dominant(JalIcon[JalIcon.COPY])
        app.setPalette(THEMES['dark'])
        on_dark = _dominant(JalIcon[JalIcon.COPY])
        assert on_light.name() != on_dark.name()
        assert contrast(on_dark, THEMES['dark'].color(QPalette.Window)) >= 4.5
    finally:
        app.setPalette(original)


# QIcon takes ownership of the engine it is built from, so clone() has to hand back a new object - two icons
# sharing one engine would free it twice.
def test_clone_returns_a_separate_engine(prepare_db):
    engine = JalIconEngine(QIcon(JalSettings.path(JalSettings.PATH_ICONS) + ICON_PREFIX + "buy.ico"), Meaning.POSITIVE)
    clone = engine.clone()
    assert clone is not engine
    assert isinstance(clone, JalIconEngine)
    assert not clone.pixmap(QSize(GLYPH_SIZE, GLYPH_SIZE), QIcon.Mode.Normal, QIcon.State.Off).isNull()


# A glyph has to keep answering for the sizes its source file actually holds, or a toolbar asking for 24 px gets
# a scaled 48 px one.
def test_available_sizes_come_from_the_source_file(themed):
    assert JalIcon[JalIcon.BUY].availableSizes() == QIcon(
        JalSettings.path(JalSettings.PATH_ICONS) + ICON_PREFIX + "buy.ico").availableSizes()


# Not an assertion so much as the sheet the semantic table is judged against - every glyph in one image, per palette.
def test_icon_sheet(themed):
    if not SHOTS:
        pytest.skip("set JAL_SHOTS to write the icon sheet")
    names = sorted(_glyph_ids())
    columns, cell = 8, GLYPH_SIZE + 16
    rows = (len(names) + columns - 1) // columns
    sheet = QImage(columns * cell, rows * cell, QImage.Format_ARGB32)
    sheet.fill(QApplication.palette().color(QPalette.Window))
    painter = QPainter(sheet)
    for index, name in enumerate(names):
        x, y = (index % columns) * cell + 8, (index // columns) * cell + 8
        JalIcon[getattr(JalIcon, name)].paint(painter, x, y, GLYPH_SIZE, GLYPH_SIZE)
    painter.end()
    assert sheet.save(os.path.join(SHOTS, f"icons_{themed}.png"))
