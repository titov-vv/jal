# Here reference goes from PYSIDE_DESIGNER_PLUGINS directory
from jal.db.db import JalDB
from jal.db.settings import JalSettings

from PySide6.QtGui import QIcon


# Designer shows this next to every jal widget in the widget box. There is no per-widget artwork, so all of
# them carry the application mark: it tells a form author that the entry is jal's, which is the only thing
# the graphic has to say - the widgets are already named and grouped under 'JAL widgets'.
# JalSettings.path() is only path arithmetic here (JalDB.get_app_path()), so it needs no open database.
def jal_widget_icon() -> QIcon:
    return QIcon(JalSettings.path(JalDB.PATH_ICONS) + "ui_jal.png")
