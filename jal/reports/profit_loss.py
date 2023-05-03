import decimal
from functools import partial
from decimal import Decimal

from PySide6.QtCore import Qt, Slot, QObject, QAbstractTableModel
from jal.ui.reports.ui_profit_loss_report import Ui_ProfitLossReportWidget
from jal.reports.reports import Reports
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.constants import BookAccount, PredefinedCategory
from jal.widgets.helpers import month_list
from jal.widgets.delegates import FloatDelegate
from jal.widgets.mdi import MdiWidget

JAL_REPORT_CLASS = "ProfitLossReport"


#-----------------------------------------------------------------------------------------------------------------------
class ProfitLossModel(QAbstractTableModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._columns = [self.tr("Period"), self.tr("Money"), self.tr("In / Out"), self.tr("Dividends"), self.tr("%"),
                         self.tr("Fees"), self.tr("Taxes"), self.tr("Assets"), self.tr("P&L"), self.tr("Total"),
                         self.tr("Change"), self.tr("Change, %")]
        self.month_name = [
            self.tr('Jan'), self.tr('Feb'), self.tr('Mar'), self.tr('Apr'), self.tr('May'), self.tr('Jun'),
            self.tr('Jul'), self.tr('Aug'), self.tr('Sep'), self.tr('Oct'), self.tr('Nov'), self.tr('Dec')
        ]
        self._view = parent_view
        self._data = []
        self._month_list = []
        self._begin = 0
        self._end = 0
        self._account_id = 0
        self._float_delegate = None
        self._color_delegate = None
        self._percent_delegate = None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section]
        return None

    def headerWidth(self, section):
        return self._view.horizontalHeader().sectionSize(section)

    def data(self, index, role=Qt.DisplayRole, field=''):
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]

    def setDatesRange(self, begin, end):
        self._begin = begin
        self._end = end
        self._month_list = month_list(begin, end)
        self.prepareData()
        self.configureView()

    def setAccount(self, account_id):
        self._account_id = account_id
        self.prepareData()
        self.configureView()

    # returns a dictionary with following keys (period is given by begin and end timestamps):
    # money - amount of money by end of the period
    # transfers - amount of money that came in(+) and out(-) of the account
    # dividends, interests, fees, taxes - amount of money that changed account value due to such events
    # assets - valuation of assets held by account by prices at the end of the period
    # p&l - profit and loss of deals closed during the period
    # total - total amount of money and assets by end of the period
    def data4period(self, begin: int, end: int, account: JalAccount) -> dict:
        assets = account.assets_list(end)
        asset_value = Decimal('0')
        for asset_data in assets:
            asset = asset_data['asset']
            asset_value += asset_data['amount'] * asset.quote(end, account.currency())[1]
        data = {
            'money': account.get_asset_amount(end, account.currency()),
            'transfers': -account.get_book_turnover(BookAccount.Transfers, begin, end),
            'dividends': -account.get_category_turnover(PredefinedCategory.Dividends, begin, end),
            'interest': -account.get_category_turnover(PredefinedCategory.Interest, begin, end),
            'fees': -account.get_category_turnover(PredefinedCategory.Fees, begin, end),
            'taxes': -account.get_category_turnover(PredefinedCategory.Taxes, begin, end),
            'assets': asset_value,
            'p&l': -account.get_category_turnover(PredefinedCategory.Profit, begin, end),
            'total': account.get_asset_amount(end, account.currency()) + asset_value
        }
        return data

    def prepareData(self):
        self._data = []
        money_p = assets_p = money_0 = assets_0 = None
        if not self._month_list:
            self.modelReset.emit()
            return
        account = JalAccount(self._account_id)
        # Prepend table with initial row and extend it with totals row
        months = [{'begin_ts': self._month_list[0]['begin_ts'], 'end_ts': self._month_list[0]['begin_ts']}]
        months.extend(self._month_list)
        months.append({'begin_ts': self._month_list[0]['begin_ts'], 'end_ts': self._month_list[-1]['end_ts']})
        for i, month in enumerate(months):
            values = self.data4period(month['begin_ts'], month['end_ts'], account)
            if i == 0:
                row_name = self.tr("Period start")
                money_p = money_0 = values['money']
                assets_p = assets_0 = values['assets']
            elif i == len(months) - 1:
                row_name = self.tr("Period end")
                money_p = money_0
                assets_p = assets_0
            else:
                row_name = f"{month['year']} {self.month_name[month['number'] - 1]}"
            try:
                rel_change = ((values['money'] + values['assets']) - (money_p + assets_p)) / (money_p + assets_p)
            except (ZeroDivisionError, decimal.InvalidOperation):
                rel_change = Decimal('0')
            data_row = [row_name, values['money'], values['transfers'], values['dividends'], values['interest'],
                        values['fees'], values['taxes'], values['assets'], values['p&l'],
                        values['total'], (values['money'] + values['assets']) - (money_p + assets_p),
                        rel_change]
            self._data.append(data_row)
            money_p = values['money']
            assets_p = values['assets']
        self.modelReset.emit()

    def configureView(self):
        self._view.setModel(self)
        font = self._view.horizontalHeader().font()
        font.setBold(True)
        self._view.horizontalHeader().setFont(font)
        self._float_delegate = FloatDelegate(2, allow_tail=False)
        self._color_delegate = FloatDelegate(2, allow_tail=False, colors=True)
        self._percent_delegate = FloatDelegate(2, allow_tail=False, colors=True, percent=True)
        self._view.setItemDelegateForColumn(1, self._float_delegate)
        self._view.setItemDelegateForColumn(2, self._color_delegate)
        self._view.setItemDelegateForColumn(3, self._float_delegate)
        self._view.setItemDelegateForColumn(4, self._float_delegate)
        self._view.setItemDelegateForColumn(5, self._float_delegate)
        self._view.setItemDelegateForColumn(6, self._float_delegate)
        self._view.setItemDelegateForColumn(7, self._float_delegate)
        self._view.setItemDelegateForColumn(8, self._color_delegate)
        self._view.setItemDelegateForColumn(9, self._float_delegate)
        self._view.setItemDelegateForColumn(10, self._color_delegate)
        self._view.setItemDelegateForColumn(11, self._percent_delegate)


# ----------------------------------------------------------------------------------------------------------------------
class ProfitLossReport(QObject):
    def __init__(self):
        super().__init__()
        self.name = self.tr("P&L by Account")
        self.window_class = "ProfitLossReportWindow"


# ----------------------------------------------------------------------------------------------------------------------
class ProfitLossReportWindow(MdiWidget):
    def __init__(self, parent: Reports, settings: dict = None):
        super().__init__(parent.mdi_area())
        self.ui = Ui_ProfitLossReportWidget()
        self.ui.setupUi(self)
        self._parent = parent
        self.name = self.tr("P&L by Account")

        self.pl_model = ProfitLossModel(self.ui.ReportTableView)
        self.ui.ReportTableView.setModel(self.pl_model)

        self.connect_signals_and_slots()

    def connect_signals_and_slots(self):
        self.ui.ReportRange.changed.connect(self.ui.ReportTableView.model().setDatesRange)
        self.ui.ReportAccountEdit.changed.connect(self.onAccountChange)
        self.ui.SaveButton.pressed.connect(partial(self._parent.save_report, self.name, self.ui.ReportTableView.model()))

    @Slot()
    def onAccountChange(self):
        account_id = self.ui.ReportAccountEdit.selected_id
        self.ui.ReportTableView.model().setAccount(account_id)
        self.ui.CurrencyLbl.setText(self.tr("Currency: ") + JalAsset(JalAccount(account_id).currency()).symbol())
