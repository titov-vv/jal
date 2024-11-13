import logging
import os
import re
from enum import auto
from collections import UserDict
from PySide6.QtGui import QIcon, QPixmap
from jal.db.settings import JalSettings
from jal.db.tag import JalTag


ICON_PREFIX = "ui_"
FLAG_PREFIX = "flag_"
AUX_PREFIX = "aux_"

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

    # initiates class loading all icons listed in self._icon_files from given directory img_path (should and
    # with a system directory separator)
    def __init__(self):
        super().__init__()
        if self._icons:     # Already loaded - nothing to do
            return
        img_path = JalSettings.path(JalSettings.PATH_ICONS)
        for icon_id, filename in self._icon_files.items():
            self._icons[icon_id] = self.add_disabled_state(self.load_icon(img_path + ICON_PREFIX + filename))
        for icon_id, filename in self._flag_files.items():
            self._icons[icon_id] = self.load_icon(img_path + FLAG_PREFIX + filename)
        for filename in os.listdir(img_path):
            match = re.match(f"^{AUX_PREFIX}.*", filename)
            if match:
                self._icons[filename] = self.load_icon(img_path + filename)
        for tag_id, filename in JalTag.icon_files().items():
            self._icons[filename] = self.add_disabled_state(self.load_icon(img_path + filename))

    @staticmethod
    def load_icon(path) -> QIcon:
        icon = QIcon(path)
        if icon.isNull():
            logging.warning(f"Image file {path} not found")  # This error won't come to GUI as LogViewer is initialized later
        return icon

    @classmethod
    def __class_getitem__(cls, key) -> QIcon:
        return cls._icons.get(key, QIcon())

    @classmethod
    def country_flag(cls, country_code) -> QIcon:
        if country_code not in cls._flags:
            return QIcon()
        return cls._icons[cls._flags[country_code]]

    @classmethod
    def aux_icon(cls, icon_name) -> QIcon:
        filename = AUX_PREFIX + icon_name
        return cls._icons.get(filename, QIcon())

    # Iterates through all available images and creates a copy of images with adjusted alpha-channel (20% of initial value)
    # This new image is added to the icon as disabled state image
    def add_disabled_state(self, icon: QIcon) -> QIcon:
        disabled_icons = []
        for size in icon.availableSizes():
            icon_image = icon.pixmap(size).toImage()
            for y in range(icon_image.height()):
                for x in range(icon_image.width()):
                    pixel_color = icon_image.pixelColor(x, y)
                    pixel_color.setAlpha(pixel_color.alpha() / 5)
                    icon_image.setPixelColor(x, y, pixel_color)
            disabled_icons.append(QPixmap.fromImage(icon_image))
        for disabled_image in disabled_icons:
            icon.addPixmap(disabled_image, mode=QIcon.Mode.Disabled)
        return icon
