import logging
from PySide6.QtSql import QSqlQuery
from jal.db.helpers import db_connection


class JalSettings:
    def __init__(self):
        self.db = db_connection()

    def getValue(self, key, default=None):
        get_query = QSqlQuery(self.db)
        get_query.setForwardOnly(True)
        get_query.prepare("SELECT value FROM settings WHERE name=:key")

        value = default
        get_query.bindValue(":key", key)
        if not get_query.exec():
            if not default:
                logging.fatal(f"Failed to get settings for key='{key}'")
            return value
        if get_query.next():
            value = get_query.value(0)
        return value

    def setValue(self, key, value):
        set_query = QSqlQuery(self.db)
        set_query.prepare("INSERT OR REPLACE INTO settings(id, name, value) "
                          "VALUES((SELECT id FROM settings WHERE name=:key), :key, :value)")
        set_query.bindValue(":key", key)
        set_query.bindValue(":value", value)
        if not set_query.exec():
            logging.fatal(f"Failed to set settings key='{key}' to value='{value}'")
        self.db.commit()
