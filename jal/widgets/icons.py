import os
from collections import UserDict
from PySide6.QtGui import QIcon
from jal.constants import Setup
from jal.db.helpers import get_app_path


ICON_PREFIX = "ui_"
class JalIcon(UserDict):
    NONE = 0
    BOND_AMORTIZATION = 1
    BOND_INTEREST = 2
    BUY = 3
    DELISTING = 4
    DEPOSIT_OPEN = 5
    DEPOSIT_CLOSE = 6
    DIVIDEND = 7
    FEE = 8
    INTEREST = 9
    MERGER = 10
    MINUS = 11
    PLUS = 12
    SELL = 13
    SPINOFF = 14
    SPLIT = 15
    STOCK_DIVIDEND = 16
    STOCK_VESTING = 17
    SYMBOL_CHANGE = 18
    TAX = 19
    TRANSFER_IN = 20
    TRANSFER_OUT = 21

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
