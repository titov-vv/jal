import sys
import logging
import traceback
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from PySide6.QtCore import Signal, Slot, QObject, QDate, QEvent, QTimer
from PySide6.QtWidgets import QDialog, QMessageBox, QApplication
from jal.constants import BookAccount, Setup
from jal.db.helpers import format_decimal
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.settings import JalSettings
from jal.db.operations import LedgerTransaction, LedgerError, LedgerAssetShortage
from jal.db.rebase_residue import RebaseResidue
from jal.widgets.helpers import ts2dt, ts2d, set_date_formats
from jal.ui.ui_rebuild_window import Ui_ReBuildDialog


# ----------------------------------------------------------------------------------------------------------------------
# Class to display window with ledger rebuild configuration options
class RebuildDialog(QDialog):
    def __init__(self, parent, frontier):
        super().__init__(parent)
        self.ui = Ui_ReBuildDialog()
        self.ui.setupUi(self)
        set_date_formats(self)

        self.ui.LastRadioButton.toggle()   # Set default option selection
        self.frontier = frontier
        frontier_text = ts2d(frontier)
        self.ui.FrontierDateLabel.setText(frontier_text)
        self.ui.CustomDateEdit.setDate(QDate.currentDate())
        self.ui.AllRadioButton.installEventFilter(self)
        self.ui.LastRadioButton.installEventFilter(self)
        self.ui.DateRadionButton.installEventFilter(self)

        # center dialog with respect to parent window
        x = parent.x() + parent.width()/2 - self.width()/2
        y = parent.y() + parent.height()/2 - self.height()/2
        self.setGeometry(x, y, self.width(), self.height())

    def getTimestamp(self):
        if self.ui.LastRadioButton.isChecked():
            return self.frontier
        elif self.ui.DateRadionButton.isChecked():
            return self.ui.CustomDateEdit.dateTime().toSecsSinceEpoch()
        else:  # self.AllRadioButton.isChecked()
            return 0

    def eventFilter(self, watched, event):
        if watched in [self.ui.AllRadioButton, self.ui.LastRadioButton, self.ui.DateRadionButton]:
            if event.type() == QEvent.MouseButtonDblClick:
                watched.setChecked(True)
                QTimer.singleShot(0, self.accept)
        return super().eventFilter(watched, event)


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
    show_progress = Signal(bool)     # Signal is emitted when ledger wants to start or stop display progress
    update_progress = Signal(float)  # Signal is emitted to report current % of execution
    SILENT_REBUILD_THRESHOLD = 1000
    MAX_ABSORBED_RESIDUES = 32       # Loop protection. A rebase residue is booked one per closing of a position, so a ledger may legitimately hold several.

    def __init__(self):
        super().__init__()
        self._cancelled = False
        self.amounts = LedgerAmounts("amount_acc")    # store last amount for [book, account, asset]
        self.values = LedgerAmounts("value_acc")      # together with corresponding value
        # The LedgerError that ended the last rebuild, or None when it ran to the end. The message of it is logged
        # for the user either way; the exception itself is kept so that a caller who knows how to make the stop good
        # can act on what it carries (absorb_residues() below) instead of parsing the text back out.
        self.stopped_by = None

    # Returns timestamp of last operations that were calculated into ledger
    def getCurrentFrontier(self):
        current_frontier = self._read("SELECT ledger_frontier FROM frontier")
        if current_frontier == '':
            current_frontier = 0
        return current_frontier

    @classmethod
    def get_operations_sequence(cls, begin: int, end: int, account_id: int = 0) -> list:
        sequence = []
        query_text = "SELECT otype, oid, opart, timestamp, account_id " \
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
    # Returns a list of [otype, oid, opart, timestamp, account_id, amount] ordered by timestamp
    # collected from 'ledger' table with given WHERE statement set as condition and parameters
    def _get_operations_by_filter(cls, condition, parameters) -> list:
        operations = []
        query = cls._exec(
            f"SELECT otype, oid, opart, timestamp, account_id, amount, category_id, tag_id, peer_id FROM ledger "
            f"{condition} ORDER BY timestamp", parameters, forward_only=True)
        while query.next():
            operations.append(cls._read_record(query, named=True))
        return operations

    @classmethod
    # Return a list of [otype, oid, subtype, timestamp, account_id] of operations that have peer_id involved
    def get_operations_by_peer(cls, begin: int, end: int, peer_id: int) -> list:
        condition = "WHERE peer_id=:peer AND timestamp>=:begin AND timestamp<=:end"
        parameters = [(":begin", begin), (":end", end), (":peer", peer_id)]
        return cls._get_operations_by_filter(condition, parameters)

    @classmethod
    # Return a list of [otype, oid, subtype, timestamp, account_id] of operations that have category_id involved
    def get_operations_by_category(cls, begin: int, end: int, category_id: int) -> list:
        condition = "WHERE category_id=:category AND timestamp>=:begin AND timestamp<=:end"
        parameters = [(":begin", begin), (":end", end), (":category", category_id)]
        return cls._get_operations_by_filter(condition, parameters)

    @classmethod
    # Return a list of [otype, oid, subtype, timestamp, account_id] of operations that have tag_id involved
    def get_operations_by_tag(cls, begin: int, end: int, tag_id: int) -> list:
        condition = "WHERE tag_id=:tag AND timestamp>=:begin AND timestamp<=:end"
        parameters = [(":begin", begin), (":end", end), (":tag", tag_id)]
        return cls._get_operations_by_filter(condition, parameters)

    # Add one more transaction to 'book' of ledger.
    # Parameters:
    # operation - ledger operation that is being processed
    # book - ledger accounting book that is being modified by operation
    # amount - money or asset amount that is being processed
    # part - identifier of operation part, specific for each operation type and may have different meaning (0 is default value)
    # If book is Assets and value is not None then amount contains Asset Quantity and Value contains amount
    #    of money in current account currency. Otherwise, Amount contains only money value.
    # Returns non-zero value if accumulated_value differs from 0.0 when accumulated account is 0.0
    def appendTransaction(self, operation, book, amount, part=0, asset_id=None, value=None, category=None, peer=None, tag=None) -> Decimal:
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
        _ = self._exec("INSERT INTO ledger (timestamp, otype, oid, opart, book_account, asset_id, "
                       "account_id, amount, value, amount_acc, value_acc, peer_id, category_id, tag_id) "
                       "VALUES(:timestamp, :otype, :oid, :opart, :book, :asset_id, :account_id, "
                       ":amount, :value, :amount_acc, :value_acc, :peer_id, :category_id, :tag_id)",
                       [(":timestamp", operation.timestamp()), (":otype", operation.type()),
                        (":oid", operation.oid()), (":opart", part), (":book", book), (":asset_id", asset_id),
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
    def rebuild(self, from_timestamp=-1):
        self._cancelled = False
        self.stopped_by = None
        exception_happened = False
        incomplete_reason = ''    # Set if the rebuild stopped for a recoverable reason (see LedgerError below)
        last_timestamp = 0
        self.amounts.clear()
        self.values.clear()
        if from_timestamp >= 0:
            frontier = from_timestamp
            operations_count = self._read("SELECT COUNT(oid) FROM operation_sequence WHERE timestamp >= :frontier",
                                          [(":frontier", frontier)])
        else:
            frontier = self.getCurrentFrontier()
            operations_count = self._read("SELECT COUNT(oid) FROM operation_sequence WHERE timestamp >= :frontier",
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
        self.show_progress.emit(True)
        logging.info(self.tr("Re-building ledger since: ") + f"{ts2dt(frontier)}")
        start_time = datetime.now()
        _ = self._exec("DELETE FROM trades_closed WHERE close_timestamp >= :frontier", [(":frontier", frontier)])
        _ = self._exec("DELETE FROM ledger WHERE timestamp >= :frontier", [(":frontier", frontier)])
        _ = self._exec("DELETE FROM ledger_totals WHERE timestamp >= :frontier", [(":frontier", frontier)])
        _ = self._exec("DELETE FROM trades_opened WHERE timestamp >= :frontier", [(":frontier", frontier)])
        try:
            query = self._exec("SELECT otype, oid, opart, timestamp, account_id FROM operation_sequence "
                               "WHERE timestamp >= :frontier", [(":frontier", frontier)])
            while query.next():
                data = self._read_record(query, named=True)
                last_timestamp = data['timestamp']
                operation = LedgerTransaction().get_operation(data['otype'], data['oid'], data['opart'])
                operation.processLedger(self)
                self.update_progress.emit(100.0 * query.at() / operations_count)
                QApplication.processEvents()
                if self._cancelled:
                    exception_happened = True
                    logging.warning(self.tr("Interrupted by user"))
                    break
        except LedgerError as e:
            # An expected stop: the data is sound but something the ledger needs isn't there yet (a quote to value
            # an operation, a setting that isn't filled in, ...). The ledger simply ends earlier than it might, so
            # the user gets the reason and what to do about it - not a traceback of a crash.
            self.stopped_by = e
            if "pytest" in sys.modules:  # Throw exception if we are in test mode or handle it if we are live
                raise e
            incomplete_reason = str(e)
        except Exception as e:
            if "pytest" in sys.modules:  # Throw exception if we are in test mode or handle it if we are live
                raise e
            exception_happened = True
            logging.error(f"{traceback.format_exc()}")  # Full log for anything unexpected
        finally:
            self.show_progress.emit(False)
        # Fill ledger totals values
        # NOFIXME: Table 'ledger_totals' may be replaced by a view. But it will impact performance heavily as
        # this view won't have indices for optimal performance
        _ = self._exec(
            "INSERT INTO ledger_totals"
            "(otype, oid, timestamp, book_account, asset_id, account_id, amount_acc, value_acc) "
            "SELECT otype, oid, timestamp, book_account, asset_id, account_id, amount_acc, value_acc "
            "FROM ledger "
            "WHERE id IN (SELECT MAX(id) FROM ledger WHERE timestamp >= :frontier "
            "GROUP BY otype, oid, book_account, account_id, asset_id)", [(":frontier", frontier)])
        JalSettings().setValue('RebuildDB', 0)
        if exception_happened:
            logging.error(self.tr("Exception happened. Ledger is incomplete. Please correct errors listed in log"))
        elif incomplete_reason:
            # A warning and not an error - the ledger is incomplete but nothing went wrong and the user has a way
            # to finish it, so it is reported in the gentler colour of the log viewer and status bar
            logging.warning(self.tr("Ledger is incomplete, it stopped at ") + f"{ts2dt(last_timestamp)}: "
                            + incomplete_reason)
        else:
            logging.info(self.tr("Ledger is complete. Elapsed time: ") + f"{datetime.now() - start_time}" +
                         self.tr(", new frontier: ") + f"{ts2dt(last_timestamp)}")
            self.report_position_mismatches()

        self.updated.emit()

    # Every ledger posting is rounded to the precision of its account (see appendTransaction) while an open lot keeps
    # all the digits it has, so a position held on an account whose precision is smaller than its asset really uses
    # ends up described by two different numbers. Nothing shows it while the position is held - it surfaces on the
    # disposal that closes it, which either comes up short and stops the whole rebuild or leaves a dust lot that no
    # future operation can consume. It is reported here, where every position is up to date, and only when the gap is
    # bigger than what the FIFO matching absorbs (Setup.LOT_QTY_TOLERANCE): that is exactly the gap a future disposal
    # would NOT pass over silently.
    def report_position_mismatches(self):
        lots = defaultdict(Decimal)
        # The latest state of every slice, the way JalAccount.open_trades_list() takes it, for all positions at once.
        # Summed in Python because the amounts are decimals kept as TEXT and SQL SUM() would coerce them to float.
        query = self._exec("WITH open_trades_numbered AS "
                           "(SELECT account_id, asset_id, remaining_qty, "
                           "ROW_NUMBER() OVER (PARTITION BY slice_id ORDER BY timestamp DESC, id DESC) AS row_no "
                           "FROM trades_opened) "
                           "SELECT account_id, asset_id, remaining_qty FROM open_trades_numbered "
                           "WHERE row_no=1 AND remaining_qty!=:zero", [(":zero", format_decimal(Decimal('0')))])
        while query.next():
            account_id, asset_id, qty = self._read_record(query, cast=[int, int, Decimal])
            lots[(account_id, asset_id)] += qty
        query = self._exec("SELECT account_id, asset_id, amount_acc FROM ledger WHERE book_account=:assets "
                           "AND id IN (SELECT MAX(id) FROM ledger WHERE book_account=:assets "
                           "GROUP BY account_id, asset_id)", [(":assets", BookAccount.Assets)])
        while query.next():
            account_id, asset_id, amount = self._read_record(query, cast=[int, int, Decimal])
            held = lots[(account_id, asset_id)]
            if abs(held - amount) <= abs(amount) * Decimal(Setup.LOT_QTY_TOLERANCE):
                continue
            account = JalAccount(account_id)
            logging.warning(self.tr("Open lots don't add up to the position, check the account precision: ")
                            + f"{account.name()} - {JalAsset(asset_id).symbol()}: "
                            + f"{held} vs {amount}, precision {account.precision()}")

    # Finishes a ledger that halted one crumb short of the withdrawal that closes a rebasing position - see
    # RebaseResidue for what is and isn't booked here. The pass drives the rebuild itself because the halt is the
    # only place the numbers exist: the ledger reports where it stopped and by how much, the residue is booked, and
    # the next rebuild resumes past it. A position opened and closed several times leaves one residue per closing,
    # so this repeats until the ledger completes, refuses or fails - never more times than there are conversions to
    # stop at. Returns how many residues were booked.
    # 'interrupted' is asked between the passes, each of which is a full rebuild, and tells that the caller was
    # stopped; a Stop pressed on the ledger itself is taken through on_cancel() and needs no callback.
    def absorb_residues(self, interrupted=None) -> int:
        absorbed = 0
        reconciler = RebaseResidue()
        for _ in range(self.MAX_ABSORBED_RESIDUES):
            try:
                self.rebuild()
            except LedgerError:
                pass          # under pytest rebuild() re-raises what it stopped on; 'stopped_by' is set either way
            except Exception as error:   # a failure here must not fail whatever asked for the rebuild
                logging.warning(self.tr("Rebase residue could not be checked: ") + f"{error}")
                return absorbed
            if self._cancelled or (interrupted is not None and interrupted()):
                logging.warning(self.tr("Absorption of rebase residues was interrupted by user"))
                return absorbed
            if not isinstance(self.stopped_by, LedgerAssetShortage):
                return absorbed   # the ledger is complete, or stopped on something this can't make good
            if not reconciler.absorb(self.stopped_by):
                return absorbed
            absorbed += 1
        logging.warning(self.tr("Too many rebase residues in a row - the ledger was left incomplete"))
        return absorbed

    def showRebuildDialog(self, parent):
        rebuild_dialog = RebuildDialog(parent, self.getCurrentFrontier())
        if rebuild_dialog.exec():
            self.rebuild(from_timestamp=rebuild_dialog.getTimestamp())

    @Slot()
    def on_cancel(self):
        self._cancelled = True
