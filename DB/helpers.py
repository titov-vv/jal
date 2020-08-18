import logging
from constants import Setup
from PySide2.QtCore import Qt, QMetaObject
from PySide2.QtSql import QSql, QSqlDatabase, QSqlQuery
from PySide2.QtWidgets import QMessageBox
from DB.bulk_db import loadDbFromSQL

# -------------------------------------------------------------------------------------------------------------------
def get_dbfilename(app_path):
    return app_path + Setup.DB_PATH

# -------------------------------------------------------------------------------------------------------------------
# prepares SQL query from given sql_text
# params_list is a list of tuples (":param", value) which are used to prepare SQL query
# return value - QSqlQuery object (to allow iteration through result)
def executeSQL(db, sql_text, params = [], forward_only = True):
    query = QSqlQuery(db)
    query.setForwardOnly(forward_only)
    if not query.prepare(sql_text):
        logging.error(f"SQL prep: '{query.lastError().text()}' for query '{sql_text}' with params '{params}'")
        return None
    for param in params:
        query.bindValue(param[0], param[1])
    if not query.exec_():
        logging.error(f"SQL exec: '{query.lastError().text()}' for query '{sql_text}' with params '{params}'")
        return None
    return query

# -------------------------------------------------------------------------------------------------------------------
# the same as executeSQL() but after query execution it takes first line of it
# and packs all field values in a list to return
def readSQL(db, sql_text, params = []):
    query = QSqlQuery(db)
    query.setForwardOnly(True)
    if not query.prepare(sql_text):
        logging.error(f"SQL prep: '{query.lastError().text()}' for query '{sql_text}' with params '{params}'")
        return None
    for param in params:
        query.bindValue(param[0], param[1])
    if not query.exec_():
        logging.error(f"SQL exec: '{query.lastError().text()}' for query '{sql_text}' with params '{params}'")
        return None
    values = []
    if query.next():
        for i in range(query.record().count()):
            values.append(query.value(i))
    if values:
        if len(values) == 1:
            return values[0]
        else:
            return values
    else:
        return None

# -------------------------------------------------------------------------------------------------------------------
def init_and_check_db(parent, db_path):
    db = QSqlDatabase.addDatabase("QSQLITE")
    db.setDatabaseName(get_dbfilename(db_path))
    db.open()
    tables = db.tables(QSql.Tables)
    if not tables:
        db.close()
        loadDbFromSQL(get_dbfilename(db_path), db_path + Setup.INIT_SCRIPT_PATH)
        QMessageBox().information(parent, parent.tr("Database initialized"),
                                  parent.tr("Database have been initialized.\n"
                                          "You need to restart the application.\n"
                                          "Application terminates now."),
                                  QMessageBox.Ok)
        _ = QMetaObject.invokeMethod(parent, "close", Qt.QueuedConnection)
        return None

    if readSQL(db, "SELECT value FROM settings WHERE name='SchemaVersion'") != Setup.TARGET_SCHEMA:
        db.close()
        QMessageBox().critical(parent, parent.tr("Database version mismatch"),
                               parent.tr("Database schema version is wrong"),
                               QMessageBox.Ok)
        _ = QMetaObject.invokeMethod(parent, "close", Qt.QueuedConnection)
        return None
    return db

# -------------------------------------------------------------------------------------------------------------------
def get_base_currency(db):
    return readSQL(db, "SELECT value FROM settings WHERE name='BaseCurrency'")

# -------------------------------------------------------------------------------------------------------------------
def get_base_currency_name(db):
    return readSQL(db, "SELECT name FROM assets WHERE id = (SELECT value FROM settings WHERE name='BaseCurrency')")