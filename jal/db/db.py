import os
import logging
import sqlparse
from datetime import datetime
from pkg_resources import parse_version
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtSql import QSql, QSqlDatabase

from jal.constants import Setup, BookAccount, PredefindedAccountType, AssetData, MarketDataFeed, PredefinedAsset
from jal.db.helpers import db_connection, executeSQL, readSQL, get_country_by_code, get_dbfilename, db_triggers_enable
from jal.db.settings import JalSettings


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
class JalDB:
    def __init__(self):
        pass

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
        sqlite_version = readSQL("SELECT sqlite_version()")
        if parse_version(sqlite_version) < parse_version(Setup.SQLITE_MIN_VERSION):
            db.close()
            return JalDBError(JalDBError.OutdatedSqlite)
        tables = db.tables(QSql.Tables)
        if not tables:
            logging.info("Loading DB initialization script")
            error = self.run_sql_script(db_path + Setup.INIT_SCRIPT_PATH)
            if error.code != JalDBError.NoError:
                return error
        schema_version = JalSettings().getValue('SchemaVersion')
        if schema_version < Setup.TARGET_SCHEMA:
            db.close()
            return JalDBError(JalDBError.OutdatedDbSchema)
        elif schema_version > Setup.TARGET_SCHEMA:
            db.close()
            return JalDBError(JalDBError.NewerDbSchema)

        _ = executeSQL("PRAGMA foreign_keys = ON")
        db_triggers_enable()

        return JalDBError(JalDBError.NoError)

    # Method loads sql script into database
    def run_sql_script(self, script_file) -> JalDBError:
        try:
            with open(script_file, 'r', encoding='utf-8') as sql_script:
                statements = sqlparse.split(sql_script)
                for statement in statements:
                    clean_statement = sqlparse.format(statement, strip_comments=True)
                    if executeSQL(clean_statement, commit=False) is None:
                        _ = executeSQL("ROLLBACK")
                        db_connection().close()
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
        db = db_connection()
        version = readSQL("SELECT value FROM settings WHERE name='SchemaVersion'")
        try:
            schema_version = int(version)
        except ValueError:
            return JalDBError(JalDBError.DbInitFailure)
        for step in range(schema_version, Setup.TARGET_SCHEMA):
            delta_file = db_path + Setup.UPDATES_PATH + os.sep + Setup.UPDATE_PREFIX + f"{step + 1}.sql"
            logging.info(f"Applying delta schema {step}->{step + 1} from {delta_file}")
            error = self.run_sql_script(delta_file)
            if error.code != JalDBError.NoError:
                db.close()
                return error
        return JalDBError(JalDBError.NoError)

    def commit(self):
        db_connection().commit()

    def set_view_param(self, view_name, param_name, param_type, value):
        fields = {int: "value_i", float: "value_f", str: "value_t"}
        field_name = fields[param_type]
        sql = f"UPDATE view_params SET {field_name}=:value WHERE view_name=:view AND param_name=:param"
        _ = executeSQL(sql, [(":value", value), (":view", view_name), (":param", param_name)])

    def get_language_id(self, language_code):
        return readSQL("SELECT id FROM languages WHERE language = :language_code", [(':language_code', language_code)])

    def get_language_code(self, language_id):
        return readSQL("SELECT language FROM languages WHERE id = :language_id", [(':language_id', language_id)])

    def get_asset_name(self, asset_id, full=False):
        if full:
            return readSQL("SELECT full_name FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
        else:   # FIXME Below query may return several symbols
            return readSQL("SELECT symbol FROM assets AS a LEFT JOIN asset_tickers AS s "   
                           "ON s.asset_id=a.id AND s.active=1 WHERE a.id=:asset_id", [(":asset_id", asset_id)])

    def get_asset_type(self, asset_id):
        return readSQL("SELECT type_id FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])

    def get_asset_country(self, asset_id):
        return readSQL("SELECT c.name FROM assets AS a LEFT JOIN countries AS c ON c.id=a.country_id "
                       "WHERE a.id=:asset_id", [(":asset_id", asset_id)])

    def get_account_name(self, account_id):
        return readSQL("SELECT name FROM accounts WHERE id=:account_id", [(":account_id", account_id)])

    # Searches for account_id by account number and optional currency
    # Returns: account_id or None if no account was found
    def get_account_id(self, accountNumber, accountCurrency=''):
        if accountCurrency:
            account_id = readSQL("SELECT a.id FROM accounts AS a "
                                 "LEFT JOIN currencies AS c ON c.id=a.currency_id "
                                 "WHERE a.number=:account_number AND c.symbol=:currency_name",
                                 [(":account_number", accountNumber), (":currency_name", accountCurrency)],
                                 check_unique=True)
        else:
            account_id = readSQL("SELECT a.id FROM accounts AS a WHERE a.number=:account_number",
                                 [(":account_number", accountNumber)],
                                 check_unique=True)
        return account_id

    def find_account(self, account_number, currency_code):
        return readSQL("SELECT id FROM accounts WHERE number=:account_number AND currency_id=:currency",
                       [(":account_number", account_number), (":currency", currency_code)], check_unique=True)

    def add_account(self, account_number, currency_id, account_type=PredefindedAccountType.Investment):
        account_id = self.find_account(account_number, currency_id)
        if account_id:  # Account already exists
            logging.warning(self.tr("Account already exists: ") +
                            f"{account_number} ({self.get_asset_name(currency_id)})")
            return account_id
        currency = self.get_asset_name(currency_id)
        account = readSQL("SELECT a.name, a.organization_id, a.country_id, c.symbol AS currency FROM accounts a "
                          "LEFT JOIN assets_ext c ON c.id=a.currency_id WHERE a.number=:number LIMIT 1",
                          [(":number", account_number)], named=True)
        if account:  # Account with the same number but different currency exists
            if account['name'][-len(account['currency']):] == account['currency']:
                new_name = account['name'][:-len(account['currency'])] + currency
            else:
                new_name = account['name'] + '.' + currency
            query = executeSQL(
                "INSERT INTO accounts (type_id, name, active, number, currency_id, organization_id, country_id) "
                "SELECT a.type_id, :new_name, a.active, a.number, :currency_id, a.organization_id, a.country_id "
                "FROM accounts AS a LEFT JOIN assets AS c ON c.id=:currency_id "
                "WHERE number=:account_number LIMIT 1",
                [(":account_number", account_number), (":currency_id", currency_id), (":new_name", new_name)])
            return query.lastInsertId()

        bank_name = self.tr("Bank for #" + account_number)
        bank_id = readSQL("SELECT id FROM agents WHERE name=:bank_name", [(":bank_name", bank_name)])
        if bank_id is None:
            query = executeSQL("INSERT INTO agents (pid, name) VALUES (0, :bank_name)", [(":bank_name", bank_name)])
            bank_id = query.lastInsertId()
        query = executeSQL("INSERT INTO accounts (type_id, name, active, number, currency_id, organization_id) "
                           "VALUES(:type, :name, 1, :number, :currency, :bank)",
                           [(":type", account_type), (":name", account_number+'.'+currency),
                            (":number", account_number), (":currency", currency_id), (":bank", bank_id)])
        return query.lastInsertId()

    def get_account_currency(self, account_id):
        return readSQL("SELECT currency_id FROM accounts WHERE id=:account_id", [(":account_id", account_id)])

    def get_account_bank(self, account_id):
        return readSQL("SELECT organization_id FROM accounts WHERE id=:account_id", [(":account_id", account_id)])

    # Searches for asset_id in database based on keys available in search data:
    # first by 'isin', then by 'reg_number', next by 'symbol' and other
    # Returns: asset_id or None if not found
    def get_asset_id(self, search_data):
        asset_id = None
        if 'isin' in search_data and search_data['isin']:
            if 'symbol' in search_data and search_data['symbol']:
                return readSQL("SELECT id FROM assets_ext WHERE (isin=:isin OR isin='') AND symbol=:symbol",
                               [(":isin", search_data['isin']), (":symbol", search_data['symbol'])])
            else:
                return readSQL("SELECT id FROM assets WHERE isin=:isin", [(":isin", search_data['isin'])])
        if asset_id is None and 'reg_number' in search_data and search_data['reg_number']:
            asset_id = readSQL("SELECT asset_id FROM asset_data WHERE datatype=:datatype AND value=:reg_number",
                               [(":datatype", AssetData.RegistrationCode), (":reg_number", search_data['reg_number'])])
        if asset_id is None and 'symbol' in search_data and search_data['symbol']:
            if 'type' in search_data:
                if 'expiry' in search_data:
                    asset_id = readSQL("SELECT a.id FROM assets_ext a "
                                       "LEFT JOIN asset_data d ON a.id=d.asset_id AND d.datatype=:datatype "
                                       "WHERE symbol=:symbol COLLATE NOCASE AND type_id=:type AND value=:value",
                                       [(":datatype", AssetData.ExpiryDate), (":symbol", search_data['symbol']),
                                        (":type", search_data['type']), (":value", search_data['expiry'])])
                else:
                    asset_id = readSQL("SELECT id FROM assets_ext "
                                       "WHERE symbol=:symbol COLLATE NOCASE and type_id=:type",
                                       [(":symbol", search_data['symbol']), (":type", search_data['type'])])
            else:
                asset_id = readSQL("SELECT id FROM assets_ext WHERE symbol=:symbol COLLATE NOCASE",
                                   [(":symbol", search_data['symbol'])])
        if asset_id is None and 'name' in search_data and search_data['name']:
            asset_id = readSQL("SELECT id FROM assets_ext WHERE full_name=:name COLLATE NOCASE",
                               [(":name", search_data['name'])])
        return asset_id

    # get asset quotation for given currency and timestamp
    # if exact is False get's last available quotation before timestamp
    def get_quote(self, asset_id, currency_id, timestamp, exact=True):
        if exact:
            return readSQL("SELECT quote FROM quotes WHERE asset_id=:asset_id "
                           "AND currency_id=:currency_id AND timestamp=:timestamp",
                           [(":asset_id", asset_id), (":currency_id", currency_id), (":timestamp", timestamp)])
        else:
            return readSQL("SELECT quote FROM quotes WHERE asset_id=:asset_id AND currency_id=:currency_id "
                           "AND timestamp<=:timestamp ORDER BY timestamp DESC LIMIT 1",
                           [(":asset_id", asset_id), (":currency_id", currency_id), (":timestamp", timestamp)])

    # Set quotations for given asset_id and currency_id
    # quotations is a list of {'timestamp', 'quote'} values
    def update_quotes(self, asset_id, currency_id, quotations):
        data = [x for x in quotations if x['timestamp'] is not None and x['quote'] is not None]  # Drop Nones
        if data:
            for quote in quotations:
                _ = executeSQL("INSERT OR REPLACE INTO quotes (asset_id, currency_id, timestamp, quote) "
                               "VALUES(:asset_id, :currency_id, :timestamp, :quote)",
                               [(":asset_id", asset_id), (":currency_id", currency_id),
                                (":timestamp", quote['timestamp']), (":quote", quote['quote'])])
            begin = min(data, key=lambda x: x['timestamp'])['timestamp']
            end = max(data, key=lambda x: x['timestamp'])['timestamp']
            logging.info(self.tr("Quotations were updated: ") +
                         f"{self.get_asset_name(asset_id)} ({self.get_asset_name(currency_id)}) " 
                         f"{datetime.utcfromtimestamp(begin).strftime('%d/%m/%Y')} - "
                         f"{datetime.utcfromtimestamp(end).strftime('%d/%m/%Y')}")

    def add_asset(self, asset_type, name, isin, country_code=''):
        country_id = get_country_by_code(country_code)
        query = executeSQL("INSERT INTO assets (type_id, full_name, isin, country_id) "
                           "VALUES (:type, :full_name, :isin, :country_id)",
                           [(":type", asset_type), (":full_name", name),
                            (":isin", isin), (":country_id", country_id)], commit=True)
        return query.lastInsertId()

    def add_symbol(self, asset_id, symbol, currency, note, data_source=MarketDataFeed.NA):
        existing = readSQL("SELECT id, symbol, description, quote_source FROM asset_tickers "
                           "WHERE asset_id=:asset_id AND symbol=:symbol AND currency_id=:currency",
                           [(":asset_id", asset_id), (":symbol", symbol), (":currency", currency)], named=True)
        if existing is None:   # Deactivate old symbols and create a new one
            _ = executeSQL("UPDATE asset_tickers SET active=0 WHERE asset_id=:asset_id AND currency_id=:currency",
                           [(":asset_id", asset_id), (":currency", currency)])
            _ = executeSQL("INSERT INTO asset_tickers (asset_id, symbol, currency_id, description, quote_source) "
                           "VALUES (:asset_id, :symbol, :currency, :note, :data_source)",
                           [(":asset_id", asset_id), (":symbol", symbol), (":currency", currency),
                            (":note", note), (":data_source", data_source)])
        else:   # Update data for existing symbol
            if not existing['description']:
                _ = executeSQL("UPDATE asset_tickers SET description=:note WHERE id=:id",
                               [(":note", note), (":id", existing['id'])])
            if existing['quote_source'] == MarketDataFeed.NA:
                _ = executeSQL("UPDATE asset_tickers SET quote_source=:data_source WHERE id=:id",
                               [(":data_source", data_source), (":id", existing['id'])])

    def update_asset_data(self, asset_id, data):
        asset = readSQL("SELECT type_id, isin, full_name FROM assets WHERE id=:asset_id",
                        [(":asset_id", asset_id)], named=True)
        if asset is None:
            logging.warning(self.tr("Asset not found for update: ") + f"{data}")
            return
        if 'isin' in data and data['isin']:
            if asset['isin']:
                if asset['isin'] != data['isin']:
                    logging.error(self.tr("Unexpected attempt to update ISIN for ")
                                  + f"{self.get_asset_name(asset_id)}: {asset['isin']} -> {data['isin']}")
            else:
                _ = executeSQL("UPDATE assets SET isin=:new_isin WHERE id=:asset_id",
                               [(":new_isin", data['isin']), (":asset_id", asset_id)])
        if 'name' in data and data['name']:
            if not asset['full_name']:
                _ = executeSQL("UPDATE assets SET full_name=:new_name WHERE id=:asset_id",
                               [(":new_name", data['name']), (":asset_id", asset_id)])
        if 'country' in data and data['country']:
            country_id, country_code = readSQL("SELECT a.country_id, c.code FROM assets AS a LEFT JOIN countries AS c "
                                               "ON a.country_id=c.id WHERE a.id=:asset_id", [(":asset_id", asset_id)])
            if (country_id == 0) or (country_code.lower() != data['country'].lower()):
                new_country_id = get_country_by_code(data['country'])
                _ = executeSQL("UPDATE assets SET country_id=:new_country_id WHERE id=:asset_id",
                               [(":new_country_id", new_country_id), (":asset_id", asset_id)])
                if country_id != 0:
                    logging.info(self.tr("Country updated for ")
                                 + f"{self.get_asset_name(asset_id)}: {country_code} -> {data['country']}")
        if 'reg_number' in data and data['reg_number']:
            reg_number = readSQL("SELECT value FROM asset_data WHERE datatype=:datatype AND asset_id=:asset_id",
                                 [(":datatype", AssetData.RegistrationCode), (":asset_id", asset_id)])
            if reg_number != data['reg_number']:
                _ = executeSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                               "VALUES(:asset_id, :datatype, :reg_number)",
                               [(":asset_id", asset_id), (":datatype", AssetData.RegistrationCode),
                                (":reg_number", data['reg_number'])])
                if reg_number:
                    logging.info(self.tr("Reg.number updated for ")
                                 + f"{self.get_asset_name(asset_id)}: {reg_number} -> {data['reg_number']}")
        if 'expiry' in data and data['expiry']:
            _ = executeSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                           "VALUES(:asset_id, :datatype, :expiry)",
                           [(":asset_id", asset_id), (":datatype", AssetData.ExpiryDate),
                            (":expiry", data['expiry'])])
        if 'principal' in data and asset['type_id'] == PredefinedAsset.Bond:
            try:
                principal = float(data['principal'])
                if principal > 0:
                    _ = executeSQL("INSERT OR REPLACE INTO asset_data(asset_id, datatype, value) "
                                   "VALUES(:asset_id, :datatype, :principal)",
                                   [(":asset_id", asset_id), (":datatype", AssetData.PrincipalValue),
                                    (":principal", principal)])
            except ValueError:
                pass

    def add_dividend(self, subtype, timestamp, account_id, asset_id, amount, note, trade_number='',
                     tax=0.0, price=None):
        id = readSQL("SELECT id FROM dividends WHERE timestamp=:timestamp AND type=:subtype AND account_id=:account_id "
                     "AND asset_id=:asset_id AND amount=:amount AND note=:note",
                     [(":timestamp", timestamp), (":subtype", subtype), (":account_id", account_id),
                      (":asset_id", asset_id), (":amount", amount), (":note", note)])
        if id:
            logging.info(self.tr("Dividend already exists: ") + f"{note}")
            return
        _ = executeSQL("INSERT INTO dividends (timestamp, number, type, account_id, asset_id, amount, tax, note) "
                       "VALUES (:timestamp, :number, :subtype, :account_id, :asset_id, :amount, :tax, :note)",
                       [(":timestamp", timestamp), (":number", trade_number), (":subtype", subtype),
                        (":account_id", account_id), (":asset_id", asset_id), (":amount", amount),
                        (":tax", tax), (":note", note)],
                       commit=True)
        if price is not None:
            self.update_quotes(asset_id, self.get_account_currency(account_id),
                               [{'timestamp': timestamp, 'quote': price}])

    def update_dividend_tax(self, dividend_id, new_tax):
        _ = executeSQL("UPDATE dividends SET tax=:tax WHERE id=:dividend_id",
                       [(":dividend_id", dividend_id), (":tax", new_tax)], commit=True)

    def add_trade(self, account_id, asset_id, timestamp, settlement, number, qty, price, fee, note=''):
        trade_id = readSQL("SELECT id FROM trades "
                           "WHERE timestamp=:timestamp AND asset_id = :asset "
                           "AND account_id = :account AND number = :number AND qty = :qty AND price = :price",
                           [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                            (":number", number), (":qty", qty), (":price", price)])
        if trade_id:
            logging.info(self.tr("Trade already exists: #") + f"{number}")
            return

        _ = executeSQL("INSERT INTO trades (timestamp, settlement, number, account_id, asset_id, qty, price, fee, note)"
                       " VALUES (:timestamp, :settlement, :number, :account, :asset, :qty, :price, :fee, :note)",
                       [(":timestamp", timestamp), (":settlement", settlement), (":number", number),
                        (":account", account_id), (":asset", asset_id), (":qty", float(qty)),
                        (":price", float(price)), (":fee", float(fee)), (":note", note)], commit=True)

    def del_trade(self, account_id, asset_id, timestamp, _settlement, number, qty, price, _fee):
        _ = executeSQL("DELETE FROM trades "
                       "WHERE timestamp=:timestamp AND asset_id=:asset "
                       "AND account_id=:account AND number=:number AND qty=:qty AND price=:price",
                       [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                        (":number", number), (":qty", -qty), (":price", price)], commit=True)

    def add_transfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note, asset=None):
        if asset is not None:
            transfer_id = readSQL("SELECT id FROM transfers WHERE withdrawal_timestamp=:timestamp "
                                  "AND withdrawal_account=:from_acc_id AND deposit_account=:to_acc_id "
                                  "AND withdrawal=:f_amount AND deposit=:t_amount AND asset=:asset",
                                  [(":timestamp", timestamp), (":from_acc_id", f_acc_id), (":to_acc_id", t_acc_id),
                                   (":f_amount", f_amount), (":t_amount", t_amount), (":asset", asset)])
            if transfer_id:
                logging.info(self.tr("Transfer/Exchange already exists: ") + f"{f_amount}->{t_amount}")
                return
        else:
            transfer_id = readSQL("SELECT id FROM transfers WHERE withdrawal_timestamp=:timestamp "
                                  "AND withdrawal_account=:from_acc_id AND deposit_account=:to_acc_id "
                                  "AND withdrawal=:f_amount AND deposit=:t_amount",
                                  [(":timestamp", timestamp), (":from_acc_id", f_acc_id), (":to_acc_id", t_acc_id),
                                   (":f_amount", f_amount), (":t_amount", t_amount)])
            if transfer_id:
                logging.info(self.tr("Transfer/Exchange already exists: ") + f"{f_amount}->{t_amount}")
                return
        if abs(fee) > Setup.CALC_TOLERANCE:
            _ = executeSQL("INSERT INTO transfers (withdrawal_timestamp, withdrawal_account, withdrawal, "
                           "deposit_timestamp, deposit_account, deposit, fee_account, fee, note, asset) "
                           "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, "
                           ":fee_acc_id, :fee_amount, :note, :asset)",
                           [(":timestamp", timestamp), (":f_acc_id", f_acc_id), (":t_acc_id", t_acc_id),
                            (":f_amount", f_amount), (":t_amount", t_amount), (":fee_acc_id", fee_acc_id),
                            (":fee_amount", fee), (":note", note), (":asset", asset)], commit=True)
        else:
            _ = executeSQL("INSERT INTO transfers (withdrawal_timestamp, withdrawal_account, withdrawal, "
                           "deposit_timestamp, deposit_account, deposit, note, asset) "
                           "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, :note, :asset)",
                           [(":timestamp", timestamp), (":f_acc_id", f_acc_id), (":t_acc_id", t_acc_id),
                            (":f_amount", f_amount), (":t_amount", t_amount), (":note", note), (":asset", asset)],
                           commit=True)

    def add_corporate_action(self, account_id, type, timestamp, number, asset, qty, outcome, note):
        action_id = readSQL("SELECT id FROM asset_actions "
                            "WHERE timestamp=:timestamp AND type = :type AND account_id = :account "
                            "AND number = :number AND asset_id = :asset",
                            [(":timestamp", timestamp), (":type", type), (":account", account_id),
                             (":number", number), (":asset", asset)])
        if action_id:
            logging.info(self.tr("Corporate action already exists: #") + f"{number}")
            return
        query = executeSQL("INSERT INTO asset_actions (timestamp, number, account_id, type, asset_id, qty, note) "
                           "VALUES (:timestamp, :number, :account, :type, :asset, :qty, :note)",
                           [(":timestamp", timestamp), (":number", number), (":account", account_id), (":type", type),
                            (":asset", asset), (":qty", float(qty)), (":note", note)], commit=True)
        action_id = query.lastInsertId()
        for item in outcome:
            _ = executeSQL("INSERT INTO action_results (action_id, asset_id, qty, value_share) "
                           "VALUES (:action_id, :asset_id, :qty, :value_share)",
                           [(":action_id", action_id), (":asset_id", -item['asset']), (":qty", item['quantity']),
                            (":value_share", item['share'])], commit=True)

    def add_cash_transaction(self, account_id, broker_id, timestamp, lines):
        if not lines:
            return   # No transaction details
        query = executeSQL("INSERT INTO actions (timestamp, account_id, peer_id) "
                           "VALUES (:timestamp, :account_id, :bank_id)",
                           [(":timestamp", timestamp), (":account_id", account_id), (":bank_id", broker_id)])
        pid = query.lastInsertId()
        for line in lines:
            _ = executeSQL("INSERT INTO action_details (pid, category_id, amount, note) "
                           "VALUES (:pid, :category_id, :amount, :note)",
                           [(":pid", pid), (":category_id", line['category']), (":amount", line['amount']),
                            (":note", line['note'])], commit=True)

    def reconcile_account(self, account_id, timestamp):
        _ = executeSQL("UPDATE accounts SET reconciled_on=:timestamp WHERE id = :account_id",
                       [(":timestamp", timestamp), (":account_id", account_id)])

    def account_reconciliation_timestamp(self, account_id):
        timestamp = readSQL("SELECT reconciled_on FROM accounts WHERE id=:account_id", [(":account_id", account_id)])
        if timestamp is None:
            return 0
        else:
            return timestamp

    def get_asset_amount(self, timestamp, account_id, asset_id):
        return readSQL("SELECT amount_acc FROM ledger "
                       "WHERE account_id=:account_id AND asset_id=:asset_id AND timestamp<=:timestamp "
                       "AND (book_account=:money OR book_account=:assets OR book_account=:liabilities) "
                       "ORDER BY id DESC LIMIT 1",
                       [(":account_id", account_id), (":asset_id", asset_id), (":timestamp", timestamp),
                        (":money", BookAccount.Money), (":assets", BookAccount.Assets),
                        (":liabilities", BookAccount.Liabilities)])
