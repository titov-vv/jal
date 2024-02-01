import os
from PySide6.QtGui import QIcon
from jal.constants import Setup
from jal.db.helpers import get_app_path


ICON_PREFIX = "ui_"
class JalIcons:
    NONE = 0
    PLUS = 1
    MINUS = 2
    _icon_files = {
        PLUS: "plus.png",
        MINUS: "minus.png"
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
