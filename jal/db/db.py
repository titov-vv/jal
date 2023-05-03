from typing import Union
import os
import sys
import re
import logging
import sqlparse
from pkg_resources import parse_version
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtSql import QSql, QSqlDatabase, QSqlQuery, QSqlTableModel

from jal.constants import Setup
from jal.db.helpers import get_dbfilename


# ----------------------------------------------------------------------------------------------------------------------
# No translation of the file because these routines might be used before QApplication initialization
class JalDBError:
    NoError = 0
    DbInitFailure = 1
    OutdatedSqlite = 2
    OutdatedDbSchema = 3
    NewerDbSchema = 4
    DbDriverFailure = 5
    NoDeltaFile = 6
    SQLFailure = 7
    _messages = {
        0: "No error",
        1: "Database initialization failure.",
        2: "You need SQLite version >= " + Setup.SQLITE_MIN_VERSION,
        3: "Database schema version is outdated. Please update it or use older application version.",
        4: "Unsupported database schema. Please update the application.",
        5: "Sqlite driver initialization failed.",
        6: "DB delta file not found.",
        7: "SQL command was executed with error."
    }

    def __init__(self, code, details=''):
        self.code = code
        self.message = self._messages[code]
        self.details = details


# ----------------------------------------------------------------------------------------------------------------------
class JalSqlError:
    def __init__(self, msg):
        self.messages = {
            'JAL_SQL_MSG_0001': self.tr("Investment account should have associated broker assigned"),
            'JAL_SQL_MSG_0002': self.tr("Can't delete predefined category"),
            'JAL_SQL_MSG_0003': self.tr("Incorrect currency assignment for an asset")
        }
        self.translations = {
            'FOREIGN KEY constraint failed': self.tr("Data are referenced in another place and can't be modified")
        }
        if msg[:4] == 'JAL_':
            self._message = self.messages[msg[:16]]
            self._custom = True
        elif msg in self.translations:
            self._message = self.translations[msg]
            self._custom = True
        else:
            self._message = msg
            self._custom = False

    def tr(self, text):
        return QApplication.translate("JalSQLerror", text)

    def show(self):
        if "pytest" in sys.modules:  # Throw exception if we are in test mode or handle it if we are live
            raise RuntimeError(self._message)
        QMessageBox().warning(None, self.tr("Database error"), self._message, QMessageBox.Ok)

    def custom(self):
        return self._custom

    def message(self):
        return self._message


# ----------------------------------------------------------------------------------------------------------------------
class JalDB:
    _tables = []
    _instances_with_cache = []

    # By default, db objects don't cache data. But if and object may cache db data we need to track it so parameter
    # 'cached' to be set to True. Such objects should implement invalidate_cache(), class_cache() methods also.
    def __init__(self, cached=False, **kwargs):
        if cached:
            self._instances_with_cache.append(self)
        super().__init__()

    def tr(self, text):
        return QApplication.translate("JalDB", text)

    # -------------------------------------------------------------------------------------------------------------------
    # This function:
    # 1) checks that DB file is present and contains some data
    #    if not - it will initialize DB with help of SQL-script
    # 2) checks that DB looks like a valid one:
    #    if schema version is invalid it will close DB
    # Returns: LedgerInitError(code == NoError(0) if db was initialized successfully)
    def init_db(self, db_path) -> JalDBError:
        db = QSqlDatabase.addDatabase("QSQLITE", Setup.DB_CONNECTION)
        if not db.isValid():
            return JalDBError(JalDBError.DbDriverFailure)
        db.setDatabaseName(get_dbfilename(db_path))
        db.setConnectOptions("QSQLITE_ENABLE_REGEXP=1")
        db.open()
        sqlite_version = self.get_engine_version()
        if parse_version(sqlite_version) < parse_version(Setup.SQLITE_MIN_VERSION):
            db.close()
            return JalDBError(JalDBError.OutdatedSqlite)
        JalDB._tables = db.tables(QSql.Tables) + db.tables(QSql.Views)  # Bitwise or somehow doesn't work here :(
        if not JalDB._tables:
            logging.info("Loading DB initialization script")
            error = self.run_sql_script(db_path + Setup.INIT_SCRIPT_PATH)
            if error.code != JalDBError.NoError:
                return error
        if self._read("SELECT value FROM settings WHERE name='CleanDB'") == 1:
            db.close()
            os.remove(get_dbfilename(db_path))
            db.open()
            error = self.run_sql_script(db_path + Setup.INIT_SCRIPT_PATH)
            if error.code != JalDBError.NoError:
                return error
        schema_version = self._read("SELECT value FROM settings WHERE name='SchemaVersion'")
        if schema_version < Setup.DB_REQUIRED_VERSION:
            db.close()
            return JalDBError(JalDBError.OutdatedDbSchema)
        elif schema_version > Setup.DB_REQUIRED_VERSION:
            db.close()
            return JalDBError(JalDBError.NewerDbSchema,
                              details=f"(expected: {Setup.DB_REQUIRED_VERSION}, got: {schema_version})")
        self.enable_fk(True)
        self.enable_triggers(True)

        return JalDBError(JalDBError.NoError)

    # ------------------------------------------------------------------------------------------------------------------
    # Returns current version of sqlite library
    def get_engine_version(self):
        return self._read("SELECT sqlite_version()")

    # Returns last inserted id
    def last_insert_id(self):
        return self._read("SELECT last_insert_rowid()")

    # ------------------------------------------------------------------------------------------------------------------
    # This function returns SQLite connection used by JAL or fails with RuntimeError exception
    @staticmethod
    def connection():
        db = QSqlDatabase.database(Setup.DB_CONNECTION)
        if not db.isValid():
            raise RuntimeError(f"DB connection '{Setup.DB_CONNECTION}' is invalid")
        if not db.isOpen():
            logging.fatal(f"DB connection '{Setup.DB_CONNECTION}' is not open")
        return db

    # Returns a name of current database file in use
    @classmethod
    def _db_path(cls) -> str:
        return cls.connection().databaseName()

    # -------------------------------------------------------------------------------------------------------------------
    # Executes an SQL query from given sql_text
    # params is a list of tuples (":param", value) which are used to prepare SQL query
    # Current transaction will be committed if 'commit' set to true
    # Parameter 'forward_only' may be used for optimization
    # return value - QSqlQuery object (to allow iteration through result)
    @classmethod
    def _exec(cls, sql_text, params=None, forward_only=True, commit=False):
        if params is None:
            params = []
        db = cls.connection()
        query = QSqlQuery(db)
        query.setForwardOnly(forward_only)
        if not query.prepare(sql_text):
            logging.error(f"SQL query preparation failure: '{query.lastError().text()}' for query '{sql_text}'")
            return None
        query_params = set(re.findall(r":(\w+)", sql_text, re.IGNORECASE))  # get all parameter names in query text
        assert len(query_params) == len(params), f"SQL: wrong number of parameters {params} for '{sql_text}'"
        for param in params:
            query.bindValue(param[0], param[1])
            assert query.boundValue(param[0]) == param[1], f"SQL: failed to assign parameter {param} in '{sql_text}'"
        if not query.exec():
            error = JalSqlError(query.lastError().text())
            if error.custom():
                error.show()
            else:
                logging.error(f"SQL failure: '{error.message()}' for query '{sql_text}' with params '{params}'")
            return None
        if commit:
            db.commit()
        return query

    # ------------------------------------------------------------------------------------------------------------------
    # Reads the result of 'sql_test' query from the database (with given params - the same as for _exec() method)
    # returns result of the query or None if result is empty
    # named = False: result is packed into a list of field values
    # named = True: result is packet into a dictionary with field names as keys
    # check_unique = True: checks that only 1 record was returned by query, otherwise returns None
    @classmethod
    def _read(cls, sql_text, params=None, named=False, check_unique=False):
        query = cls._exec(sql_text, params)
        if query.next():
            res = cls._read_record(query, named=named)
            if check_unique and query.next():
                return None  # More than one record in result when only one expected
            return res
        else:
            return None

    # ------------------------------------------------------------------------------------------------------------------
    # Method takes current active record of given query and returns its values as:
    # named = False: a list of field values
    # named = True: a dictionary with field names as keys
    @classmethod
    def _read_record(cls, query, named=False, cast=None):
        if cast is None:
            cast = []
        values = {} if named else []
        if cast:
            assert len(cast) == query.record().count()
        for i in range(query.record().count()):
            value = cast[i](query.value(i)) if cast else query.value(i)
            if named:
                values[query.record().fieldName(i)] = value
            else:
                values.append(value)
        if values:
            if len(values) == 1 and not named:
                return values[0]
            else:
                return values
        else:
            return None

    # ------------------------------------------------------------------------------------------------------------------
    def invalidate_cache(self):
        processed_cache_classes = set()   # a list of classes that were already invalidated and don't need extra action
        for item in self._instances_with_cache:
            if item.class_cache() and type(item) in processed_cache_classes:
                continue
            else:
                processed_cache_classes.add(type(item))
            item.invalidate_cache()

    # Method returns true if data are cached on a class level, not in every instance
    @classmethod
    def class_cache(cls) -> True:
        return False

    # ------------------------------------------------------------------------------------------------------------------
    # Enables DB triggers if enable == True and disables it otherwise
    def enable_triggers(self, enable):
        if enable:
            _ = self._exec("UPDATE settings SET value=1 WHERE name='TriggersEnabled'", commit=True)
        else:
            _ = self._exec("UPDATE settings SET value=0 WHERE name='TriggersEnabled'", commit=True)

    # ------------------------------------------------------------------------------------------------------------------
    # Set synchronous mode ON if synchronous == True and OFF it otherwise
    def set_synchronous(self, synchronous):
        if synchronous:
            _ = self._exec("PRAGMA synchronous = ON")
        else:
            _ = self._exec("PRAGMA synchronous = OFF")

    # ------------------------------------------------------------------------------------------------------------------
    # Enables DB foreign keys if enable == True and disables it otherwise
    def enable_fk(self, enable):
        if enable:
            _ = self._exec("PRAGMA foreign_keys = ON")
        else:
            _ = self._exec("PRAGMA foreign_keys = OFF")

    # Method loads sql script into database
    def run_sql_script(self, script_file) -> JalDBError:
        try:
            with open(script_file, 'r', encoding='utf-8') as sql_script:
                statements = sqlparse.split(sql_script)
                for statement in statements:
                    clean_statement = sqlparse.format(statement, strip_comments=True)
                    if self._exec(clean_statement, commit=False) is None:
                        _ = self._exec("ROLLBACK")
                        self.connection().close()
                        return JalDBError(JalDBError.SQLFailure, f"FAILED: {clean_statement}")
                    else:
                        logging.debug(f"EXECUTED OK:\n{clean_statement}")
        except FileNotFoundError:
            return JalDBError(JalDBError.NoDeltaFile, script_file)
        return JalDBError(JalDBError.NoError)

    # updates current db schema to the latest available with help of scripts in 'updates' folder
    def update_db_schema(self, db_path) -> JalDBError:
        if QMessageBox().warning(None, QApplication.translate('DB', "Database format is outdated"),
                                 QApplication.translate('DB', "Do you agree to upgrade your data to newer format?"),
                                 QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
            return JalDBError(JalDBError.OutdatedDbSchema)
        db = self.connection()
        version = self._read("SELECT value FROM settings WHERE name='SchemaVersion'")
        try:
            schema_version = int(version)
        except ValueError:
            return JalDBError(JalDBError.DbInitFailure, details=f"(db schema: {version}")
        for step in range(schema_version, Setup.DB_REQUIRED_VERSION):
            delta_file = db_path + Setup.UPDATES_PATH + os.sep + Setup.UPDATE_PREFIX + f"{step + 1}.sql"
            logging.info(f"Applying delta schema {step}->{step + 1} from {delta_file}")
            error = self.run_sql_script(delta_file)
            if error.code != JalDBError.NoError:
                db.close()
                return error
        return JalDBError(JalDBError.NoError)

    def commit(self):
        self.connection().commit()

    # This method creates a db record in 'table' name that describes relevant operation.
    # 'data' is a dict that contains operation data and dict 'fields' describes it having
    # 'mandatory'=True if this piece must be present, 'validation'=True if it is used to check if operation is
    # present in database already (and 'default' is used for this check if no value provided in 'data')
    def create_operation(self, table_name, fields, data):
        self.validate_operation_data(table_name, fields, data)
        oid = self.locate_operation(table_name, fields, data)
        if oid:
            logging.warning(self.tr("Operation already present in db and was skipped: ") + f"{table_name}, {data}")
            return oid
        else:
            oid = self.insert_operation(table_name, fields, data)
        children = [x for x in fields if 'children' in fields[x] and fields[x]['children']]
        for child in children:
            for item in data[child]:
                item[fields[child]['child_pid']] = oid
                self.create_operation(fields[child]['child_table'], fields[child]['child_fields'], item)
        return oid

    # Verify that 'data' contains no more fields than described in 'fields'
    # Next it checks that 'data' has all fields described with 'mandatory'=True in 'fields'
    # TODO Add datatype validation
    def validate_operation_data(self, table_name, fields, data):
        if 'id' in data:
            data.pop('id')
        delta = set(data.keys()) - set(fields.keys())
        if len(delta):
            raise ValueError(f"Extra field(s) {delta} in {data} for table {table_name}")
        for field in fields:
            if fields[field]['mandatory'] and field not in data:
                raise KeyError(f"Mandatory field '{field}' for table '{table_name}' is missing in {data}")

    # Returns operation_id if given operation is present in 'table_name' already and 0 if not
    # Check happens based on field values that marked with 'validation'=True in 'fields' dict
    def locate_operation(self, table_name, fields, data) -> int:
        query_text = f"SELECT id FROM {table_name} WHERE "
        params = []
        validation_fields = [x for x in fields if 'validation' in fields[x] and fields[x]['validation']]
        if not validation_fields:
            return 0
        for field in validation_fields:
            if field not in data:
                data[field] = fields[field]['default']   # set to default value
            if data[field] is None:
                query_text += f"{field} IS NULL AND "
            else:
                query_text += f"{field} = :{field} AND "
                params.append((f":{field}", data[field]))
        query_text = query_text[:-len(" AND ")]   # cut extra tail
        oid = self._read(query_text, params)
        if oid:
            return int(oid)
        return 0

    # Method stores given operation in the database 'table_name'.
    # Returns 'id' of inserted operation.
    def insert_operation(self, table_name, fields, data) -> int:
        query_text = f"INSERT INTO {table_name} ("
        params = []
        values_text = "VALUES ("
        for field in fields:
            if 'children' in fields[field] and fields[field]['children']:
                continue   # Skip children for separate processing by create_operation()
            if field in data:
                query_text += f"{field}, "
                values_text += f":{field}, "
                params.append((f":{field}", data[field]))
        query_text = query_text[:-2] + ") " + values_text[:-2] + ")"
        query = self._exec(query_text, params, commit=True)
        return query.lastInsertId()


# -------------------------------------------------------------------------------------------------------------------
# Subclassing to hide db connection details
class JalModel(QSqlTableModel, JalDB):
    def __init__(self, parent, table_name):
        super().__init__(parent=parent, db=self.connection())
        self.setTable(table_name)
        self._table = table_name

    # Returns value of 'field_name' where 'key_field' is equal to 'search_value'
    def get_value(self, field_name: str, key_field: str, search_value: Union[int, str]) -> str:
        if ' ' in field_name or ' ' in key_field:
            return ''
        if type(search_value) == str:
            search_value = "'" + search_value + "'"   # Enclose string into quotes
        self.setFilter(f"{key_field}={search_value}")
        self.select()
        result = self.record(0).field(field_name).value()
        self.setFilter('')
        self.select()
        return result
