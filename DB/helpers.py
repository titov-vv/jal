from constants import *
from PySide2.QtCore import Qt, QMetaObject
from PySide2.QtSql import QSql, QSqlDatabase, QSqlQuery
from PySide2.QtWidgets import QMessageBox
from DB.bulk_db import loadDbFromSQL


def init_and_check_db(parent, db_path):
    db = QSqlDatabase.addDatabase("QSQLITE")
    db.setDatabaseName(db_path + DB_PATH)
    db.open()
    tables = db.tables(QSql.Tables)
    if not tables:
        db.close()
        loadDbFromSQL(db_path + DB_PATH, db_path + INIT_SCRIPT_PATH)
        QMessageBox().information(parent, parent.tr("Database initialized"),
                                  parent.tr("Database have been initialized.\n"
                                          "You need to restart the application.\n"
                                          "Application terminates now."),
                                  QMessageBox.Ok)
        _ = QMetaObject.invokeMethod(parent, "close", Qt.QueuedConnection)
        return None

    query = QSqlQuery(db)
    query.exec_("SELECT value FROM settings WHERE name='SchemaVersion'")
    query.next()
    if query.value(0) != TARGET_SCHEMA:
        db.close()
        QMessageBox().critical(parent, parent.tr("Database version mismatch"),
                               parent.tr("Database schema version is wrong"),
                               QMessageBox.Ok)
        _ = QMetaObject.invokeMethod(parent, "close", Qt.QueuedConnection)
        return None
    return db

