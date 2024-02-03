import os
from enum import auto
from collections import UserDict
from PySide6.QtGui import QIcon
from jal.constants import Setup
from jal.db.helpers import get_app_path


ICON_PREFIX = "ui_"
class JalIcon(UserDict):
    NONE = auto()
    BOND_AMORTIZATION = auto()
    BOND_INTEREST = auto()
    BUY = auto()
    DELISTING = auto()
    DEPOSIT_OPEN = auto()
    DEPOSIT_CLOSE = auto()
    DIVIDEND = auto()
    FEE = auto()
    INTEREST = auto()
    MERGER = auto()
    MINUS = auto()
    PLUS = auto()
    SELL = auto()
    SPINOFF = auto()
    SPLIT = auto()
    STOCK_DIVIDEND = auto()
    STOCK_VESTING = auto()
    SYMBOL_CHANGE = auto()
    TAX = auto()
    TRANSFER_IN = auto()
    TRANSFER_OUT = auto()

    _icon_files = {
        BOND_AMORTIZATION: "amortization.ico",
        BOND_INTEREST: "coupon.ico",
        BUY: "buy.ico",
        DELISTING: "delisting.ico",
        DEPOSIT_OPEN: "deposit_open.ico",
        DEPOSIT_CLOSE: "deposit_close.ico",
        DIVIDEND: "dividend.ico",
        FEE: "fee.ico",
        INTEREST: "interest.ico",
        MERGER: "merger.ico",
        MINUS: "minus.ico",
        PLUS: "plus.ico",
        SELL: "sell.ico",
        SPINOFF: "spinoff.ico",
        SPLIT: "split.ico",
        STOCK_DIVIDEND: "dividend_stock.ico",
        STOCK_VESTING: "vesting.ico",
        SYMBOL_CHANGE: "renaming.ico",
        TAX: "tax.ico",
        TRANSFER_IN: "transfer_in.ico",
        TRANSFER_OUT: "transfer_out.ico"
    }
    _icons = {}

    # initiates class loading all icons listed in self._icon_files from given directory img_path (should and
    # with a system directory separator)
    def __init__(self):
        super().__init__()
        if self._icons:     # Already loaded - nothing to do
            return
        img_path = get_app_path() + Setup.ICONS_PATH + os.sep + ICON_PREFIX
        for icon_id, filename in self._icon_files.items():
            self._icons[icon_id] = QIcon(img_path + filename)

    @classmethod
    def __class_getitem__(cls, key) -> QIcon:
        if key not in cls._icons:
            return QIcon()
        return cls._icons[key]
