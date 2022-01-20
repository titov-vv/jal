import logging
from datetime import datetime
from math import copysign
from PySide6.QtCore import Signal, QObject, QDate
from PySide6.QtWidgets import QDialog, QMessageBox
from jal.constants import Setup, BookAccount, TransactionType, TransferSubtype, ActionSubtype, DividendSubtype, \
    CorporateAction, PredefinedCategory, PredefinedPeer
from jal.db.helpers import executeSQL, readSQL, readSQLrecord, db_triggers_disable, db_triggers_enable
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.ui.ui_rebuild_window import Ui_ReBuildDialog


class RebuildDialog(QDialog, Ui_ReBuildDialog):
    def __init__(self, parent, frontier):
        QDialog.__init__(self)
        self.setupUi(self)

        self.LastRadioButton.toggle()
        self.frontier = frontier
        frontier_text = datetime.utcfromtimestamp(frontier).strftime('%d/%m/%Y')
        self.FrontierDateLabel.setText(frontier_text)
        self.CustomDateEdit.setDate(QDate.currentDate())

        # center dialog with respect to parent window
        x = parent.x() + parent.width()/2 - self.width()/2
        y = parent.y() + parent.height()/2 - self.height()/2
        self.setGeometry(x, y, self.width(), self.height())

    def isFastAndDirty(self):
        return self.FastAndDirty.isChecked()

    def getTimestamp(self):
        if self.LastRadioButton.isChecked():
            return self.frontier
        elif self.DateRadionButton.isChecked():
            return self.CustomDateEdit.dateTime().toSecsSinceEpoch()
        else:  # self.AllRadioButton.isChecked()
            return 0


# ===================================================================================================================
# Subclasses dictionary to store last amount/value for [book, account, asset]
# Differs from dictionary in a way that __getitem__() method uses DB-stored values for initialization
class LedgerAmounts(dict):
    def __init__(self, total_field=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if total_field is None:
            raise ValueError("Unitialized field in LedgerAmounts")
        self.total_field = total_field

    def __getitem__(self, key):
        # predefined indices in key tuple
        BOOK = 0
        ACCOUNT = 1
        ASSET = 2

        try:
            return super().__getitem__(key)
        except KeyError:
            amount = readSQL(f"SELECT {self.total_field} FROM ledger "
                             "WHERE book_account = :book AND account_id = :account_id AND asset_id = :asset_id "
                             "ORDER BY id DESC LIMIT 1",
                             [(":book", key[BOOK]), (":account_id", key[ACCOUNT]), (":asset_id", key[ASSET])])
            amount = float(amount) if amount is not None else 0.0
            super().__setitem__(key, amount)
            return amount


# ===================================================================================================================
class Ledger(QObject):
    updated = Signal()
    SILENT_REBUILD_THRESHOLD = 1000

    def __init__(self):
        QObject.__init__(self)
        self.current = {}
        self.amounts = LedgerAmounts("amount_acc")    # store last amount for [book, account, asset]
        self.values = LedgerAmounts("value_acc")      # together with corresponding value
        self.main_window = None
        self.progress_bar = None

    def setProgressBar(self, main_window, progress_widget):
        self.main_window = main_window
        self.progress_bar = progress_widget

    # Returns timestamp of last operations that were calculated into ledger
    def getCurrentFrontier(self):
        current_frontier = readSQL("SELECT ledger_frontier FROM frontier")
        if current_frontier == '':
            current_frontier = 0
        return current_frontier

    # Add one more transaction to 'book' of ledger.
    # If book is Assets and value is not None then amount contains Asset Quantity and Value contains amount
    #    of money in current account currency. Otherwise Amount contains only money value.
    # Method uses Account, Asset,Peer, Category and Tag values from current transaction
    def appendTransaction(self, book, amount, value=None):
        op_type = self.current['type']
        op_id = self.current['id']
        timestamp = self.current['timestamp']
        if book == BookAccount.Assets:
            asset_id = self.current['asset']
        else:
            asset_id = self.current['currency']
        account_id = self.current['account']
        if book == BookAccount.Costs or book == BookAccount.Incomes:
            peer_id = self.current['peer']
            category_id = self.current['category']
            tag_id = None if self.current['tag'] == '' else self.current['tag']
        else:
            peer_id = None
            category_id = None
            tag_id = None
        value = 0.0 if value is None else value
        self.amounts[(book, account_id, asset_id)] += amount
        self.values[(book, account_id, asset_id)] += value
        if (abs(amount) + abs(value)) <= (4 * Setup.CALC_TOLERANCE):
            return  # we have zero amount - no reason to put it into ledger

        _ = executeSQL("INSERT INTO ledger (timestamp, op_type, operation_id, book_account, asset_id, account_id, "
                       "amount, value, amount_acc, value_acc, peer_id, category_id, tag_id) "
                       "VALUES(:timestamp, :op_type, :operation_id, :book, :asset_id, :account_id, "
                       ":amount, :value, :amount_acc, :value_acc, :peer_id, :category_id, :tag_id)",
                       [(":timestamp", timestamp), (":op_type", op_type), (":operation_id", op_id),
                        (":book", book), (":asset_id", asset_id), (":account_id", account_id), (":amount", amount),
                        (":value", value), (":amount_acc", self.amounts[(book, account_id, asset_id)]),
                        (":value_acc", self.values[(book, account_id, asset_id)]),
                        (":peer_id", peer_id), (":category_id", category_id), (":tag_id", tag_id)])

    # Returns Amount measured in current account currency or asset that 'book' has at current ledger frontier
    def getAmount(self, book, asset_id=None):
        if asset_id is None:
            asset_id = self.current['currency']
        return self.amounts[(book, self.current['account'], asset_id)]

    def takeCredit(self, operation_amount):
        money_available = self.getAmount(BookAccount.Money)
        credit = 0
        if money_available < operation_amount:
            credit = operation_amount - money_available
            self.appendTransaction(BookAccount.Liabilities, -credit)
        return credit

    def returnCredit(self, operation_amount):
        current_credit_value = -1.0 * self.getAmount(BookAccount.Liabilities)
        debit = 0
        if current_credit_value > 0:
            if current_credit_value >= operation_amount:
                debit = operation_amount
            else:
                debit = current_credit_value
        if debit > 0:
            self.appendTransaction(BookAccount.Liabilities, debit)
        return debit

    def processActionDetails(self):
        query = executeSQL("SELECT amount, category_id, tag_id FROM action_details AS d WHERE pid=:pid",
                           [(":pid", self.current['id'])])
        while query.next():
            amount, self.current['category'], self.current['tag'] = readSQLrecord(query)
            book = BookAccount.Costs if amount < 0 else BookAccount.Incomes
            self.appendTransaction(book, -amount)

    def processAction(self):
        if self.current['amount'] == '':
            logging.warning(self.tr("Can't process operation without details") +
                            f" @{datetime.utcfromtimestamp(self.current['timestamp']).strftime('%d.%m.%Y %H:%M:%S')}")
            return
        action_amount = self.current['amount']
        if action_amount < 0:
            credit_taken = self.takeCredit(-action_amount)
            self.appendTransaction(BookAccount.Money, -(-action_amount - credit_taken))
        else:
            credit_returned = self.returnCredit(action_amount)
            if credit_returned < action_amount:
                self.appendTransaction(BookAccount.Money, action_amount - credit_returned)
        if self.current['subtype'] == ActionSubtype.SingleIncome:
            self.appendTransaction(BookAccount.Incomes, -action_amount)
        elif self.current['subtype'] == ActionSubtype.SingleSpending:
            self.appendTransaction(BookAccount.Costs, -action_amount)
        else:
            self.processActionDetails()

    def processDividend(self):
        if self.current['subtype'] == DividendSubtype.Dividend:
            self.current['category'] = PredefinedCategory.Dividends
        elif self.current['subtype'] == DividendSubtype.BondInterest:
            self.current['category'] = PredefinedCategory.Interest
        else:
            logging.error(self.tr("Can't process dividend with N/A type"))
            return
        if self.current['peer'] == '':
            logging.error(self.tr("Can't process dividend as bank isn't set for investment account"))
            return
        dividend_amount = self.current['amount']
        tax_amount = self.current['fee_tax']
        if dividend_amount > 0:
            credit_returned = self.returnCredit(dividend_amount - tax_amount)
            if credit_returned < (dividend_amount - tax_amount):
                self.appendTransaction(BookAccount.Money, dividend_amount - credit_returned)
            self.appendTransaction(BookAccount.Incomes, -dividend_amount)
        else:
            credit_taken = self.takeCredit(-dividend_amount - tax_amount)  # tax always positive
            if credit_taken < -dividend_amount:
                self.appendTransaction(BookAccount.Money, dividend_amount + credit_taken)
            self.appendTransaction(BookAccount.Costs, -dividend_amount)
        if tax_amount:
            self.appendTransaction(BookAccount.Money, -tax_amount)
            self.current['category'] = PredefinedCategory.Taxes
            self.appendTransaction(BookAccount.Costs, tax_amount)

    # Process buy or sell operation base on self.current['amount'] (>0 - buy, <0 - sell)
    def processTrade(self):
        if self.current['peer'] == '':
            logging.error(self.tr("Can't process trade as bank isn't set for investment account: ") +
                          JalDB().get_account_name(self.current['account']))
            return

        account_id = self.current['account']
        asset_id = self.current['asset']
        type = copysign(1, self.current['amount'])  # 1 is buy, -1 is sell
        qty = type * self.current['amount']
        price = self.current['price']

        trade_value = round(price * qty, 2) + type * self.current['fee_tax']

        processed_qty = 0
        processed_value = 0
        # Get asset amount accumulated before current operation
        asset_amount = self.getAmount(BookAccount.Assets, asset_id)
        if ((-type) * asset_amount) > 0:  # Process deal match if we have asset that is opposite to operation
            # Get a list of all previous not matched trades or corporate actions
            query = executeSQL("SELECT timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty "
                               "FROM open_trades "
                               "WHERE account_id=:account_id AND asset_id=:asset_id AND remaining_qty!=0 "
                               "ORDER BY timestamp, op_type DESC",
                               [(":account_id", account_id), (":asset_id", asset_id)])
            while query.next():
                opening_trade = readSQLrecord(query, named=True)
                next_deal_qty = opening_trade['remaining_qty']
                if (processed_qty + next_deal_qty) > qty:  # We can't close all trades with current operation
                    next_deal_qty = qty - processed_qty  # If it happens - just process the remainder of the trade
                _ = executeSQL("UPDATE open_trades SET remaining_qty=remaining_qty-:qty "
                               "WHERE op_type=:op_type AND operation_id=:id AND asset_id=:asset_id",
                               [(":qty", next_deal_qty), (":op_type", opening_trade['op_type']),
                                (":id", opening_trade['operation_id']), (":asset_id", asset_id)])
                _ = executeSQL("INSERT INTO deals(account_id, asset_id, open_op_type, open_op_id, open_timestamp, close_op_type, close_op_id, close_timestamp, qty) "
                               "VALUES(:account_id, :asset_id, :open_op_type, :open_op_id, :open_timestamp, :close_op_type, :close_op_id, :close_timestamp, :qty)",
                               [(":account_id", account_id), (":asset_id", asset_id), (":open_op_type", opening_trade['op_type']), (":open_op_id", opening_trade['operation_id']), (":open_timestamp", opening_trade['timestamp']),
                                (":close_op_type", TransactionType.Trade), (":close_op_id", self.current['id']), (":close_timestamp", self.current['timestamp']), (":qty", (-type)*next_deal_qty)])
                processed_qty += next_deal_qty
                processed_value += (next_deal_qty * opening_trade['price'])
                if processed_qty == qty:
                    break
        if type > 0:
            credit_value = self.takeCredit(trade_value)
        else:
            credit_value = self.returnCredit(trade_value)
        if credit_value < trade_value:
            self.appendTransaction(BookAccount.Money, (-type)*(trade_value - credit_value))
        if processed_qty > 0:  # Add result of closed deals
            # decrease (for sell) or increase (for buy) amount of assets in ledger
            self.appendTransaction(BookAccount.Assets, type*processed_qty, type*processed_value)
            self.current['category'] = PredefinedCategory.Profit
            self.appendTransaction(BookAccount.Incomes, type * ((price * processed_qty) - processed_value))
        if processed_qty < qty:  # We have reminder that opens a new position
            _ = executeSQL("INSERT INTO open_trades(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
                           "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
                           [(":timestamp", self.current['timestamp']), (":type", TransactionType.Trade), (":operation_id", self.current['id']),
                            (":account_id", account_id), (":asset_id", asset_id), (":price", price), (":remaining_qty", qty - processed_qty)])
            self.appendTransaction(BookAccount.Assets, type*(qty - processed_qty), type*(qty - processed_qty) * price)
        if self.current['fee_tax']:
            self.current['category'] = PredefinedCategory.Fees
            self.appendTransaction(BookAccount.Costs, self.current['fee_tax'])

    def processTransfer(self):
        if self.current['subtype'] == TransferSubtype.Outgoing:
            credit_taken = self.takeCredit(self.current['amount'])
            self.appendTransaction(BookAccount.Money, -(self.current['amount'] - credit_taken))
            self.appendTransaction(BookAccount.Transfers, self.current['amount'])
        elif self.current['subtype'] == TransferSubtype.Fee:
            credit_taken = self.takeCredit(self.current['amount'])
            self.current['peer'] = PredefinedPeer.Financial
            self.current['category'] = PredefinedCategory.Fees
            self.appendTransaction(BookAccount.Money, -(self.current['amount'] - credit_taken))
            self.appendTransaction(BookAccount.Costs, self.current['amount'])
            self.appendTransaction(BookAccount.Transfers, self.current['amount'])
        elif self.current['subtype'] == TransferSubtype.Incoming:
            credit_returned = self.returnCredit(self.current['amount'])
            if credit_returned < self.current['amount']:
                self.appendTransaction(BookAccount.Money, (self.current['amount'] - credit_returned))
            self.appendTransaction(BookAccount.Transfers, -self.current['amount'])
        else:   # TODO implement assets transfer
            logging.error(self.tr("Unexpected data in transfer transaction"))
            return

    def updateStockDividendAssets(self):
        asset_amount = self.getAmount(BookAccount.Assets, self.current['asset'])
        self.current['price'] = self.current['price'] + asset_amount
        self.current['amount'] = asset_amount
        asset = JalDB().get_asset_name(self.current['asset'])
        QMessageBox().information(None, self.tr("Confirmation"),
                                  self.tr("Stock dividend for was updated for ") + asset +
                                  f" @{datetime.utcfromtimestamp(self.current['timestamp']).strftime('%d.%m.%Y')}\n" +
                                  self.tr("Please check that quantity is correct."),
                                  QMessageBox.Ok)
        _ = executeSQL("UPDATE corp_actions SET qty=:qty, qty_new=:qty_new WHERE id=:id",
                       [(":id", self.current['id']),
                        (":qty", self.current['amount']), (":qty_new", self.current['price'])])

    def processCorporateAction(self):
        # Stock dividends are imported without initial stock amounts -> correction happens here
        if self.current['subtype'] == CorporateAction.StockDividend and self.current['amount'] < 0:
            self.updateStockDividendAssets()

        account_id = self.current['account']
        asset_id = self.current['asset']
        qty = self.current['amount']

        processed_qty = 0
        processed_value = 0
        # Get asset amount accumulated before current operation
        asset_amount = self.getAmount(BookAccount.Assets, asset_id)
        if asset_amount < (qty - 2*Setup.CALC_TOLERANCE):
            logging.fatal(self.tr("Asset amount is not enough for corporate action processing. Date: ")
                          + f"{datetime.utcfromtimestamp(self.current['timestamp']).strftime('%d/%m/%Y %H:%M:%S')}")
            return

        # Get a list of all previous not matched trades or corporate actions
        query = executeSQL("SELECT timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty "
                           "FROM open_trades "
                           "WHERE account_id=:account_id AND asset_id=:asset_id  AND remaining_qty!=0 "
                           "ORDER BY timestamp, op_type DESC",
                           [(":account_id", account_id), (":asset_id", asset_id)])
        while query.next():
            opening_trade = readSQLrecord(query, named=True)
            next_deal_qty = opening_trade['remaining_qty']
            if (processed_qty + next_deal_qty) > qty:  # We can't close all trades with current operation
                raise ValueError(self.tr("Unhandled case: Corporate action covers not full open position"))
            _ = executeSQL("UPDATE open_trades SET remaining_qty=0 "
                           "WHERE op_type=:op_type AND operation_id=:id AND asset_id=:asset_id",
                           [(":op_type", opening_trade['op_type']),(":id", opening_trade['operation_id']),
                            (":asset_id", asset_id)])

            # Create a deal with relevant sign of quantity (-1 for short, +1 for long)
            _ = executeSQL("INSERT INTO deals(account_id, asset_id, open_op_type, open_op_id, open_timestamp, close_op_type, close_op_id, close_timestamp, qty) "
                           "VALUES(:account_id, :asset_id, :open_op_type, :open_op_id, :open_timestamp, :close_op_type, :close_op_id, :close_timestamp, :qty)",
                           [(":account_id", account_id), (":asset_id", asset_id), (":open_op_type", opening_trade['op_type']),(":open_op_id", opening_trade['operation_id']), (":open_timestamp", opening_trade['timestamp']),
                            (":close_op_type", TransactionType.CorporateAction), (":close_op_id", self.current['id']), (":close_timestamp", self.current['timestamp']), (":qty", next_deal_qty)])
            processed_qty += next_deal_qty
            processed_value += (next_deal_qty * opening_trade['price'])
            if processed_qty == qty:
                break
        # Asset allocations for different corporate actions:
        # +-----------------+-------+-----+------------+-----------+----------+---------------+--------------------+
        # |                 | Asset | Qty | cost basis | Asset new | Qty new  | cost basis    | The same algo for: |
        # +-----------------+-------+-----+------------+-----------+----------+---------------+--------------------+
        # | Symbol Change   |   A   |  N  |  100 %     |     B     |    N     |   100%        |                    |
        # | (R-)Split       |   A   |  N  |  100 %     |     A     |    M     |   100%        | Stock Dividend     |
        # | Merger          |   A   |  N  |  100 %     |     B     |    M     |   100%        |                    |
        # | Spin-Off        |   A   |  N  |  100 %     |   A & B   | AxN, BxM | X% & (100-X)% |                    |
        # +-----------------+-------+-----+------------+-----------+----------+---------------+--------------------+
        # Withdraw value with old quantity of old asset as it common for all corporate action
        self.appendTransaction(BookAccount.Assets, -processed_qty, -processed_value)

        # Prepare details about new asset
        new_asset = self.current['peer']
        new_qty = self.current['price']
        new_value = processed_value
        if self.current['subtype'] == CorporateAction.SpinOff:
            new_value = processed_value * (1 - self.current['fee_tax'])
            price = (processed_value - new_value) / self.current['amount']
            # Modify value for old asset
            self.appendTransaction(BookAccount.Assets, self.current['amount'], processed_value - new_value)
            _ = executeSQL(
                "INSERT INTO open_trades(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
                "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
                [(":timestamp", self.current['timestamp']), (":type", TransactionType.CorporateAction),
                 (":operation_id", self.current['id']),
                 (":account_id", account_id), (":asset_id", self.current['asset']), (":price", price), (":remaining_qty", self.current['amount'])])
        # Create value for new asset
        self.current['asset'] = new_asset
        new_price = new_value / new_qty
        _ = executeSQL("INSERT INTO open_trades(timestamp, op_type, operation_id, account_id, asset_id, price, remaining_qty) "
                       "VALUES(:timestamp, :type, :operation_id, :account_id, :asset_id, :price, :remaining_qty)",
                       [(":timestamp", self.current['timestamp']), (":type", TransactionType.CorporateAction),
                        (":operation_id", self.current['id']),
                        (":account_id", account_id), (":asset_id", new_asset), (":price", new_price), (":remaining_qty", new_qty)])
        self.appendTransaction(BookAccount.Assets, new_qty, new_value)

    # Rebuild transaction sequence and recalculate all amounts
    # timestamp:
    # -1 - re-build from last valid operation (from ledger frontier)
    #      will asks for confirmation if we have more than SILENT_REBUILD_THRESHOLD operations require rebuild
    # 0 - re-build from scratch
    # any - re-build all operations after given timestamp
    def rebuild(self, from_timestamp=-1, fast_and_dirty=False):
        operationProcess = {
            TransactionType.Action: self.processAction,
            TransactionType.Dividend: self.processDividend,
            TransactionType.Trade: self.processTrade,
            TransactionType.Transfer: self.processTransfer,
            TransactionType.CorporateAction: self.processCorporateAction
        }

        self.amounts.clear()
        self.values.clear()
        if from_timestamp >= 0:
            frontier = from_timestamp
            operations_count = readSQL("SELECT COUNT(id) FROM all_transactions WHERE timestamp >= :frontier",
                                       [(":frontier", frontier)])
        else:
            frontier = self.getCurrentFrontier()
            operations_count = readSQL("SELECT COUNT(id) FROM all_transactions WHERE timestamp >= :frontier",
                                       [(":frontier", frontier)])
            if operations_count > self.SILENT_REBUILD_THRESHOLD:
                if QMessageBox().warning(None, self.tr("Confirmation"), f"{operations_count}" +
                                         self.tr(" operations require rebuild. Do you want to do it right now?"),
                                         QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                    JalSettings().setValue('RebuildDB', 1)
                    return
        if operations_count == 0:
            logging.info(self.tr("Leger is empty"))
            return
        if self.progress_bar is not None:
            self.progress_bar.setRange(0, operations_count)
            self.main_window.showProgressBar(True)
        logging.info(self.tr("Re-building ledger since: ") +
                     f"{datetime.utcfromtimestamp(frontier).strftime('%d/%m/%Y %H:%M:%S')}")
        start_time = datetime.now()
        _ = executeSQL("DELETE FROM deals WHERE close_timestamp >= :frontier", [(":frontier", frontier)])
        _ = executeSQL("DELETE FROM ledger WHERE timestamp >= :frontier", [(":frontier", frontier)])
        _ = executeSQL("DELETE FROM ledger_totals WHERE timestamp >= :frontier", [(":frontier", frontier)])
        _ = executeSQL("DELETE FROM open_trades WHERE timestamp >= :frontier", [(":frontier", frontier)])

        db_triggers_disable()
        if fast_and_dirty:  # For 30k operations difference of execution time is - with 0:02:41 / without 0:11:44
            _ = executeSQL("PRAGMA synchronous = OFF")
        try:
            query = executeSQL("SELECT type, id, timestamp, subtype, account, currency, asset, amount, "
                               "category, price, fee_tax, peer, tag FROM all_transactions "
                               "WHERE timestamp >= :frontier", [(":frontier", frontier)])
            while query.next():
                self.current = readSQLrecord(query, named=True)
                operationProcess[self.current['type']]()
                if self.progress_bar is not None:
                    self.progress_bar.setValue(query.at())
        finally:
            if fast_and_dirty:
                _ = executeSQL("PRAGMA synchronous = ON")
            db_triggers_enable()
        # Fill ledger totals values
        _ = executeSQL("INSERT INTO ledger_totals"
                       "(op_type, operation_id, timestamp, book_account, asset_id, account_id, amount_acc, value_acc) "
                       "SELECT op_type, operation_id, timestamp, book_account, "
                       "asset_id, account_id, amount_acc, value_acc FROM ledger "
                       "WHERE id IN ("
                       "SELECT MAX(id) FROM ledger WHERE timestamp >= :frontier "
                       "GROUP BY op_type, operation_id, book_account, account_id)", [(":frontier", frontier)])

        if self.progress_bar is not None:
            self.main_window.showProgressBar(False)
        JalSettings().setValue('RebuildDB', 0)
        logging.info(self.tr("Ledger is complete. Elapsed time: ") + f"{datetime.now() - start_time}" +
                     self.tr(", new frontier: ") + f"{datetime.utcfromtimestamp(self.current['timestamp']).strftime('%d/%m/%Y %H:%M:%S')}")

        self.updated.emit()

    def showRebuildDialog(self, parent):
        rebuild_dialog = RebuildDialog(parent, self.getCurrentFrontier())
        if rebuild_dialog.exec():
            self.rebuild(from_timestamp=rebuild_dialog.getTimestamp(),
                         fast_and_dirty=rebuild_dialog.isFastAndDirty())
