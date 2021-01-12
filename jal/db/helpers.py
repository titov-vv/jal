import logging
import sqlite3
from jal.constants import Setup
from PySide2.QtSql import QSql, QSqlDatabase, QSqlQuery

# No translation of the file because these routines might be used before QApplication initialization
class LedgerInitError:
    DbInitSuccess = 0
    EmptyDbInitialized = 1
    OutdatedDbSchema = 2
    NewerDbSchema = 3
    DbDriverFailure = 4
    _messages = {
        0: "No error",
        1: "Database was initialized. You need to start application again.",
        2: "Database schema version is outdated. Please execute update script.",
        3: "Unsupported database schema. Please update application",
        4: "Sqlite driver initialization failed."
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

def readSQLrecord(query, named = False):
    if named:
        values = {}
    else:
        values = []
    for i in range(query.record().count()):
        if named:
            values[query.record().fieldName(i)] = query.value(i)
        else:
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
    if not db.isValid():
        return None, LedgerInitError(LedgerInitError.DbDriverFailure)
    db.setDatabaseName(get_dbfilename(db_path))
    db.open()
    tables = db.tables(QSql.Tables)
    if not tables:
        db.close()
        connection_name = db.connectionName()
        init_db_from_sql(get_dbfilename(db_path), db_path + Setup.INIT_SCRIPT_PATH)
        QSqlDatabase.removeDatabase(connection_name)
        return None, LedgerInitError(LedgerInitError.EmptyDbInitialized)

    schema_version = readSQL(db, "SELECT value FROM settings WHERE name='SchemaVersion'")
    if schema_version < Setup.TARGET_SCHEMA:
        db.close()
        return None, LedgerInitError(LedgerInitError.OutdatedDbSchema)
    elif schema_version > Setup.TARGET_SCHEMA:
        db.close()
        return None, LedgerInitError(LedgerInitError.NewerDbSchema)

    _ = executeSQL(db, "PRAGMA foreign_keys = ON")

    return db, LedgerInitError(LedgerInitError.DbInitSuccess)

# -------------------------------------------------------------------------------------------------------------------
def init_db_from_sql(db_file, sql_file):
    with open(sql_file, 'r', encoding='utf-8') as sql_file:
        sql_text = sql_file.read()
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    cursor.executescript(sql_text)
    db.commit()
    db.close()

# -------------------------------------------------------------------------------------------------------------------
def get_language(db):
    language = ''
    if db:
        language = readSQL(db, "SELECT l.language FROM settings AS s "
                               "LEFT JOIN languages AS l ON s.value=l.id WHERE s.name='Language'")
    language = 'us' if language == '' else language
    return language

# -------------------------------------------------------------------------------------------------------------------
def get_base_currency(db):
    return readSQL(db, "SELECT value FROM settings WHERE name='BaseCurrency'")

# -------------------------------------------------------------------------------------------------------------------
def get_field_by_id_from_table(db, table_name, field_name, id):
    SQL = f"SELECT t.{field_name} FROM {table_name} AS t WHERE t.id = :id"
    return readSQL(db, SQL, [(":id", id)])

# -------------------------------------------------------------------------------------------------------------------
def get_category_name(db, category_id):
    return readSQL(db, "SELECT c.name FROM categories AS c WHERE c.id=:category_id", [(":category_id", category_id)])

# -------------------------------------------------------------------------------------------------------------------
def get_account_id(db, account_name):
    id = readSQL(db, "SELECT id FROM accounts WHERE name=:account_name", [(":account_name", account_name)])
    if id is None:
        id = 0
    return id

def get_account_name(db, account_id):
    return readSQL(db, "SELECT name FROM accounts WHERE id=:account_id", [(":account_id", account_id)])

# -------------------------------------------------------------------------------------------------------------------
def get_country_by_code(db, country_code):
    id = readSQL(db, "SELECT id FROM countries WHERE code=:code", [(":code", country_code)])
    if id is None:
        id = 0
    return id