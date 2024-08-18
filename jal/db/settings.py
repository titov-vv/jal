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

    def getValue(self, key, default=None):
        value = self._read("SELECT value FROM settings WHERE name=:key", [(":key", key)])
        if value is None:
            value = default
        try:
            return int(value)   # Try to provide integer if conversion is possible
        except ValueError:
            return value

    def setValue(self, key, value):
        self._exec("INSERT OR REPLACE INTO settings(name, value) VALUES(:key, :value)",
                   [(":key", key), (":value", value)], commit=True)

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
