from view_delegate import *
from PySide2 import QtWidgets
from PySide2.QtCore import QObject, SIGNAL
from action_delegate import ActionDelegate, ActionDetailDelegate
from dividend_delegate import DividendSqlDelegate
from trade_delegate import TradeSqlDelegate
from transfer_delegate import TransferSqlDelegate
from CustomUI.helpers import UseSqlTable, ConfigureTableView, ConfigureDataMappers


class TableViewConfig:
    BALANCES = 0
    HOLDINGS = 1
    OPERATIONS = 2
    ACTIONS = 3
    ACTION_DETAILS = 4
    TRADES = 5
    DIVIDENDS = 6
    TRANSFERS = 7

    ACTION_SRC = 0
    ACTION_SIGNAL = 1
    ACTION_SLOT = 2

    table_names = {
        BALANCES: 'balances',
        HOLDINGS: 'holdings',
        OPERATIONS: 'all_operations',
        ACTIONS: 'actions',
        ACTION_DETAILS: 'action_details',
        TRADES: 'trades',
        DIVIDENDS: 'dividends',
        TRANSFERS: 'transfers_combined'
    }

    # if True - then link model 'dataChanged' signal with self.parent.on_data_changed() slot
    notify_changes = {
        BALANCES: False,
        HOLDINGS: False,
        OPERATIONS: False,
        ACTIONS: True,
        ACTION_DETAILS: True,
        TRADES: True,
        DIVIDENDS: True,
        TRANSFERS: True
    }

    table_relations = {
        BALANCES: None,
        HOLDINGS: None,
        OPERATIONS: None,
        ACTIONS: None,
        ACTION_DETAILS: [("category_id", "categories", "id", "name", None),
                         ("tag_id", "tags", "id", "tag", None)],
        TRADES: [("corp_action_id", "corp_actions", "id", "type", None)],
        DIVIDENDS: None,
        TRANSFERS: None
    }

    table_view_columns = {
        BALANCES: [("level1", None, None, None, None),
                   ("level2", None, None, None, None),
                   ("account_name", "Account", -1, None, BalanceAccountDelegate),
                   ("balance", "Balance", 100, None, BalanceAmountDelegate),
                   ("currency_name", " ", 35, None, BalanceCurrencyDelegate),
                   ("balance_adj", "Balance, RUB", 110, None, BalanceAmountAdjustedDelegate),
                   ("days_unreconciled", None, None, None, None),
                   ("active", None, None, None, None)],
        HOLDINGS: [("level1", None, None, None, None),
                   ("level2", None, None, None, None),
                   ("currency", None, None, None, None),
                   ("account", "C/A", 32, None, HoldingsAccountDelegate),
                   ("asset", " ", None, None, None),
                   ("asset_name", "Asset", -1, None, None),
                   ("qty", "Qty", None, None, HoldingsFloatDelegate),
                   ("open", "Open", None, None, HoldingsFloat4Delegate),
                   ("quote", "Last", None, None, HoldingsFloat4Delegate),
                   ("share", "Share, %", None, None, HoldingsFloat2Delegate),
                   ("profit_rel", "P/L, %", None, None, HoldingsProfitDelegate),
                   ("profit", "P/L", None, None, HoldingsProfitDelegate),
                   ("value", "Value", None, None, HoldingsFloat2Delegate),
                   ("value_adj", "Value, RUB", None, None, HoldingsFloat2Delegate)],
        OPERATIONS: [("type", " ", 10, None, OperationsTypeDelegate),
                     ("id", None, None, None, None),
                     ("timestamp", "Timestamp", 150, None, OperationsTimestampDelegate),
                     # TODO: check if possible implement correct sizehint for "00/00/0000 00:00:00"
                     ("account_id", None, None, None, None),
                     ("account", "Account", 300, None, OperationsAccountDelegate),
                     ("num_peer", None, None, None, None),
                     ("asset_id", None, None, None, None),
                     ("asset", None, None, None, None),
                     ("asset_name", None, None, None, None),
                     ("note", "Notes", -1, None, OperationsNotesDelegate),
                     ("note2", None, None, None, None),
                     ("amount", "Amount", None, None, OperationsAmountDelegate),
                     ("qty_trid", None, None, None, None),
                     ("price", None, None, None, None),
                     ("fee_tax", None, None, None, None),
                     ("t_amount", "Balance", None, None, OperationsTotalsDelegate),
                     ("t_qty", None, None, None, None),
                     ("currency", "Currency", None, None, OperationsCurrencyDelegate),
                     ("reconciled", None, None, None, None)],
        ACTIONS: [],
        ACTION_DETAILS: [("id", None, None, None, None),
                         ("pid", None, None, None, None),
                         ("category_id", "Category", 200, None, ActionDetailDelegate),
                         ("tag_id", "Tag", 200, None, ActionDetailDelegate),
                         ("sum", "Amount", 100, None, ActionDetailDelegate),
                         ("alt_sum", "Amount *", 100, None, ActionDetailDelegate),
                         ("note", "Note", -1, None, None)],
        TRADES: [],
        DIVIDENDS: [],
        TRANSFERS: []
    }

    mapper_delegates = {
        BALANCES: None,
        HOLDINGS: None,
        OPERATIONS: None,
        ACTIONS: ActionDelegate,
        ACTION_DETAILS: None,
        TRADES: TradeSqlDelegate,
        DIVIDENDS: DividendSqlDelegate,
        TRANSFERS: TransferSqlDelegate
    }

    def __init__(self, parent):
        self.parent = parent
        self.delegates_storage = []   #  Keep references to all created delegates here
        self.views = {
            self.BALANCES: parent.BalancesTableView,
            self.HOLDINGS: parent.HoldingsTableView,
            self.OPERATIONS: parent.OperationsTableView,
            self.ACTIONS: None,
            self.ACTION_DETAILS: parent.ActionDetailsTableView,
            self.TRADES: None,
            self.DIVIDENDS: None,
            self.TRANSFERS: None
        }
        self.mappers = {}
        self.widget_mappers = {
            self.BALANCES: None,
            self.HOLDINGS: None,
            self.OPERATIONS: None,
            self.ACTIONS: [("timestamp", parent.ActionTimestampEdit, parent.widthForTimestampEdit, None),
                           ("account_id", parent.ActionAccountWidget, 0, None),
                           ("peer_id", parent.ActionPeerWidget, 0, None)],
            self.ACTION_DETAILS: None,
            self.TRADES: [("timestamp", parent.TradeTimestampEdit, parent.widthForTimestampEdit, None),
                          ("corp_action_id", parent.TradeActionWidget, 0, None),
                          ("account_id", parent.TradeAccountWidget, 0, None),
                          ("asset_id", parent.TradeAssetWidget, 0, None),
                          ("settlement", parent.TradeSettlementEdit, 0, None),
                          ("number", parent.TradeNumberEdit, parent.widthForTimestampEdit, None),
                          ("price", parent.TradePriceEdit, parent.widthForAmountEdit, parent.doubleValidate6),
                          ("qty", parent.TradeQtyEdit, parent.widthForAmountEdit, parent.doubleValidate6),
                          ("coupon", parent.TradeCouponEdit, parent.widthForAmountEdit, parent.doubleValidate6),
                          ("fee", parent.TradeFeeEdit, parent.widthForAmountEdit, parent.doubleValidate6)],
            self.DIVIDENDS: [("timestamp", parent.DividendTimestampEdit, parent.widthForTimestampEdit, None),
                             ("account_id", parent.DividendAccountWidget, 0, None),
                             ("asset_id", parent.DividendAssetWidget, 0, None),
                             ("number", parent.DividendNumberEdit, parent.widthForTimestampEdit, None),
                             ("sum", parent.DividendSumEdit, parent.widthForAmountEdit, parent.doubleValidate2),
                             ("note", parent.DividendSumDescription, 0, None),
                             ("sum_tax", parent.DividendTaxEdit, parent.widthForAmountEdit, parent.doubleValidate2),
                             ("note_tax", parent.DividendTaxDescription, 0, None)],
            self.TRANSFERS: [("from_acc_id", parent.TransferFromAccountWidget, 0, None),
                             ("to_acc_id", parent.TransferToAccountWidget, 0, None),
                             ("fee_acc_id", parent.TransferFeeAccountWidget, 0, None),
                             ("from_timestamp", parent.TransferFromTimestamp, parent.widthForTimestampEdit, None),
                             ("to_timestamp", parent.TransferToTimestamp, parent.widthForTimestampEdit, None),
                             ("fee_timestamp", parent.TransferFeeTimestamp, parent.widthForTimestampEdit, None),
                             ("from_amount", parent.TransferFromAmount, parent.widthForAmountEdit,
                              parent.doubleValidate2),
                             ("to_amount", parent.TransferToAmount, parent.widthForAmountEdit, parent.doubleValidate2),
                             (
                             "fee_amount", parent.TransferFeeAmount, parent.widthForAmountEdit, parent.doubleValidate2),
                             ("note", parent.TransferNote, 0, None)]
        }
        self.actions = [
            (parent.actionExit,             "triggered",        QtWidgets.QApplication.instance().quit),
            (parent.action_Load_quotes,     "triggered",        parent.UpdateQuotes),
            (parent.actionLoad_Statement,   "triggered",        parent.loadReportIBKR),
            (parent.actionBackup,           "triggered",        parent.Backup),
            (parent.actionRestore,          "triggered",        parent.Restore),
            (parent.action_Re_build_Ledger, "triggered",        parent.ShowRebuildDialog),
            (parent.actionAccountTypes,     "triggered",        parent.EditAccountTypes),
            (parent.actionAccounts,         "triggered",        parent.EditAccounts),
            (parent.actionAssets,           "triggered",        parent.EditAssets),
            (parent.actionPeers,            "triggered",        parent.EditPeers),
            (parent.actionCategories,       "triggered",        parent.EditCategories),
            (parent.actionTags,             "triggered",        parent.EditTags),
            (parent.MakeIncomeSpendingReport, "triggered",      parent.ReportIncomeSpending),
            (parent.MakeDealsReport,        "triggered",        parent.ReportDeals),
            (parent.MakePLReport,           "triggered",        parent.ReportProfitLoss),
            (parent.PrepareTaxForms,        "triggered",        parent.ExportTaxForms),
            (parent.MainTabs,               "currentChanged",   parent.OnMainTabChange),
            (parent.BalanceDate,            "dateChanged",      parent.onBalanceDateChange),
            (parent.HoldingsDate,           "dateChanged",      parent.onHoldingsDateChange),
            (parent.BalancesCurrencyCombo,  "currentIndexChanged", parent.OnBalanceCurrencyChange),
            (parent.HoldingsCurrencyCombo,  "currentIndexChanged", parent.OnHoldingsCurrencyChange),
            (parent.ShowInactiveCheckBox,   "stateChanged",     parent.OnBalanceInactiveChange),
            (parent.DateRangeCombo,         "currentIndexChanged", parent.OnOperationsRangeChange),
            (parent.OperationsTableView,    "customContextMenuRequested", parent.OnOperationsContextMenu),
            (parent.ChooseAccountBtn,       "clicked",          parent.OnAccountChange),
            (parent.SearchString,           "textChanged",      parent.OnSearchChange),
            (parent.AddActionDetail,        "clicked",          parent.AddDetail),
            (parent.RemoveActionDetail,     "clicked",          parent.RemoveDetail),
            (parent.DeleteOperationBtn,     "clicked",          parent.DeleteOperation),
            (parent.CopyOperationBtn,       "clicked",          parent.CopyOperation),
            (parent.SaveOperationBtn,       "clicked",          parent.SaveOperation),
            (parent.RevertOperationBtn,     "clicked",          parent.RevertOperation)
        ]

    def configure(self, i):
        model = UseSqlTable(self.parent.db, self.table_names[i], self.table_view_columns[i],
                            relations=self.table_relations[i])
        if self.views[i]:
            delegates = ConfigureTableView(self.views[i], model, self.table_view_columns[i])
            self.delegates_storage.append(delegates)
            self.views[i].show()
        if self.notify_changes[i]:
            model.dataChanged.connect(self.parent.on_data_changed)
        if self.widget_mappers[i]:
            self.mappers[i] = ConfigureDataMappers(model, self.widget_mappers[i], self.mapper_delegates[i])
        else:
            self.mappers[i] = None
        model.select()

    def configure_all(self):
        for table in self.table_names:
            self.configure(table)
        for action in self.actions:
            QObject.connect(action[self.ACTION_SRC], SIGNAL(action[self.ACTION_SIGNAL]+'()'), action[self.ACTION_SLOT])