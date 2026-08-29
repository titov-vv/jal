import logging
import os
import re
from enum import auto
from collections import UserDict
from PySide6.QtGui import QIcon, QIconEngine, QPixmap, QImage, QPainter, QPalette
from PySide6.QtWidgets import QApplication
from jal.db.settings import JalSettings
from jal.widgets.theme import Meaning, Theme


ICON_PREFIX = "ui_"
FLAG_PREFIX = "flag_"    # Country flags for languages and reports
AUX_PREFIX = "aux_"      # Logos of broker statement modules
CHAIN_PREFIX = "chain_"  # Logos of blockchain fetcher modules
ATYPE_PREFIX = "atype_"  # Glyphs of the account types (see JalAccount._TYPE_ICONS)
MONEY_PREFIX = "money_"  # Currency signs, each file named after the ticker of the currency it stands for

# ----------------------------------------------------------------------------------------------------------------------
# Every ui_*.ico, atype_*.ico and money_*.ico in jal/img is a black glyph on transparency - the files carry a shape
# and no color at all. This engine keeps the shape and supplies the color, asking the live palette for it at paint time.
class JalIconEngine(QIconEngine):
    def __init__(self, source, meaning=None):
        super().__init__()
        self._source = QIcon(source) if isinstance(source, str) else source
        self._meaning = meaning
        self._cache = {}
        self._cache_palette = None

    # The color this glyph is drawn in, against the ground it is drawn on.
    # A meaningful glyph keeps its hue and takes whatever lightness makes it readable, derived against Window
    # rather than Base. A glyph with no meaning is simply the palette's own text colour, which is what every other
    # glyph on a toolbar is drawn in anyway.
    def _ink(self, mode: QIcon.Mode):
        palette = QApplication.palette()
        if mode == QIcon.Mode.Disabled:
            return palette.color(QPalette.Disabled, QPalette.WindowText)
        if mode == QIcon.Mode.Selected:
            ground = palette.color(QPalette.Highlight)
            return Theme.text(self._meaning, ground) if self._meaning is not None \
                else palette.color(QPalette.HighlightedText)
        if self._meaning is not None:
            return Theme.text(self._meaning, palette.color(QPalette.Active, QPalette.Window))
        return palette.color(QPalette.Active, QPalette.WindowText)

    def pixmap(self, size, mode, state) -> QPixmap:
        palette_key = QApplication.palette().cacheKey()
        if self._cache_palette != palette_key:
            self._cache.clear()
            self._cache_palette = palette_key
        key = (size.width(), size.height(), mode, state)
        if key not in self._cache:
            # Painting an opaque colour in 'SourceIn' mode keeps the glyph's alpha and replaces its colour.
            # Conversion to a format with an alpha channel is required as some files may not have one.
            image = self._source.pixmap(size, QIcon.Mode.Normal, state).toImage()
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(image.rect(), self._ink(mode))
            painter.end()
            self._cache[key] = QPixmap.fromImage(image)
        return self._cache[key]

    def paint(self, painter, rect, mode, state):
        painter.drawPixmap(rect, self.pixmap(rect.size(), mode, state))

    def availableSizes(self, mode=QIcon.Mode.Normal, state=QIcon.State.Off) -> list:
        return self._source.availableSizes(QIcon.Mode.Normal, state)

    def actualSize(self, size, mode, state):
        return self._source.actualSize(size, QIcon.Mode.Normal, state)

    # QIcon takes ownership of the engine it is built from, so a clone has to be a new object - handing back
    # self would let two icons free the same engine.
    def clone(self) -> QIconEngine:
        return JalIconEngine(self._source, self._meaning)


class JalIcon(UserDict):
    NONE = auto()
    ADD = auto()
    ADD_CHILD = auto()
    APP_MAIN = auto()
    BOND_AMORTIZATION = auto()
    BOND_INTEREST = auto()
    BUY = auto()
    CANCEL = auto()
    CHART = auto()
    CLEAN = auto()
    CONVERSION = auto()
    COPY = auto()
    DELISTING = auto()
    DEPOSIT_ACCOUNT = auto()
    DEPOSIT_OPEN = auto()
    DEPOSIT_CLOSE = auto()
    DETAILS = auto()
    DIVIDEND = auto()
    FEE = auto()
    INTEREST = auto()
    LIST = auto()
    MERGER = auto()
    MINUS = auto()
    OK = auto()
    PLUS = auto()
    REMOVE = auto()
    SELL = auto()
    SPINOFF = auto()
    SWAP = auto()
    SPLIT = auto()
    STOCK_DIVIDEND = auto()
    STOCK_VESTING = auto()
    SYMBOL_CHANGE = auto()
    TAG = auto()
    TAX = auto()
    TOTAL = auto()
    TRANSFER_IN = auto()
    TRANSFER_OUT = auto()
    TRANSFER_ASSET_IN = auto()
    TRANSFER_ASSET_OUT = auto()
    WITH_CREDIT = auto()

    FLAG_PT = auto()
    FLAG_RU = auto()
    FLAG_US = auto()

    _icon_files = {
        ADD: "add.ico",
        ADD_CHILD: "add_child.ico",
        APP_MAIN: "jal.png",
        BOND_AMORTIZATION: "amortization.ico",
        BOND_INTEREST: "coupon.ico",
        BUY: "buy.ico",
        CANCEL: "cancel.ico",
        CHART: "chart.ico",
        CLEAN: "clean.ico",
        CONVERSION: "renaming.ico",             # TODO dedicated icon for conversions (reuses the symbol-change glyph)
        COPY: "copy.ico",
        DELISTING: "delisting.ico",
        DEPOSIT_ACCOUNT: "deposit_account.ico",
        DEPOSIT_OPEN: "deposit_open.ico",
        DEPOSIT_CLOSE: "deposit_close.ico",
        DETAILS: "details.ico",
        DIVIDEND: "dividend.ico",
        FEE: "fee.ico",
        INTEREST: "interest.ico",
        LIST: "list.ico",
        MERGER: "merger.ico",
        MINUS: "minus.ico",
        OK: "ok.ico",
        PLUS: "plus.ico",
        REMOVE: "remove.ico",
        SELL: "sell.ico",
        SPINOFF: "spinoff.ico",
        SWAP: "renaming.ico",                   # TODO dedicated icon for swaps (reuses the symbol-change glyph)
        SPLIT: "split.ico",
        STOCK_DIVIDEND: "dividend_stock.ico",
        STOCK_VESTING: "vesting.ico",
        SYMBOL_CHANGE: "renaming.ico",
        TAG: "tag.ico",
        TAX: "tax.ico",
        TOTAL: "total.ico",
        TRANSFER_IN: "transfer_in.ico",
        TRANSFER_OUT: "transfer_out.ico",
        TRANSFER_ASSET_IN: "transfer_asset_in.ico",
        TRANSFER_ASSET_OUT: "transfer_asset_out.ico",
        WITH_CREDIT: "with_credit.ico"
    }
    _icons = {}
    _flag_files = {
        FLAG_PT: "pt.png",
        FLAG_RU: "ru.png",
        FLAG_US: "en.png"
    }
    _flags = {
        'pt': FLAG_PT,
        'ru': FLAG_RU,
        'en': FLAG_US
    }

    # What an icon means, for the few that mean anything. A glyph listed here is drawn in its meaning's colour
    # instead of the palette's plain text colour; theme.py keeps that colour readable on whatever ground the
    # application is running against, so this table holds an intent and never a value.
    _icon_meanings = {
        BUY: Meaning.POSITIVE,
        PLUS: Meaning.POSITIVE,
        DIVIDEND: Meaning.POSITIVE,
        STOCK_DIVIDEND: Meaning.POSITIVE,
        STOCK_VESTING: Meaning.POSITIVE,
        BOND_INTEREST: Meaning.POSITIVE,
        BOND_AMORTIZATION: Meaning.POSITIVE,
        INTEREST: Meaning.POSITIVE,
        TRANSFER_IN: Meaning.POSITIVE,
        TRANSFER_ASSET_IN: Meaning.POSITIVE,
        OK: Meaning.POSITIVE,
        SELL: Meaning.NEGATIVE,
        MINUS: Meaning.NEGATIVE,
        FEE: Meaning.NEGATIVE,
        TAX: Meaning.NEGATIVE,
        TRANSFER_OUT: Meaning.NEGATIVE,
        TRANSFER_ASSET_OUT: Meaning.NEGATIVE,
        CANCEL: Meaning.NEGATIVE,
        REMOVE: Meaning.NEGATIVE,
        WITH_CREDIT: Meaning.WARNING
    }

    # initiates class loading all icons listed in self._icon_files from given directory img_path (should and
    # with a system directory separator)
    def __init__(self):
        super().__init__()
        if self._icons:     # Already loaded - nothing to do
            return
        img_path = JalSettings.path(JalSettings.PATH_ICONS)
        for icon_id, filename in self._icon_files.items():
            self._icons[icon_id] = self.load_glyph(img_path + ICON_PREFIX + filename,
                                                   self._icon_meanings.get(icon_id))
        for icon_id, filename in self._flag_files.items():
            self._icons[icon_id] = self.load_icon(img_path + FLAG_PREFIX + filename)
        # Logos that dynamically loaded modules ask for by name - a broker statement (aux_*) or a blockchain
        # fetcher (chain_*). They are keyed by filename as neither set is known before the modules are loaded.
        for filename in os.listdir(img_path):
            if re.match(f"^({AUX_PREFIX}|{CHAIN_PREFIX}).*", filename):
                self._icons[filename] = self.load_icon(img_path + filename)
        # Account-type glyphs and currency signs are keyed by filename because what wants them names the file
        # rather than a member of this class - an account type by JalAccount._TYPE_ICONS, a currency by its own
        # ticker - so load whatever is on disk. A currency JAL never heard of is given its sign by putting a file
        # into jal/img and changing nothing here.
        for filename in os.listdir(img_path):
            if re.match(f"^({ATYPE_PREFIX}|{MONEY_PREFIX}).*\\.ico$", filename):
                self._icons[filename] = self.load_glyph(img_path + filename)

    @staticmethod
    def load_icon(path) -> QIcon:
        icon = QIcon(path)
        if icon.isNull():
            logging.warning(f"Image file {path} not found")  # This error won't come to GUI as LogViewer is initialized later
        return icon

    # A glyph is an .ico file: a black shape on transparency, which carries no color of its own and takes the
    # palette's. The application's own logo is a .png and is a picture, not a glyph, so it is loaded untouched -
    # that is the whole difference between the two extensions in jal/img.
    @classmethod
    def load_glyph(cls, path, meaning=None) -> QIcon:
        icon = cls.load_icon(path)
        if icon.isNull() or not path.lower().endswith('.ico'):
            return icon
        return QIcon(JalIconEngine(icon, meaning))

    @classmethod
    def __class_getitem__(cls, key) -> QIcon:
        return cls._icons.get(key, QIcon())

    @classmethod
    def country_flag(cls, country_code) -> QIcon:
        if country_code not in cls._flags:
            return QIcon()
        return cls._icons[cls._flags[country_code]]

    # The sign of the currency with the given ticker ('USD' -> money_usd.ico), or an empty icon if the package
    # carries none for it. It marks a KIND of thing - every dollar account, listing or amount wears the same
    # sign - which is what makes it a glyph and not one of the pictures kept per element (see jal.db.icon).
    @classmethod
    def money_glyph(cls, ticker: str) -> QIcon:
        return cls._icons.get(MONEY_PREFIX + ticker.lower() + ".ico", QIcon())

    # Logo of a dynamically loaded module: the module names the image file it wants and the prefix says which
    # kind of module asks (AUX_PREFIX for broker statements, CHAIN_PREFIX for blockchain fetchers), so two
    # modules of different kinds may name their images alike. An unknown name gives an empty icon.
    @classmethod
    def module_icon(cls, prefix, icon_name) -> QIcon:
        return cls._icons.get(prefix + icon_name, QIcon())
