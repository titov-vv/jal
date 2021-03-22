import logging
from datetime import datetime
from jal.constants import Setup
from jal.db.helpers import db_connection, executeSQL, readSQL
from jal.widgets.helpers import g_tr


# ----------------------------------------------------------------------------------------------------------------------
class JalDB():
    def __init__(self):
        pass

    def commit(self):
        db_connection().commit()

    def get_asset_name(self, asset_id):
        return readSQL("SELECT name FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])

    def get_account_currency(self, account_id):
        return readSQL("SELECT currency_id FROM accounts WHERE id=:account_id", [(":account_id", account_id)])

    # Find asset by give partial name and type. Returns only first match even if many were found
    def find_asset_like_name(self, partial_name, asset_type=0):
        name = '%' + partial_name.replace(' ', '%') + '%'
        if asset_type:
            return readSQL("SELECT id FROM assets WHERE full_name LIKE :name AND type_id=:type",
                           [(":name", name), (":type", asset_type)])
        else:
            return readSQL("SELECT id FROM assets WHERE full_name LIKE :name", [(":name", name)])

    def update_isin_reg(self, asset_id, new_isin, new_reg):
        if new_isin:
            isin = readSQL("SELECT isin FROM assets WHERE id=:asset_id", [(":asset_id", asset_id)])
            if new_isin != isin:
                executeSQL("UPDATE assets SET isin=:new_isin WHERE id=:asset_id",
                           [(":new_isin", new_isin), (":asset_id", asset_id)])
                logging.info(g_tr('JalDB', "ISIN updated for ")
                             + f"{self.get_asset_name(asset_id)}: {isin} -> {new_isin}")
        if new_reg:
            reg = readSQL("SELECT reg_code FROM asset_reg_id WHERE asset_id=:asset_id", [(":asset_id", asset_id)])
            if new_reg != reg:
                executeSQL("INSERT OR REPLACE INTO asset_reg_id(asset_id, reg_code) VALUES(:asset_id, :new_reg)",
                           [(":new_reg", new_reg), (":asset_id", asset_id)])
                logging.info(g_tr('JalDB', "Reg.number updated for ")
                             + f"{self.get_asset_name(asset_id)}: {reg} -> {new_reg}")

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

    def add_asset(self, symbol, name, asset_type, isin, data_source=-1):
        _ = executeSQL("INSERT INTO assets(name, type_id, full_name, isin, src_id) "
                       "VALUES(:symbol, :type, :full_name, :isin, :data_src)",
                       [(":symbol", symbol), (":type", asset_type), (":full_name", name),
                        (":isin", isin), (":data_src", data_source)], commit=True)
        asset_id = readSQL("SELECT id FROM assets WHERE name=:symbol", [(":symbol", symbol)])
        if asset_id is None:
            logging.error(g_tr('JalDB', "Failed to add new asset: ") + f"{symbol}")
        return asset_id

    def add_dividend(self, subtype, timestamp, account_id, asset_id, amount, note, trade_number='', tax=0.0):
        id = readSQL("SELECT id FROM dividends WHERE timestamp=:timestamp "
                     "AND account_id=:account_id AND asset_id=:asset_id AND note=:note",
                     [(":timestamp", timestamp), (":account_id", account_id), (":asset_id", asset_id), (":note", note)])
        if id:
            logging.info(g_tr('JalDB', "Dividend already exists: ") + f"{note}")
            return
        _ = executeSQL("INSERT INTO dividends (timestamp, number, type, account_id, asset_id, amount, tax, note) "
                       "VALUES (:timestamp, :number, :subtype, :account_id, :asset_id, :amount, :tax, :note)",
                       [(":timestamp", timestamp), (":number", trade_number), (":subtype", subtype),
                        (":account_id", account_id), (":asset_id", asset_id), (":amount", amount),
                        (":tax", tax), (":note", note)],
                       commit=True)

    def add_trade(self, account_id, asset_id, timestamp, settlement, number, qty, price, fee):
        trade_id = readSQL("SELECT id FROM trades "
                           "WHERE timestamp=:timestamp AND asset_id = :asset "
                           "AND account_id = :account AND number = :number AND qty = :qty AND price = :price",
                           [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                            (":number", number), (":qty", qty), (":price", price)])
        if trade_id:
            logging.info(g_tr('JalDB', "Trade already exists: #") + f"{number}")
            return

        _ = executeSQL("INSERT INTO trades (timestamp, settlement, number, account_id, asset_id, qty, price, fee) "
                       "VALUES (:timestamp, :settlement, :number, :account, :asset, :qty, :price, :fee)",
                       [(":timestamp", timestamp), (":settlement", settlement), (":number", number),
                        (":account", account_id), (":asset", asset_id), (":qty", float(qty)),
                        (":price", float(price)), (":fee", -float(fee))], commit=True)

    def del_trade(self, account_id, asset_id, timestamp, _settlement, number, qty, price, _fee):
        _ = executeSQL("DELETE FROM trades "
                       "WHERE timestamp=:timestamp AND asset_id=:asset "
                       "AND account_id=:account AND number=:number AND qty=:qty AND price=:price",
                       [(":timestamp", timestamp), (":asset", asset_id), (":account", account_id),
                        (":number", number), (":qty", -qty), (":price", price)], commit=True)

    def add_transfer(self, timestamp, f_acc_id, f_amount, t_acc_id, t_amount, fee_acc_id, fee, note):
        transfer_id = readSQL("SELECT id FROM transfers WHERE withdrawal_timestamp=:timestamp "
                              "AND withdrawal_account=:from_acc_id AND deposit_account=:to_acc_id",
                              [(":timestamp", timestamp), (":from_acc_id", f_acc_id), (":to_acc_id", t_acc_id)])
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
        _ = executeSQL("INSERT INTO action_details (pid, category_id, sum, note) "
                       "VALUES (:pid, :category_id, :sum, :note)",
                       [(":pid", pid), (":category_id", category_id), (":sum", amount),
                        (":note", description)], commit=True)
