import logging
from PySide2.QtSql import QSqlDatabase, QSqlQuery
from jal.constants import Setup


class JalSettings:
    def __init__(self):
        self.db = QSqlDatabase.database(Setup.DB_CONNECTION)
        if not self.db.isValid():
            self.db = None
            logging.fatal("DB connection is invalid")
            return
        if not self.db.isOpen():
            self.db = None
            logging.fatal("DB connection is not open")
            return

    def getValue(self, key, default=None):
        get_query = QSqlQuery(self.db)
        get_query.setForwardOnly(True)
        get_query.prepare("SELECT value FROM settings WHERE name=:key")

        value = default
        get_query.bindValue(":key", key)
        if not get_query.exec_():
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
        if not set_query.exec_():
            logging.fatal(f"Failed to set settings key='{key}' to value='{value}'")
        self.db.commit()
