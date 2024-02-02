import os
from PySide6.QtGui import QIcon
from jal.constants import Setup
from jal.db.helpers import get_app_path


ICON_PREFIX = "ui_"
class JalIcons:
    NONE = 0
    PLUS = 1
    MINUS = 2
    BUY = 3
    SELL = 4
    TRANSFER_IN = 5
    TRANSFER_OUT = 6
    FEE = 7
    INTEREST = 8
    MERGER = 9
    SPINOFF = 10
    SPLIT = 11
    TAX = 12
    _icon_files = {
        BUY: "buy.png",
        FEE: "fee.png",
        INTEREST: "interest.png",
        MERGER: "merger.png",
        MINUS: "minus.png",
        PLUS: "plus.png",
        SELL: "sell.png",
        SPINOFF: "spinoff.png",
        SPLIT: "split.png",
        TAX: "tax.png",
        TRANSFER_IN: "transfer_in.png",
        TRANSFER_OUT: "transfer_out.png"
    }
    _icons = {}

    # initiates class loading all icons listed in self._icon_files from given directory img_path (should and
    # with a system directory separator)
    def __init__(self):
        if self._icons:     # Already loaded - nothing to do
            return
        img_path = get_app_path() + Setup.ICONS_PATH + os.sep + ICON_PREFIX
        for icon_id, filename in self._icon_files.items():
            self._icons[icon_id] = QIcon(img_path + filename)

    def icon(self, id: int) -> QIcon:
        if id not in self._icons:
            return QIcon()
        return self._icons[id]
