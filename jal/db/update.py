import logging
from datetime import datetime
from PySide2.QtWidgets import QApplication, QDialog
from PySide2.QtSql import QSqlTableModel

from jal.ui.ui_add_asset_dlg import Ui_AddAssetDialog
from jal.constants import Setup, PredefindedAccountType, PredefinedAsset
from jal.db.helpers import db_connection, executeSQL, readSQL, get_country_by_code
from jal.widgets.helpers import g_tr


# -----------------------------------------------------------------------------------------------------------------------
class AddAssetDialog(QDialog, Ui_AddAssetDialog):
    def __init__(self, symbol, isin='', name=''):
        QDialog.__init__(self)
        self.setupUi(self)
        self.asset_id = None

        self.SymbolEdit.setText(symbol)
        self.isinEdit.setText(isin)
        self.NameEdit.setText(name)

        self.type_model = QSqlTableModel(db=db_connection())
        self.type_model.setTable('asset_types')
        self.type_model.select()
        self.TypeCombo.setModel(self.type_model)
        self.TypeCombo.setModelColumn(1)

        self.data_src_model = QSqlTableModel(db=db_connection())
        self.data_src_model.setTable('data_sources')
        self.data_src_model.select()
        self.DataSrcCombo.setModel(self.data_src_model)
        self.DataSrcCombo.setModelColumn(1)

        # center dialog with respect to main application window
        parent = None
        for widget in QApplication.topLevelWidgets():
            if widget.objectName() == Setup.MAIN_WND_NAME:
                parent = widget
        if parent:
            x = parent.x() + parent.width() / 2 - self.width() / 2
            y = parent.y() + parent.height() / 2 - self.height() / 2
            self.setGeometry(x, y, self.width(), self.height())

    def accept(self):
        self.asset_id = JalDB().add_asset(self.SymbolEdit.text(), self.NameEdit.text(),
                                          self.type_model.record(self.TypeCombo.currentIndex()).value("id"),
                                          self.isinEdit.text(),
                                          self.data_src_model.record(self.DataSrcCombo.currentIndex()).value("id"))
        super().accept()


# ----------------------------------------------------------------------------------------------------------------------
class JalDB():
    def __init__(self):
        pass

    def commit(self):
        db_connection().commit()

    def get_language_id(self, language_code):
        return readSQL("SELECT id FROM languages WHERE language = :language_code", [(':language_code', language_code)])

    def get_language_code(self, language_id):
        return readSQL("SELECT language FROM languages WHERE id = :language_id", [(':language_id', language_id)])

    def get_asset_name(self, asset_id):
        return readSQL("SELECT name FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])

    def get_asset_type(self, asset_id):
        return readSQL("SELECT type_id FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])

    def get_account_name(self, account_id):
        return readSQL("SELECT name FROM accounts WHERE id=:account_id", [(":account_id", account_id)])

    # Searches for account_id by account number and optional currency
    # Returns: account_id or None if no account was found
    def get_account_id(self, accountNumber, accountCurrency=''):
        if accountCurrency:
            account_id = readSQL("SELECT a.id FROM accounts AS a "
                                 "LEFT JOIN assets AS c ON c.id=a.currency_id "
                                 "WHERE a.number=:account_number AND c.name=:currency_name",
                                 [(":account_number", accountNumber), (":currency_name", accountCurrency)],
                                 check_unique=True)
        else:
            account_id = readSQL("SELECT a.id FROM accounts AS a "
                                 "LEFT JOIN assets AS c ON c.id=a.currency_id "
                                 "WHERE a.number=:account_number", [(":account_number", accountNumber)],
                                 check_unique=True)
        return account_id

    def find_account(self, account_number, currency_code):
        return readSQL("SELECT id FROM accounts WHERE number=:account_number AND currency_id=:currency",
                       [(":account_number", account_number), (":currency", currency_code)], check_unique=True)

    def add_account(self, account_number, currency_code, account_type=PredefindedAccountType.Investment):
        account_id = self.find_account(account_number, currency_code)
        if account_id:  # Account already exists
            logging.warning(g_tr('JalDB', "Account already exists: ") +
                            f"{account_number} ({self.get_asset_name(currency_code)})")
            return account_id
        currency = self.get_asset_name(currency_code)
        account_info = readSQL(
            "SELECT a.name AS name, SUBSTR(a.name, 1, LENGTH(a.name)-LENGTH(c.name)-1) AS short_name, "
            "SUBSTR(a.name, -(LENGTH(c.name)+1), LENGTH(c.name)+1) = '.'||c.name AS auto_name "
            "FROM accounts AS a LEFT JOIN assets AS c ON a.currency_id = c.id WHERE number=:account_number LIMIT 1",
            [(":account_number", account_number)], named=True)
        if account_info:  # Account with the same number but different currency exists
            if account_info['auto_name']:
                new_name = account_info['short_name'] + '.' + currency
            else:
                new_name = account_info['name'] + '.' + currency
            query = executeSQL(
                "INSERT INTO accounts (type_id, name, active, number, currency_id, organization_id, country_id) "
                "SELECT a.type_id, :new_name, a.active, a.number, :currency_id, a.organization_id, a.country_id "
                "FROM accounts AS a LEFT JOIN assets AS c ON c.id=:currency_id "
                "WHERE number=:account_number LIMIT 1",
                [(":account_number", account_number), (":currency_id", currency_code), (":new_name", new_name)])
            return query.lastInsertId()

        bank_name = g_tr('JalB', "Bank for #" + account_number)
        bank_id = readSQL("SELECT id FROM agents WHERE name=:bank_name", [(":bank_name", bank_name)])
        if bank_id is None:
            query = executeSQL("INSERT INTO agents (pid, name) VALUES (0, :bank_name)", [(":bank_name", bank_name)])
            bank_id = query.lastInsertId()
        query = executeSQL("INSERT INTO accounts (type_id, name, active, number, currency_id, organization_id) "
                           "VALUES(:type, :name, 1, :number, :currency, :bank)",
                           [(":type", account_type), (":name", account_number+'.'+currency),
                            (":number", account_number), (":currency", currency_code), (":bank", bank_id)])
        return query.lastInsertId()

    def get_account_currency(self, account_id):
        return readSQL("SELECT currency_id FROM accounts WHERE id=:account_id", [(":account_id", account_id)])

    def get_account_bank(self, account_id):
        return readSQL("SELECT organization_id FROM accounts WHERE id=:account_id", [(":account_id", account_id)])

    # Searches for asset_id in database - first by ISIN, then by Reg.Code next by Symbol
    # If found - tries to update data if some is empty in database
    # If asset not found and 'dialog_new' is True - pops up a window for asset creation
    # Returns: asset_id or None if new asset creation failed
    def get_asset_id(self, symbol, isin='', reg_code='', name='', expiry=0, dialog_new=True):  # TODO Change params to **kwargs
        asset_id = None
        if isin:
            asset_id = readSQL("SELECT id FROM assets WHERE isin=:isin", [(":isin", isin)])
            if asset_id is None:
                asset_id = readSQL("SELECT id FROM assets WHERE name=:symbol COLLATE NOCASE AND coalesce(isin, '')=''",
                                   [(":symbol", symbol)])
        if asset_id is None:
            if reg_code:
                asset_id = readSQL("SELECT asset_id FROM asset_reg_id WHERE reg_code=:reg_code",
                                   [(":reg_code", reg_code)])
            if asset_id is None:
                asset_id = readSQL("SELECT id FROM assets WHERE name=:symbol AND "
                                   "((expiry=:expiry AND type_id=:derivative) OR type_id<>:derivative) COLLATE NOCASE",
                                   [(":symbol", symbol), (":expiry", expiry),
                                    (":derivative", PredefinedAsset.Derivative)])
        if asset_id is None and dialog_new:
            dialog = AddAssetDialog(symbol, isin=isin, name=name)
            dialog.exec_()
            asset_id = dialog.asset_id
        return asset_id

    def update_asset_data(self, asset_id, new_symbol='', new_isin='', new_reg='', new_country_code='', expiry=0):  # TODO Change params to **kwargs
        if new_symbol:
            symbol = readSQL("SELECT name FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
            if new_symbol.upper() != symbol.upper():
                _ = executeSQL("UPDATE assets SET name=:symbol WHERE id=:asset_id",
                               [(":symbol", new_symbol), (":asset_id", asset_id)])
                # Show warning only if symbol was changed not due known bankruptcy or new issue pattern
                if not (((symbol == new_symbol[:-1]) and (new_symbol[-1] == 'D' or new_symbol[-1] == 'Q')) or
                        ((symbol[:-1] == new_symbol) and (symbol[-1] == 'D' or symbol[-1] == 'Q'))):
                    logging.info(g_tr('JalDB', "Symbol updated ") + f"{symbol} -> {new_symbol}")
        if new_isin:
            isin = readSQL("SELECT isin FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
            if isin == '':
                _ = executeSQL("UPDATE assets SET isin=:new_isin WHERE id=:asset_id",
                               [(":new_isin", new_isin), (":asset_id", asset_id)])
            elif isin != new_isin:
                logging.warning(g_tr('JalDB', "ISIN mismatch for ")
                                + f"{self.get_asset_name(asset_id)}: {isin} != {new_isin}")
        if new_reg:
            reg = readSQL("SELECT reg_code FROM asset_reg_id WHERE asset_id=:asset_id", [(":asset_id", asset_id)])
            if new_reg != reg:
                _ = executeSQL("INSERT OR REPLACE INTO asset_reg_id(asset_id, reg_code) VALUES(:asset_id, :new_reg)",
                               [(":new_reg", new_reg), (":asset_id", asset_id)])
                logging.info(g_tr('JalDB', "Reg.number updated for ")
                             + f"{self.get_asset_name(asset_id)}: {reg} -> {new_reg}")
        if new_country_code:
            country_id, country_code = readSQL("SELECT a.country_id, c.code FROM assets AS a LEFT JOIN countries AS c "
                                   "ON a.country_id=c.id WHERE a.id=:asset_id", [(":asset_id", asset_id)])
            if (country_id == 0) or (country_code.lower() != new_country_code.lower()):
                new_country_id = get_country_by_code(new_country_code)
                _ = executeSQL("UPDATE assets SET country_id=:new_country_id WHERE id=:asset_id",
                               [(":new_country_id", new_country_id), (":asset_id", asset_id)])
                if country_id != 0:
                    logging.info(g_tr('JalDB', "Country updated for ")
                                 + f"{self.get_asset_name(asset_id)}: {country_code} -> {new_country_code}")
        if expiry:
            _ = executeSQL("UPDATE assets SET expiry=:expiry WHERE id=:asset_id",
                           [(":expiry", expiry), (":asset_id", asset_id)])

    def update_quote(self, asset_id, timestamp, quote):
        if (timestamp is None) or (quote is None):
            return
        old_id = 0
        query = executeSQL("SELECT id FROM quotes WHERE asset_id = :asset_id AND timestamp = :timestamp",
                           [(":asset_id", asset_id), (":timestamp", timestamp)])
        if query.next():
            old_id = query.value(0)
        if old_id:
            executeSQL("UPDATE quotes SET quote=:quote WHERE id=:old_id", [(":quote", quote), (":old_id", old_id), ])
        else:
            executeSQL("INSERT INTO quotes(timestamp, asset_id, quote) VALUES (:timestamp, :asset_id, :quote)",
                       [(":timestamp", timestamp), (":asset_id", asset_id), (":quote", quote)])
        logging.info(g_tr('JalDB', "Quote loaded: ") +
                     f"{self.get_asset_name(asset_id)} " 
                     f"@ {datetime.utcfromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')} = {quote}")

    def add_asset(self, symbol, name, asset_type, isin, data_source=-1, reg_code=None, country_code='', expiry=0):  # TODO Change params to **kwargs
        country_id = get_country_by_code(country_code)
        query = executeSQL("INSERT INTO assets(name, type_id, full_name, isin, src_id, country_id, expiry) "
                           "VALUES(:symbol, :type, :full_name, :isin, :data_src, :country_id, :expiry)",
                           [(":symbol", symbol), (":type", asset_type), (":full_name", name),
                            (":isin", isin), (":data_src", data_source), (":country_id", country_id),
                            (":expiry", expiry)], commit=True)
        asset_id = query.lastInsertId()
        if asset_id is None:
            logging.error(g_tr('JalDB', "Failed to add new asset: ") + f"{symbol}")
        if reg_code is not None:
            _ = executeSQL("INSERT INTO asset_reg_id(asset_id, reg_code) VALUES(:asset_id, :new_reg)",
                           [(":new_reg", reg_code), (":asset_id", asset_id)])
        return asset_id

    def add_dividend(self, subtype, timestamp, account_id, asset_id, amount, note, trade_number='', tax=0.0):
        id = readSQL("SELECT id FROM dividends WHERE timestamp=:timestamp AND account_id=:account_id "
                     "AND asset_id=:asset_id AND amount=:amount AND note=:note",
                     [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id),
                      (":amount", amount), (":note", note)])
        if id:
            logging.info(g_tr('JalDB', "Dividend already exists: ") + f"{note}")
            return
        _ = executeSQL("INSERT INTO dividends (timestamp, number, type, account_id, asset_id, amount, tax, note) "
                       "VALUES (:timestamp, :number, :subtype, :account_id, :asset_id, :amount, :tax, :note)",
                       [(":timestamp", timestamp), (":number", trade_number), (":subtype", subtype),
                        (":account_id", account_id), (":asset_id", asset_id), (":amount", amount),
                        (":tax", tax), (":note", note)],
                       commit=True)

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
            logging.info(g_tr('JalDB', "Trade already exists: #") + f"{number}")
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

    def add_transfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note):
        transfer_id = readSQL("SELECT id FROM transfers WHERE withdrawal_timestamp=:timestamp "
                              "AND withdrawal_account=:from_acc_id AND deposit_account=:to_acc_id "
                              "AND withdrawal=:f_amount AND deposit=:t_amount",
                              [(":timestamp", timestamp), (":from_acc_id", f_acc_id), (":to_acc_id", t_acc_id),
                               (":f_amount", f_amount), (":t_amount", t_amount)])
        if transfer_id:
            logging.info(g_tr('JalDB', "Transfer/Exchange already exists: ") + f"{f_amount}->{t_amount}")
            return
        if abs(fee) > Setup.CALC_TOLERANCE:
            _ = executeSQL("INSERT INTO transfers (withdrawal_timestamp, withdrawal_account, withdrawal, "
                           "deposit_timestamp, deposit_account, deposit, fee_account, fee, note) "
                           "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, "
                           ":fee_acc_id, :fee_amount, :note)",
                           [(":timestamp", timestamp), (":f_acc_id", f_acc_id), (":t_acc_id", t_acc_id),
                            (":f_amount", f_amount), (":t_amount", t_amount), (":fee_acc_id", fee_acc_id),
                            (":fee_amount", fee), (":note", note)], commit=True)
        else:
            _ = executeSQL("INSERT INTO transfers (withdrawal_timestamp, withdrawal_account, withdrawal, "
                           "deposit_timestamp, deposit_account, deposit, note) "
                           "VALUES (:timestamp, :f_acc_id, :f_amount, :timestamp, :t_acc_id, :t_amount, :note)",
                           [(":timestamp", timestamp), (":f_acc_id", f_acc_id), (":t_acc_id", t_acc_id),
                            (":f_amount", f_amount), (":t_amount", t_amount), (":note", note)], commit=True)

    def add_corporate_action(self, account_id, type, timestamp, number,
                             asset_id_old, qty_old, asset_id_new, qty_new, basis_ratio, note):
        action_id = readSQL("SELECT id FROM corp_actions "
                            "WHERE timestamp=:timestamp AND type = :type AND account_id = :account AND number = :number "
                            "AND asset_id = :asset AND asset_id_new = :asset_new",
                            [(":timestamp", timestamp), (":type", type), (":account", account_id), (":number", number),
                             (":asset", asset_id_old), (":asset_new", asset_id_new)])
        if action_id:
            logging.info(g_tr('JalDB', "Corporate action already exists: #") + f"{number}")
            return

        _ = executeSQL("INSERT INTO corp_actions (timestamp, number, account_id, type, "
                       "asset_id, qty, asset_id_new, qty_new, basis_ratio, note) "
                       "VALUES (:timestamp, :number, :account, :type, "
                       ":asset, :qty, :asset_new, :qty_new, :basis_ratio, :note)",
                       [(":timestamp", timestamp), (":number", number), (":account", account_id), (":type", type),
                        (":asset", asset_id_old), (":qty", float(qty_old)), (":asset_new", asset_id_new),
                        (":qty_new", float(qty_new)), (":basis_ratio", basis_ratio), (":note", note)], commit=True)

    def add_cash_transaction(self, account_id, broker_id, timestamp, amount, category_id, description):
        query = executeSQL("INSERT INTO actions (timestamp, account_id, peer_id) "
                           "VALUES (:timestamp, :account_id, :bank_id)",
                           [(":timestamp", timestamp), (":account_id", account_id), (":bank_id", broker_id)])
        pid = query.lastInsertId()
        _ = executeSQL("INSERT INTO action_details (pid, category_id, amount, note) "
                       "VALUES (:pid, :category_id, :amount, :note)",
                       [(":pid", pid), (":category_id", category_id), (":amount", amount),
                        (":note", description)], commit=True)
