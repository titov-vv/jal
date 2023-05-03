import sys
import logging
import traceback
from datetime import datetime
from decimal import Decimal
from PySide6.QtCore import Signal, QObject, QDate
from PySide6.QtWidgets import QDialog, QMessageBox
from jal.constants import BookAccount
from jal.db.helpers import format_decimal
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.settings import JalSettings
from jal.db.operations import LedgerTransaction, LedgerError
from jal.widgets.helpers import ts2dt, ts2d
from jal.ui.ui_rebuild_window import Ui_ReBuildDialog


# ----------------------------------------------------------------------------------------------------------------------
# Class to display window with ledger rebuild configuration options
class RebuildDialog(QDialog):
    def __init__(self, parent, frontier):
        super().__init__(parent)
        self.ui = Ui_ReBuildDialog()
        self.ui.setupUi(self)

        self.ui.LastRadioButton.toggle()   # Set default option selection
        self.frontier = frontier
        frontier_text = ts2d(frontier)
        self.ui.FrontierDateLabel.setText(frontier_text)
        self.ui.CustomDateEdit.setDate(QDate.currentDate())

        # center dialog with respect to parent window
        x = parent.x() + parent.width()/2 - self.width()/2
        y = parent.y() + parent.height()/2 - self.height()/2
        self.setGeometry(x, y, self.width(), self.height())

    def isFastAndDirty(self):
        return self.ui.FastAndDirty.isChecked()

    def getTimestamp(self):
        if self.ui.LastRadioButton.isChecked():
            return self.frontier
        elif self.ui.DateRadionButton.isChecked():
            return self.ui.CustomDateEdit.dateTime().toSecsSinceEpoch()
        else:  # self.AllRadioButton.isChecked()
            return 0


# ===================================================================================================================
# Subclasses dictionary to store last amount/value for [book, account, asset]
# Differs from dictionary in a way that __getitem__() method uses DB-stored values for initialization
# Parameter 'timestamp' is used in tests only - in order to get a slice from ledger in past
class LedgerAmounts(dict, JalDB):
    def __init__(self, total_field=None, timestamp=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if total_field is None:
            raise ValueError("Uninitialized field in LedgerAmounts")
        if timestamp is None:
            self.__time_filter__ = ''
        else:
            self.__time_filter__ = f"AND timestamp <= {timestamp:d}"
        self.total_field = total_field

    def __getitem__(self, key):
        # predefined indices in key tuple
        BOOK = 0
        ACCOUNT = 1
        ASSET = 2

        try:
            return super().__getitem__(key)
        except KeyError:
            amount = self._read(f"SELECT {self.total_field} FROM ledger "
                                f"WHERE book_account = :book AND account_id = :account_id AND asset_id = :asset_id "
                                f"{self.__time_filter__} "
                                f"ORDER BY id DESC LIMIT 1",
                                [(":book", key[BOOK]), (":account_id", key[ACCOUNT]), (":asset_id", key[ASSET])])
            amount = Decimal(amount) if amount is not None else Decimal('0')
            super().__setitem__(key, amount)
            return amount


# ===================================================================================================================
class Ledger(QObject, JalDB):
    updated = Signal()
    SILENT_REBUILD_THRESHOLD = 1000

    def __init__(self):
        super().__init__()
        self.amounts = LedgerAmounts("amount_acc")    # store last amount for [book, account, asset]
        self.values = LedgerAmounts("value_acc")      # together with corresponding value
        self.main_window = None
        self.progress_bar = None

    def setProgressBar(self, main_window, progress_widget):
        self.main_window = main_window
        self.progress_bar = progress_widget

    # Returns timestamp of last operations that were calculated into ledger
    def getCurrentFrontier(self):
        current_frontier = self._read("SELECT ledger_frontier FROM frontier")
        if current_frontier == '':
            current_frontier = 0
        return current_frontier

    @classmethod
    def get_operations_sequence(cls, begin: int, end: int, account_id: int = 0) -> list:
        sequence = []
        query_text = "SELECT op_type, id, timestamp, account_id, subtype " \
                     "FROM operation_sequence WHERE timestamp>=:begin AND timestamp<=:end"
        params = [(":begin", begin), (":end", end)]
        if account_id:
            query_text += " AND account_id=:account"
            params += [(":account", account_id)]
        query = cls._exec(query_text, params, forward_only=True)
        while query.next():
            sequence.append(cls._read_record(query, named=True))
        return sequence

    @classmethod
    # Returns a list of [op_type, op_id, timestamp, account_id, subtype] ordered by timestamp
    # collected from 'ledger' table with given WHERE statement set as condition and parameters
    def _get_operations_by_filter(cls, condition, parameters) -> list:
        operations = []
        query = cls._exec(
            f"SELECT DISTINCT op_type, operation_id AS id, timestamp, account_id, 0 AS subtype FROM ledger "
            f"{condition} ORDER BY timestamp", parameters, forward_only=True)
        while query.next():
            operations.append(cls._read_record(query, named=True))
        return operations

    @classmethod
    # Return a list of [op_type, op_id, timestamp, account_id, subtype] of operations that have peer_id involved
    def get_operations_by_peer(cls, begin: int, end: int, peer_id: int) -> list:
        condition = "WHERE peer_id=:peer AND timestamp>=:begin AND timestamp<=:end"
        parameters = [(":begin", begin), (":end", end), (":peer", peer_id)]
        return cls._get_operations_by_filter(condition, parameters)

    @classmethod
    # Return a list of [op_type, op_id, timestamp, account_id, subtype] of operations that have category_id involved
    def get_operations_by_category(cls, begin: int, end: int, category_id: int) -> list:
        condition = "WHERE category_id=:category AND timestamp>=:begin AND timestamp<=:end"
        parameters = [(":begin", begin), (":end", end), (":category", category_id)]
        return cls._get_operations_by_filter(condition, parameters)

    @classmethod
    # Return a list of [op_type, op_id, timestamp, account_id, subtype] of operations that have tag_id involved
    def get_operations_by_tag(cls, begin: int, end: int, tag_id: int) -> list:
        condition = "WHERE tag_id=:tag AND timestamp>=:begin AND timestamp<=:end"
        parameters = [(":begin", begin), (":end", end), (":tag", tag_id)]
        return cls._get_operations_by_filter(condition, parameters)

    # Add one more transaction to 'book' of ledger.
    # If book is Assets and value is not None then amount contains Asset Quantity and Value contains amount
    #    of money in current account currency. Otherwise, Amount contains only money value.
    # Returns non-zero value if accumulated_value differs from 0.0 when accumulated account is 0.0
    def appendTransaction(self, operation, book, amount, asset_id=None, value=None, category=None, peer=None, tag=None) -> Decimal:
        rounding_error = Decimal('0')
        if book == BookAccount.Assets and asset_id is None:
            raise ValueError(self.tr("No asset defined for: ") + f"{operation.dump()}")
        if asset_id is None:
            asset_id = JalAccount(operation.account_id()).currency()
        if (book == BookAccount.Costs or book == BookAccount.Incomes) and category is None:
            raise ValueError(self.tr("No category set for: ") + f"{operation.dump()}")
        if (book == BookAccount.Costs or book == BookAccount.Incomes) and peer is None:
            raise ValueError(self.tr("No peer set for: ") + f"{operation.dump()}")
        tag = tag if tag else None  # Get rid of possible empty values
        # Round values according to account decimal precision
        precision = JalAccount(operation.account_id()).precision()
        amount = round(amount, precision)
        value = Decimal('0') if value is None else round(value, precision)
        self.amounts[(book, operation.account_id(), asset_id)] += amount
        self.values[(book, operation.account_id(), asset_id)] += value
        if (abs(amount) + abs(value)) == Decimal('0'):
            return rounding_error  # we have zero amount - no reason to put it into ledger (return 0.0)
        if (book == BookAccount.Assets) and \
                (self.amounts[(book, operation.account_id(), asset_id)] == Decimal('0')) and \
                (self.values[(book, operation.account_id(), asset_id)] != Decimal('0')):
            rounding_error = Decimal('0') - self.values[(book, operation.account_id(), asset_id)]
            self.values[(book, operation.account_id(), asset_id)] += rounding_error
        _ = self._exec("INSERT INTO ledger (timestamp, op_type, operation_id, book_account, asset_id, "
                       "account_id, amount, value, amount_acc, value_acc, peer_id, category_id, tag_id) "
                       "VALUES(:timestamp, :op_type, :operation_id, :book, :asset_id, :account_id, "
                       ":amount, :value, :amount_acc, :value_acc, :peer_id, :category_id, :tag_id)",
                       [(":timestamp", operation.timestamp()), (":op_type", operation.type()),
                        (":operation_id", operation.oid()), (":book", book), (":asset_id", asset_id),
                        (":account_id", operation.account_id()),
                        (":amount", format_decimal(amount)), (":value", format_decimal(value)),
                        (":amount_acc", format_decimal(self.amounts[(book, operation.account_id(), asset_id)])),
                        (":value_acc", format_decimal(self.values[(book, operation.account_id(), asset_id)])),
                        (":peer_id", peer), (":category_id", category), (":tag_id", tag)])
        return rounding_error

    # Returns Amount measured in current account currency or asset that 'book' has at current ledger frontier
    def getAmount(self, book, account_id, asset_id=None):
        if asset_id is None:
            asset_id = JalAccount(account_id).currency()
        return self.amounts[(book, account_id, asset_id)]

    def takeCredit(self, operation, account_id, operation_amount):
        money_available = self.getAmount(BookAccount.Money, account_id)
        credit = Decimal('0')
        if money_available < operation_amount:
            credit = operation_amount - money_available
            self.appendTransaction(operation, BookAccount.Liabilities, -credit)
        return credit

    def returnCredit(self, operation, account_id, operation_amount):
        current_credit_value = -self.getAmount(BookAccount.Liabilities, account_id)
        debit = Decimal('0')
        if current_credit_value > Decimal('0'):
            if current_credit_value >= operation_amount:
                debit = operation_amount
            else:
                debit = current_credit_value
        if debit > Decimal('0'):
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
            operations_count = self._read("SELECT COUNT(id) FROM operation_sequence WHERE timestamp >= :frontier",
                                          [(":frontier", frontier)])
        else:
            frontier = self.getCurrentFrontier()
            operations_count = self._read("SELECT COUNT(id) FROM operation_sequence WHERE timestamp >= :frontier",
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
        logging.info(self.tr("Re-building ledger since: ") + f"{ts2dt(frontier)}")
        start_time = datetime.now()
        _ = self._exec("DELETE FROM trades_closed WHERE close_timestamp >= :frontier", [(":frontier", frontier)])
        _ = self._exec("DELETE FROM ledger WHERE timestamp >= :frontier", [(":frontier", frontier)])
        _ = self._exec("DELETE FROM ledger_totals WHERE timestamp >= :frontier", [(":frontier", frontier)])
        _ = self._exec("DELETE FROM trades_opened WHERE timestamp >= :frontier", [(":frontier", frontier)])

        self.enable_triggers(False)
        if fast_and_dirty:  # For 30k operations difference of execution time is - with 0:02:41 / without 0:11:44
            self.set_synchronous(False)
        try:
            query = self._exec("SELECT op_type, id, timestamp, account_id, subtype FROM operation_sequence "
                               "WHERE timestamp >= :frontier", [(":frontier", frontier)])
            while query.next():
                data = self._read_record(query, named=True)
                last_timestamp = data['timestamp']
                operation = LedgerTransaction().get_operation(data['op_type'], data['id'], data['subtype'])
                operation.processLedger(self)
                if self.progress_bar is not None:
                    self.progress_bar.setValue(query.at())
        except Exception as e:
            if "pytest" in sys.modules:  # Throw exception if we are in test mode or handle it if we are live
                raise e
            exception_happened = True
            if type(e) == LedgerError:
                logging.error(e)   # Short log for ledger custom exception
            else:
                logging.error(f"{traceback.format_exc()}")  # and full log for anything unexpected
        finally:
            if fast_and_dirty:
                self.set_synchronous(True)
            self.enable_triggers(True)
            if self.progress_bar is not None:
                self.main_window.showProgressBar(False)
        # Fill ledger totals values
        # NOFIXME: Table 'ledger_totals' may be replaced by a view. But it will impact performance heavily as
        # this view won't have indices for optimal performance
        _ = self._exec(
            "INSERT INTO ledger_totals"
            "(op_type, operation_id, timestamp, book_account, asset_id, account_id, amount_acc, value_acc) "
            "SELECT op_type, operation_id, timestamp, book_account, asset_id, account_id, amount_acc, value_acc "
            "FROM ledger "
            "WHERE id IN (SELECT MAX(id) FROM ledger WHERE timestamp >= :frontier "
            "GROUP BY op_type, operation_id, book_account, account_id, asset_id)", [(":frontier", frontier)])
        JalSettings().setValue('RebuildDB', 0)
        if exception_happened:
            logging.error(self.tr("Exception happened. Ledger is incomplete. Please correct errors listed in log"))
        else:
            logging.info(self.tr("Ledger is complete. Elapsed time: ") + f"{datetime.now() - start_time}" +
                         self.tr(", new frontier: ") + f"{ts2dt(last_timestamp)}")

        self.updated.emit()

    def showRebuildDialog(self, parent):
        rebuild_dialog = RebuildDialog(parent, self.getCurrentFrontier())
        if rebuild_dialog.exec():
            self.rebuild(from_timestamp=rebuild_dialog.getTimestamp(),
                         fast_and_dirty=rebuild_dialog.isFastAndDirty())
