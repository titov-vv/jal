import os
from enum import auto
from jal.db.db import JalDB
from PySide6.QtCore import QStandardPaths, QFileInfo
from jal.constants import Setup

class FolderFor:
    Statement = auto()
    Report = auto()

class JalSettings(JalDB):
    __RECENT_PREFIX = "RecentFolder_"
    __folders = {
        FolderFor.Statement: "Statement",
        FolderFor.Report: "Report"
    }

    def __init__(self):
        super().__init__()

    @staticmethod
    def path(path_type) -> str:
        app_path = JalDB.get_app_path()
        if path_type == JalDB.PATH_APP:
            return app_path
        if path_type == JalDB.PATH_DB_FILE:
            return JalDB.get_db_path()
        if path_type == JalDB.PATH_LANG:
            return app_path + Setup.LANG_PATH + os.sep
        if path_type == JalDB.PATH_ICONS:
            return app_path + Setup.ICONS_PATH + os.sep
        if path_type == JalDB.PATH_LANG_FILE:
            return app_path + Setup.LANG_PATH + os.sep + JalSettings().getLanguage() + '.qm'
        if path_type == JalDB.PATH_TAX_REPORT_TEMPLATE:
            return app_path + Setup.EXPORT_PATH + os.sep + Setup.TAX_REPORT_PATH + os.sep
        if path_type == JalDB.PATH_TEMPLATES:
            return app_path + Setup.EXPORT_PATH + os.sep + Setup.TEMPLATE_PATH + os.sep

    #TODO Replace with new typed methods
    # Legacy untyped accessor: it guesses the type of the value and returns an int whenever the stored text
    # converts to one. Existing callers rely on that guess (a stored '1' is expected back as 1), so it stays,
    # but it must not be used for a value whose type matters - an all-digit API key would come back as an int.
    # Use getStr()/getInt()/getBool() below instead, they never guess.
    def getValue(self, key, default=None):
        value = self._read("SELECT value FROM settings WHERE name=:key", [(":key", key)])
        if value is None:
            return default   # The default is returned as it is: converting it here raised TypeError for None
        try:
            return int(value)   # Try to provide integer if conversion is possible
        except ValueError:
            return value

    # Typed accessors. Every value is stored as TEXT, so the type is decided by the caller and not by the
    # shape of the stored text. A value that doesn't convert is reported as the default rather than raising,
    # because a settings table edited by hand must never prevent the application from starting.
    def getStr(self, key, default: str = '') -> str:
        value = self._read("SELECT value FROM settings WHERE name=:key", [(":key", key)])
        return default if value is None else str(value)

    def getInt(self, key, default: int = 0) -> int:
        try:
            return int(self.getStr(key, str(default)))
        except ValueError:
            return default

    # '1'/'0' is the stored form, but any value that int() accepts is understood in order to keep the
    # settings that were written by the legacy setValue() readable.
    def getBool(self, key, default: bool = False) -> bool:
        return bool(self.getInt(key, int(default)))

    def setValue(self, key, value):
        if isinstance(value, bool):   # bool is a subclass of int and would be stored as 'True'/'False' otherwise
            value = int(value)
        self._exec("INSERT OR REPLACE INTO settings(name, value) VALUES(:key, :value)",
                   [(":key", key), (":value", str(value))], commit=True)

    # Returns 2-letter language code that corresponds to current 'Language' settings in DB
    def getLanguage(self):
        lang_id = self.getValue('Language', default=1)
        return self._read("SELECT language FROM languages WHERE id = :language_id", [(':language_id', lang_id)])

    # Set 'Language' setting in DB that corresponds to given 2-letter language code
    def setLanguage(self, language_code):
        lang_id = self._read("SELECT id FROM languages WHERE language = :language_code",
                             [(':language_code', language_code)])
        self.setValue('Language', lang_id)

    def getRecentFolder(self, folder_type: int, default: str=''):
        folder = self.getValue(self.__RECENT_PREFIX + self.__folders[folder_type])
        if not folder:
            folder = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        if not folder:
            folder = default
        return folder

    def setRecentFolder(self, folder_type: int, folder: str):
        file_info = QFileInfo(folder)
        if file_info.isDir():
            path = file_info.absoluteFilePath()
        else:
            path = file_info.absolutePath()
        self.setValue(self.__RECENT_PREFIX + self.__folders[folder_type], path)
