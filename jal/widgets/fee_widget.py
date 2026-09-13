from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Slot, Signal, QByteArray
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLineEdit, QComboBox, QToolButton, QDataWidgetMapper
from PySide6.QtSql import QSqlTableModel

from jal.constants import PredefinedAsset
from jal.db.account import JalAccount
from jal.db.asset_models import SymbolsListModel
from jal.db.common_models import AccountListModel
from jal.db.operations import FeeKind
from jal.db.symbol import JalSymbol
from jal.db.view_model import JalViewModel
from jal.widgets.account_select import AccountCurrencyLabel
from jal.widgets.assets_dialogs import SymbolListDialog
from jal.widgets.delegates import WidgetMapperDelegateBase, FloatDelegate
from jal.widgets.helpers import layout_step
from jal.widgets.icons import JalIcon
from jal.widgets.reference_dialogs import AccountListDialog
from jal.widgets.reference_selector import ReferenceSelectorWidget


# ----------------------------------------------------------------------------------------------------------------------
class FeeWidgetDelegate(WidgetMapperDelegateBase):
    def __init__(self, precision, parent=None):
        super().__init__(parent=parent)
        self.delegates = {'amount': FloatDelegate(precision, allow_tail=True)}


# ----------------------------------------------------------------------------------------------------------------------
# The fee an operation bears, as a widget: a row of 'fees' shown, edited and detached where the operation is edited.
# Placed from Qt Designer as one opaque widget - everything bound to the database arrives at run time through
# setup_fees(), the way ReferenceSelectorWidget takes setup_selector(), so Designer's bare createWidget() is enough.
#
# It holds ZERO OR ONE fee and binds the FIRST row. The schema, the ledger part and the import path are uncapped, so
# THE RULE THAT COMES WITH THAT: never delete or overwrite a row this widget does not show. An operation that carries
# a second fee must still save with both.
#
# The operation declares what it may be charged - the allowed kinds and whether the fee account can differ from its
# own - and the widget enforces it alone. That is what replaces the fee-kind combos, the stacked pages and the
# "include fee" checkboxes that each editor carried a copy of.
class FeeWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._model = None
        self._mapper = None
        self._kinds = [FeeKind.Commission]
        self._linked_account = 0     # Pushed in by the parent where the fee can only be charged on its own account
        self._account_may_differ = True

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(max(1, layout_step(self) // 2))
        self.kind = QComboBox()
        self.layout.addWidget(self.kind)
        self.amount = QLineEdit()
        self.layout.addWidget(self.amount)
        self.currency = AccountCurrencyLabel(self)
        self.layout.addWidget(self.currency)
        self.symbol = ReferenceSelectorWidget(self, validate=False)
        self.layout.addWidget(self.symbol)
        self.account = ReferenceSelectorWidget(self, validate=False)
        self.layout.addWidget(self.account)
        self.add_button = QToolButton()
        self.add_button.setIcon(JalIcon[JalIcon.ADD])
        self.add_button.setAutoRaise(True)
        self.add_button.setVisible(False)
        self.layout.addWidget(self.add_button)
        self.del_button = QToolButton()
        self.del_button.setIcon(JalIcon[JalIcon.REMOVE])
        self.del_button.setAutoRaise(True)
        self.layout.addWidget(self.del_button)
        self.setLayout(self.layout)
        self.setFocusProxy(self.amount)

        self.add_button.clicked.connect(self.attach)
        self.del_button.clicked.connect(self.detach)
        self.kind.activated.connect(self.kind_selected)

    # Binds the widget to the database. 'kinds' are the FeeKind values this operation type may be charged in - one of
    # them and the kind is derived and shown nowhere, more than one and it is chosen here. 'account_may_differ' says
    # whether the fee can be borne by an account other than the operation's own; where it can't, the parent pushes
    # its own selection in with set_fee_account() and the control is hidden. 'precision' is the amount's delegate.
    def setup_fees(self, kinds: list, account_may_differ: bool = False, precision: int = 2, parent=None):
        self._kinds = list(kinds)
        self._account_may_differ = account_may_differ
        self.symbol.setup_selector(SymbolsListModel, SymbolListDialog, parent if parent is not None else self)
        self.account.setup_selector(AccountListModel, AccountListDialog, parent if parent is not None else self)
        self.kind.clear()
        for kind in self._kinds:
            self.kind.addItem(self._kind_name(kind), kind)
        self.kind.setVisible(len(self._kinds) > 1)
        self.account.setVisible(self._account_may_differ)

        self._model = FeeModel(self)
        self._mapper = QDataWidgetMapper(self)
        self._mapper.setModel(self._model)
        self._mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
        self._mapper.setItemDelegate(FeeWidgetDelegate(precision, self._mapper))
        self._mapper.addMapping(self.amount, self._model.fieldIndex("amount"))
        self._mapper.addMapping(self.currency, self._model.fieldIndex("account_id"))
        self._mapper.addMapping(self.symbol, self._model.fieldIndex("symbol_id"), QByteArray("selected_id_str"))
        self._mapper.addMapping(self.account, self._model.fieldIndex("account_id"), QByteArray("selected_id_str"))
        self.symbol.changed.connect(self._mapper.submit)
        self.symbol.changed.connect(self.changed)
        self.account.changed.connect(self._mapper.submit)
        self.account.changed.connect(self.changed)
        self.amount.textEdited.connect(self.changed)

    # The fee rows of one operation. Set BEFORE the parent loads the operation into its own mapper, the way
    # CorporateActionWidget filters its results model.
    def set_operation(self, oid):
        self._model.setFilter(f"fees.operation_id = {oid}")
        self._model.select()
        self._show_current_fee()

    # The account the parent has selected, where the fee can only be borne by it. Pushed on the user's change and
    # never on display: a stored fee whose account disagrees with its parent (an importer can write one) must not be
    # rewritten by merely opening the operation.
    @Slot(int)
    def set_fee_account(self, account_id: int):
        self._linked_account = account_id
        if self._current_row() is not None and not self._account_may_differ:
            self.account.selected_id = account_id
            self._mapper.submit()

    # Every fee the widget holds, as dicts - what the parent's validation reads. A detached row is not one of them.
    def fees(self) -> list:
        if self._model is None:
            return []
        return [self._row_data(row) for row in range(self._model.rowCount()) if not self._model.row_is_deleted(row)]

    # Why this fee can't be saved, or '' when it can. The rules are the ones the five editors carried: an attached
    # fee has a non-zero amount, gas is paid in a crypto asset, and a fee is collected from an account with an
    # organization (see FeeCarrier.processFee).
    def validation_error(self) -> str:
        for fee in self.fees():
            if not fee['amount']:
                return self.tr("A fee is attached to the operation, but its amount is empty")
            if fee['symbol_id']:
                if JalSymbol(fee['symbol_id']).asset().type() != PredefinedAsset.Crypto:
                    return self.tr("A fee may be paid in a crypto asset only")
            elif self._is_asset_kind(fee['kind']):
                return self.tr("An asset isn't chosen to pay the gas in")
            if not fee['account_id']:
                return self.tr("An account isn't chosen for fee collection from")
            if not JalAccount(fee['account_id']).organization():
                return self.tr("Can't collect fee from an account without organization assigned")
        return ''

    # Stamps every row with the operation it belongs to and writes them. Called from INSIDE the parent's own
    # transaction in its _save() - the widget owns the rows and never the transaction.
    def submit(self, oid) -> bool:
        symbol_column = self._model.fieldIndex("symbol_id")
        for row in range(self._model.rowCount()):
            self._model.setData(self._model.index(row, self._model.fieldIndex("operation_id")), oid)
            # A fee paid in money names no asset, and the selector reads back as 0 - which is not an asset but a
            # reference to none, and the column has to be NULL to say so.
            if self._model.data(self._model.index(row, symbol_column)) in (None, '', '0', 0):
                self._model.setData(self._model.index(row, symbol_column), None)
        return self._model.submitAll()

    def revert(self):
        self._model.revertAll()
        self._show_current_fee()

    # Re-inserts the fee under a new operation, as copyNew() does for the parent - with no parent key, which submit()
    # fills in once the copy has one.
    def copy_to_new(self):
        records = [self._model.record(row) for row in range(self._model.rowCount())
                   if not self._model.row_is_deleted(row)]
        self._model.setFilter("fees.operation_id = 0")
        self._model.select()
        for record in reversed(records):
            record.setNull("id")
            record.setNull("operation_id")
            assert self._model.insertRows(0, 1)
            self._model.setRecord(0, record)
        self._show_current_fee()

    @Slot()
    def attach(self):
        record = self._model.record()
        record.setNull("id")
        record.setNull("operation_id")
        record.setValue("idx", 0)
        record.setValue("account_id", self._linked_account)
        record.setValue("amount", '0')
        record.setValue("kind", self._kinds[0])
        if self._is_asset_kind(self._kinds[0]):
            record.setValue("symbol_id", 0)
        else:
            record.setNull("symbol_id")
        assert self._model.insertRecord(-1, record)
        self._show_current_fee()
        self.changed.emit()

    @Slot()
    def detach(self):
        row = self._current_row()
        if row is not None:
            self._model.removeRow(row)
        self._show_current_fee()
        self.changed.emit()

    @Slot()
    def kind_selected(self, index):
        kind = self.kind.itemData(index)
        row = self._current_row()
        if row is None:
            return
        self._model.setData(self._model.index(row, self._model.fieldIndex("kind")), kind)
        if not self._is_asset_kind(kind):   # a money fee is paid in no asset
            self.symbol.selected_id = 0
            self._model.setData(self._model.index(row, self._model.fieldIndex("symbol_id")), None)
        self._show_current_fee()
        self.changed.emit()

    # Named here and not on FeeKind, which is a storage constant and has no business carrying display text
    def _kind_name(self, kind) -> str:
        return {FeeKind.Commission: self.tr("Fee"), FeeKind.Gas: self.tr("Gas"),
                FeeKind.Rent: self.tr("Rent")}[kind]

    @staticmethod
    def _is_asset_kind(kind) -> bool:
        return int(kind) != FeeKind.Commission

    # The row the widget shows, or None when no fee is attached. It is the first one that isn't detached - the widget
    # binds one row and leaves any other alone.
    def _current_row(self):
        if self._model is None:
            return None
        for row in range(self._model.rowCount()):
            if not self._model.row_is_deleted(row):
                return row
        return None

    def _row_data(self, row) -> dict:
        record = self._model.record(row)
        try:
            amount = Decimal(record.value("amount"))
        except (TypeError, InvalidOperation):
            amount = Decimal('0')
        symbol_id = record.value("symbol_id")
        return {'amount': amount, 'account_id': int(record.value("account_id") or 0),
                'symbol_id': int(symbol_id) if symbol_id else 0, 'kind': int(record.value("kind") or 0)}

    # Either the fee or the "+" that attaches one, and within the fee only the controls its kind and its operation
    # allow. This is the one place the widget's appearance is decided.
    def _show_current_fee(self):
        row = self._current_row()
        attached = row is not None
        if attached:
            self._mapper.setCurrentIndex(row)
            kind = self._row_data(row)['kind']
            if self.kind.findData(kind) >= 0:
                self.kind.setCurrentIndex(self.kind.findData(kind))
        else:
            kind = self._kinds[0]
        asset_kind = self._is_asset_kind(kind)
        self.add_button.setVisible(not attached)
        self.del_button.setVisible(attached)
        self.amount.setVisible(attached)
        self.kind.setVisible(attached and len(self._kinds) > 1)
        self.symbol.setVisible(attached and asset_kind)
        self.currency.setVisible(attached and not asset_kind)
        self.account.setVisible(attached and self._account_may_differ)

    def tr(self, text):
        return QApplication.translate("FeeWidget", text)


# ----------------------------------------------------------------------------------------------------------------------
# The child model of one operation's fees. It has no view - the widget above is the view - but it is a JalViewModel
# for row_is_deleted(): with OnManualSubmit a removed row is only MARKED until the parent's save, so the widget has
# to be able to tell a detached row from one that is still there.
class FeeModel(JalViewModel):
    def __init__(self, parent):
        super().__init__(parent, "fees")
        self._columns = ["id", "operation_id", "idx", "account_id", "symbol_id", "amount", "kind"]
        self.setEditStrategy(QSqlTableModel.OnManualSubmit)
