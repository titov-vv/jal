import base64
from decimal import Decimal

from PySide6.QtCore import Qt, QAbstractTableModel, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QHeaderView
from jal.constants import Setup
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.country import JalCountry
from jal.db.helpers import localize_decimal
from jal.db.residence import JalResidence
from jal.db.settings import JalSettings
from jal.data_export.taxes import TaxReport
from jal.data_export.tax_estimate import TaxEstimate
from jal.ui.ui_position_details_window import Ui_PositionDetailsWindow
from jal.widgets.delegates import FloatDelegate
from jal.widgets.helpers import ts2d, set_grids_metrics, restore_columns, restore_splitters, save_splitters
from jal.widgets.icons import JalIcon
from jal.widgets.mdi import MdiWidget
from jal.widgets.price_chart import ChartWidget, lot_markers, price_history


# ----------------------------------------------------------------------------------------------------------------------
# The open lots of a position at 'quote', each with a check box that says whether it is counted; the footer holds
# the totals of the checked ones
class LotsModel(QAbstractTableModel):
    CHECK, DATE, HELD, QTY, PRICE, COST, PL, PL_PERCENT = range(8)
    checkedChanged = Signal()

    def __init__(self, view, lots, quote, timestamp, currency):
        super().__init__(view)
        self._view = view
        self._lots = lots
        self._quote = quote
        self._timestamp = timestamp
        self._checked = [True] * len(lots)
        self._columns = ["", self.tr("Date"), self.tr("Held, days"), self.tr("Qty"), self.tr("Price, ") + currency,
                         self.tr("Cost, ") + currency, self.tr("P/L, ") + currency, self.tr("P/L, %")]
        self._delegates = []

    def rowCount(self, parent=None):
        return len(self._lots)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._columns[section]
            if role == Qt.ToolTipRole and section == self.CHECK:
                return self.tr("Check or uncheck all lots")
        return None

    def flags(self, index):
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return flags | Qt.ItemIsUserCheckable if index.column() == self.CHECK else flags

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        lot, column = self._lots[index.row()], index.column()
        if role == Qt.CheckStateRole and column == self.CHECK:
            return Qt.Checked if self._checked[index.row()] else Qt.Unchecked
        if role == Qt.DisplayRole:
            return self._value(lot, column)
        if role == Qt.TextAlignmentRole and column > self.DATE:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.CheckStateRole or index.column() != self.CHECK:
            return False
        self._checked[index.row()] = Qt.CheckState(value) == Qt.Checked
        self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), self.columnCount() - 1))
        self.checkedChanged.emit()
        return True

    # Checks every lot, or unchecks every lot if all are checked already
    def toggle_all(self):
        if not self._lots:
            return
        self._checked = [not all(self._checked)] * len(self._lots)
        self.dataChanged.emit(self.index(0, 0), self.index(len(self._lots) - 1, self.columnCount() - 1))
        self.checkedChanged.emit()

    def checked_rows(self) -> set:
        return {i for i, x in enumerate(self._checked) if x}

    def checked_lots(self) -> list:
        return [x for x, checked in zip(self._lots, self._checked) if checked]

    def _value(self, lot, column):
        cost = lot.open_qty() * lot.open_price(adjusted=True)
        if column == self.DATE:
            return ts2d(lot.acquired())
        if column == self.HELD:
            return str((self._timestamp - lot.acquired()) // 86400)
        if column == self.QTY:
            return lot.open_qty()
        if column == self.PRICE:
            return lot.open_price(adjusted=True)
        if column == self.COST:
            return cost
        if column == self.PL:
            return lot.open_qty() * self._quote - cost
        if column == self.PL_PERCENT:
            return (lot.open_qty() * self._quote - cost) / cost if cost else None
        return None

    # (qty, cost) of the checked lots
    def totals(self) -> (Decimal, Decimal):
        lots = self.checked_lots()
        return (sum((x.open_qty() for x in lots), Decimal('0')),
                sum((x.open_qty() * x.open_price(adjusted=True) for x in lots), Decimal('0')))

    # The average cost of a unit of the checked lots, None if none is checked
    def average(self):
        qty, cost = self.totals()
        return cost / qty if qty else None

    def footerData(self, section, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            qty, cost = self.totals()
            pl = qty * self._quote - cost
            if section == self.DATE:
                return self.tr("{checked} of {total} lots").format(checked=len(self.checked_lots()),
                                                                  total=len(self._lots))
            if section == self.QTY:
                return localize_decimal(qty)
            if section == self.PRICE:
                return localize_decimal(cost / qty, precision=2) if qty else ''
            if section == self.COST:
                return localize_decimal(cost, precision=2)
            if section == self.PL:
                return localize_decimal(pl, precision=2)
            if section == self.PL_PERCENT:
                return localize_decimal(pl / cost, precision=2, percent=True) if cost else ''
        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter if section <= self.DATE else Qt.AlignRight | Qt.AlignVCenter
        return None

    def configureView(self):
        self._delegates = [FloatDelegate(0, allow_tail=True, parent=self._view),
                           FloatDelegate(2, allow_tail=True, parent=self._view),
                           FloatDelegate(2, allow_tail=False, parent=self._view),
                           FloatDelegate(2, allow_tail=False, colors=True, parent=self._view),
                           FloatDelegate(2, allow_tail=False, colors=True, percent=True, parent=self._view)]
        for column, delegate in ((self.QTY, 0), (self.PRICE, 1), (self.COST, 2), (self.PL, 3), (self.PL_PERCENT, 4)):
            self._view.setItemDelegateForColumn(column, self._delegates[delegate])
        self._view.horizontalHeader().setSectionResizeMode(self.CHECK, QHeaderView.ResizeToContents)
        digit = self._view.fontMetrics().horizontalAdvance("0")
        for column, digits in ((self.DATE, 12), (self.HELD, 10), (self.QTY, 8), (self.PRICE, 10), (self.COST, 11),
                               (self.PL, 11), (self.PL_PERCENT, 8)):
            self._view.setColumnWidth(column, digit * digits)
        restore_columns(self._view, Setup.COLUMNS_STATE_PREFIX)


# ----------------------------------------------------------------------------------------------------------------------
# A position on 'timestamp': its open lots, the price chart with them and a rough tax on selling the checked ones
class PositionDetails(MdiWidget):
    GEOMETRY_KEY = "WindowGeometry_PositionDetails"

    def __init__(self, account_id, asset_id, currency_id, timestamp, parent=None):
        super().__init__(parent)
        self.ui = Ui_PositionDetailsWindow()
        self.ui.setupUi(self)
        set_grids_metrics(self)

        self._account = JalAccount(account_id)
        self._asset = JalAsset(asset_id)
        self._timestamp = timestamp
        currency = JalAsset(self._account.currency()).symbol()
        self.setWindowTitle(self.tr("Position details: ") + self._asset.symbol(self._account.currency()))
        self.lots = self._account.open_trades_list(self._asset, timestamp)
        quote = self._asset.quote(timestamp, self._account.currency())[1]
        self.ui.QuoteLbl.setText(self.tr("Quote on {date}: {quote} {currency}").format(
            date=ts2d(timestamp), quote=localize_decimal(quote, precision=4), currency=currency))

        self.model = LotsModel(self.ui.LotsView, self.lots, quote, timestamp, currency)
        self.ui.LotsView.setModel(self.model)
        self.model.configureView()

        chart_currency = currency_id if asset_id != currency_id else 1   # a currency is charted against the base one
        trades = lot_markers(self.lots, self._asset, chart_currency)
        quotes, data_range = price_history(self._asset, chart_currency, trades, timestamp)
        self.chart = ChartWidget(self.ui.ChartFrame, quotes, trades, data_range, currency)
        self.ui.ChartLayout.addWidget(self.chart)
        self.ui.PositionDetailsSplitter.setStretchFactor(0, 3)
        self.ui.PositionDetailsSplitter.setStretchFactor(1, 2)

        residence = JalCountry(JalResidence.country(timestamp)).code()
        for code in TaxReport.jurisdictions:
            self.ui.CountryCombo.addItem(JalIcon.country_flag(code),
                                         JalCountry(data={'code': code}, search=True).name(), code)
            if code == residence:
                self.ui.CountryCombo.setCurrentIndex(self.ui.CountryCombo.count() - 1)

        self.model.checkedChanged.connect(self.onLotsChanged)
        self.ui.LotsView.selectionModel().selectionChanged.connect(self.onLotsChanged)
        self.ui.LotsView.horizontalHeader().sectionClicked.connect(self.onHeaderClicked)
        self.chart.lotClicked.connect(self.ui.LotsView.selectRow)
        self.ui.CountryCombo.currentIndexChanged.connect(self.showTax)
        self.onLotsChanged()
        self._restored = False
        QApplication.instance().aboutToQuit.connect(self.save_layout)   # an open window gets no closeEvent on exit
        self.ready = True

    # After addWindow() has sized and centred the window, so that the stored layout wins
    def showEvent(self, event):
        if not self._restored:
            stored = JalSettings().getStr(self.GEOMETRY_KEY)
            if stored:
                self.restoreGeometry(base64.decodebytes(stored.encode('utf-8')))
            restore_splitters(self, Setup.SPLITTER_STATE_PREFIX)
            self._restored = True
        super().showEvent(event)

    @Slot()
    def save_layout(self):
        JalSettings().setValue(self.GEOMETRY_KEY, base64.encodebytes(self.saveGeometry().data()).decode('utf-8'))
        save_splitters(self, Setup.SPLITTER_STATE_PREFIX)

    def closeEvent(self, event):
        QApplication.instance().aboutToQuit.disconnect(self.save_layout)
        self.save_layout()
        super().closeEvent(event)

    @Slot()
    def onHeaderClicked(self, section):
        if section == LotsModel.CHECK:
            self.model.toggle_all()

    @Slot()
    def onLotsChanged(self):
        selected = self.ui.LotsView.selectionModel().selectedRows()
        self.chart.show_lots(self.model.checked_rows(), selected[0].row() if selected else None, self.model.average())
        self.showTax()

    @Slot()
    def showTax(self):
        code = self.ui.CountryCombo.currentData()
        if code is None:
            return
        estimate = TaxEstimate(code, self._account, self._asset, self._timestamp)
        totals = estimate.totals(self.model.checked_lots())
        tax_currency = estimate.currency_name
        currency = JalAsset(self._account.currency()).symbol()
        rate = f"{localize_decimal(estimate.rate, precision=4)} {tax_currency}/{currency}"
        self.ui.GainValue.setText(f"{localize_decimal(totals['gain'], precision=2)} {tax_currency}")
        if estimate.base_rate is None:
            self.ui.BaseRateValue.setText(self.tr("not known for {year}").format(year=estimate.year))
            self.ui.TaxValue.setText("")
        else:
            self.ui.BaseRateValue.setText(localize_decimal(estimate.base_rate, percent=True) + " %")
            self.ui.TaxValue.setText(f"~ {localize_decimal(totals['tax'], precision=2)} {tax_currency}")
        notes = []
        if code == 'pt':
            self.ui.RateValue.setText(self.tr("{rate} on {date}, cost and value").format(
                rate=rate, date=ts2d(self._timestamp)))
            if totals['excluded']:
                notes.append(self.tr("Crypto held 365 days or more is left out: {count} lot(s).").format(
                    count=totals['excluded']))
            if totals['short_held']:
                notes.append(self.tr("{count} lot(s) held under 365 days: their gain may have to be added to other "
                                     "income (englobamento).").format(count=totals['short_held']))
        else:
            self.ui.RateValue.setText(self.tr("{rate} on {date} for value, cost at each purchase's settlement "
                                              "date").format(rate=rate, date=ts2d(self._timestamp)))
        notes.append(self.tr("Rough estimate: losses of other deals and of earlier years, deductions and fees of "
                             "the sale are not taken into account."))
        self.ui.NoteLbl.setText("\n".join(notes))
