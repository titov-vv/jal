import logging
import traceback
from datetime import datetime
from PySide6.QtCore import Signal, QObject, QDate
from PySide6.QtWidgets import QDialog, QMessageBox
from jal.constants import Setup, BookAccount
from jal.db.helpers import executeSQL, readSQL, readSQLrecord, db_triggers_disable, db_triggers_enable
from jal.db.db import JalDB
from jal.db.settings import JalSettings
from jal.db.operations import LedgerTransaction
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
    def appendTransaction(self, operation, book, amount, asset_id=None, value=None, category=None, peer=None, tag=None):
        if book == BookAccount.Assets and asset_id is None:
            raise ValueError(self.tr("No asset defined for: ") + f"{operation.dump()}")
        if asset_id is None:
            asset_id = JalDB().get_account_currency(operation.account_id())
        if (book == BookAccount.Costs or book == BookAccount.Incomes) and category is None:
            raise ValueError(self.tr("No category set for: ") + f"{operation.dump()}")
        if (book == BookAccount.Costs or book == BookAccount.Incomes) and peer is None:
            raise ValueError(self.tr("No peer set for: ") + f"{operation.dump()}")
        tag = tag if tag else None  # Get rid of possible empty values
        value = 0.0 if value is None else value
        self.amounts[(book, operation.account_id(), asset_id)] += amount
        self.values[(book, operation.account_id(), asset_id)] += value
        if (abs(amount) + abs(value)) <= (4 * Setup.CALC_TOLERANCE):
            return  # we have zero amount - no reason to put it into ledger

        _ = executeSQL("INSERT INTO ledger (timestamp, op_type, operation_id, book_account, asset_id, account_id, "
                       "amount, value, amount_acc, value_acc, peer_id, category_id, tag_id) "
                       "VALUES(:timestamp, :op_type, :operation_id, :book, :asset_id, :account_id, "
                       ":amount, :value, :amount_acc, :value_acc, :peer_id, :category_id, :tag_id)",
                       [(":timestamp", operation.timestamp()), (":op_type", operation.type()),
                        (":operation_id", operation.oid()), (":book", book), (":asset_id", asset_id),
                        (":account_id", operation.account_id()), (":amount", amount), (":value", value),
                        (":amount_acc", self.amounts[(book, operation.account_id(), asset_id)]),
                        (":value_acc", self.values[(book, operation.account_id(), asset_id)]),
                        (":peer_id", peer), (":category_id", category), (":tag_id", tag)])

    # Returns Amount measured in current account currency or asset that 'book' has at current ledger frontier
    def getAmount(self, book, account_id, asset_id=None):
        if asset_id is None:
            asset_id = JalDB().get_account_currency(account_id)
        return self.amounts[(book, account_id, asset_id)]

    def takeCredit(self, operation, account_id, operation_amount):
        money_available = self.getAmount(BookAccount.Money, account_id)
        credit = 0
        if money_available < operation_amount:
            credit = operation_amount - money_available
            self.appendTransaction(operation, BookAccount.Liabilities, -credit)
        return credit

    def returnCredit(self, operation, account_id, operation_amount):
        current_credit_value = -1.0 * self.getAmount(BookAccount.Liabilities, account_id)
        debit = 0
        if current_credit_value > 0:
            if current_credit_value >= operation_amount:
                debit = operation_amount
            else:
                debit = current_credit_value
        if debit > 0:
            self.appendTransaction(operation, BookAccount.Liabilities, debit)
        return debit

    # Rebuild transaction sequence and recalculate all amounts
    # timestamp:
    # -1 - re-build from last valid operation (from ledger frontier)
    #      will asks for confirmation if we have more than SILENT_REBUILD_THRESHOLD operations require rebuild
    # 0 - re-build from scratch
    # any - re-build all operations after given timestamp
    def rebuild(self, from_timestamp=-1, fast_and_dirty=False):
        exception_happened = False
        last_timestamp = 0
        self.amounts.clear()
        self.values.clear()
        if from_timestamp >= 0:
            frontier = from_timestamp
            operations_count = readSQL("SELECT COUNT(id) FROM operation_sequence WHERE timestamp >= :frontier",
                                       [(":frontier", frontier)])
        else:
            frontier = self.getCurrentFrontier()
            operations_count = readSQL("SELECT COUNT(id) FROM operation_sequence WHERE timestamp >= :frontier",
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
            query = executeSQL("SELECT op_type, id, timestamp, account_id, subtype FROM operation_sequence "
                               "WHERE timestamp >= :frontier", [(":frontier", frontier)])
            while query.next():
                data = readSQLrecord(query, named=True)
                last_timestamp = data['timestamp']
                operation = LedgerTransaction().get_operation(data['op_type'], data['id'], data['subtype'])
                operation.processLedger(self)
                if self.progress_bar is not None:
                    self.progress_bar.setValue(query.at())
        except Exception as e:
            exception_happened = True
            logging.error(f"{traceback.format_exc()}")
        finally:
            if fast_and_dirty:
                _ = executeSQL("PRAGMA synchronous = ON")
            db_triggers_enable()
            if self.progress_bar is not None:
                self.main_window.showProgressBar(False)
        # Fill ledger totals values
        _ = executeSQL("INSERT INTO ledger_totals"
                       "(op_type, operation_id, timestamp, book_account, asset_id, account_id, amount_acc, value_acc) "
                       "SELECT op_type, operation_id, timestamp, book_account, "
                       "asset_id, account_id, amount_acc, value_acc FROM ledger "
                       "WHERE id IN ("
                       "SELECT MAX(id) FROM ledger WHERE timestamp >= :frontier "
                       "GROUP BY op_type, operation_id, book_account, account_id)", [(":frontier", frontier)])
        JalSettings().setValue('RebuildDB', 0)
        if exception_happened:
            logging.error(self.tr("Exception happened. Ledger is incomplete. Please correct errors listed in log"))
        else:
            logging.info(self.tr("Ledger is complete. Elapsed time: ") + f"{datetime.now() - start_time}" +
                         self.tr(", new frontier: ") +
                         f"{datetime.utcfromtimestamp(last_timestamp).strftime('%d/%m/%Y %H:%M:%S')}")

        self.updated.emit()

    def showRebuildDialog(self, parent):
        rebuild_dialog = RebuildDialog(parent, self.getCurrentFrontier())
        if rebuild_dialog.exec():
            self.rebuild(from_timestamp=rebuild_dialog.getTimestamp(),
                         fast_and_dirty=rebuild_dialog.isFastAndDirty())
