import logging
from constants import Setup
from PySide2.QtSql import QSql, QSqlDatabase, QSqlQuery
from DB.backup_restore import loadDbFromSQL

# No translation of the file because these routines might be used before QApplication initialization
class LedgerInitError:
    DbInitSuccess = 0
    EmptyDbInitialized = 1
    WrongSchemaVersion = 2
    _messages = {
        0: "No error",
        1: "Database was initialized. You need to start application again.",
        2: "Database version mismatch. Can't start application."
    }

    def __init__(self, code):
        self.code = code
        self.message = self._messages[code]


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
    if query.next():
        return readSQLrecord(query)
    else:
        return None

def readSQLrecord(query):
    values = []
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
# This function:
# 1) checks that DB file is present and contains some data
#    if not - it will initialize DB with help of SQL-script
# 2) checks that DB looks like a valid one:
#    if schema version is invalid it will close DB
# Returns: db hanlder, LedgerInitError(code = 0 if db initialzied successfully)
def init_and_check_db(db_path):
    db = QSqlDatabase.addDatabase("QSQLITE")
    db.setDatabaseName(get_dbfilename(db_path))
    db.open()
    tables = db.tables(QSql.Tables)
    if not tables:
        db.close()
        loadDbFromSQL(get_dbfilename(db_path), db_path + Setup.INIT_SCRIPT_PATH)
        return None, LedgerInitError(LedgerInitError.EmptyDbInitialized)

    if readSQL(db, "SELECT value FROM settings WHERE name='SchemaVersion'") != Setup.TARGET_SCHEMA:
        db.close()
        return None, LedgerInitError(LedgerInitError.WrongSchemaVersion)
    return db, LedgerInitError(LedgerInitError.DbInitSuccess)

# -------------------------------------------------------------------------------------------------------------------
def get_base_currency(db):
    return readSQL(db, "SELECT value FROM settings WHERE name='BaseCurrency'")

# -------------------------------------------------------------------------------------------------------------------
def get_base_currency_name(db):
    return readSQL(db, "SELECT name FROM assets WHERE id = (SELECT value FROM settings WHERE name='BaseCurrency')")