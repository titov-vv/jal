from view_delegate import *
from constants import ColumnWidth
from reports.reports import ReportType
from PySide2 import QtWidgets
from PySide2.QtCore import QObject, SIGNAL, Slot
from functools import partial
from mapper_delegate import MapperDelegate
from CustomUI.helpers import UseSqlTable, ConfigureTableView, ConfigureDataMappers
from CustomUI.reference_data import ReferenceDataDialog, ReferenceTreeDelegate, ReferenceBoolDelegate, \
    ReferenceIntDelegate, ReferenceLookupDelegate, ReferenceTimestampDelegate


class TableViewConfig:
    BALANCES = 0
    HOLDINGS = 1
    OPERATIONS = 2
    ACTIONS = 3
    ACTION_DETAILS = 4
    TRADES = 5
    DIVIDENDS = 6
    TRANSFERS = 7
    ACCOUNT_TYPES = 8
    ACCOUNTS = 9
    ASSETS = 10
    PEERS = 11
    CATEGORIES = 12
    TAGS = 13

    ACTION_SRC = 0
    ACTION_SIGNAL = 1
    ACTION_SLOT = 2

    DLG_TABLE = 0
    DLG_TITLE = 1
    DLG_COLUMNS = 2
    DLG_SEARCH = 3
    DLG_TOGGLE = 4
    DLG_TREE = 5
    DLG_RELATIONS = 6

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
                   ("account_name", "Account", ColumnWidth.STRETCH, None, BalanceAccountDelegate),
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
                   ("asset_name", "Asset", ColumnWidth.STRETCH, None, None),
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
                     ("account_id", None, None, None, None),
                     ("account", "Account", 300, None, OperationsAccountDelegate),
                     ("num_peer", None, None, None, None),
                     ("asset_id", None, None, None, None),
                     ("asset", None, None, None, None),
                     ("asset_name", None, None, None, None),
                     ("note", "Notes", ColumnWidth.STRETCH, None, OperationsNotesDelegate),
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
                         ("category_id", "Category", 200, None, MapperDelegate),
                         ("tag_id", "Tag", 200, None, MapperDelegate),
                         ("sum", "Amount", 100, None, MapperDelegate),
                         ("alt_sum", "Amount *", 100, None, MapperDelegate),
                         ("note", "Note", ColumnWidth.STRETCH, None, None)],
        TRADES: [],
        DIVIDENDS: [],
        TRANSFERS: []
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
            self.ACTIONS: [("timestamp", parent.ActionTimestampEdit),
                           ("account_id", parent.ActionAccountWidget),
                           ("peer_id", parent.ActionPeerWidget)],
            self.ACTION_DETAILS: None,
            self.TRADES: [("timestamp", parent.TradeTimestampEdit),
                          ("corp_action_id", parent.TradeActionWidget),
                          ("account_id", parent.TradeAccountWidget),
                          ("asset_id", parent.TradeAssetWidget),
                          ("settlement", parent.TradeSettlementEdit),
                          ("number", parent.TradeNumberEdit),
                          ("price", parent.TradePriceEdit) ,
                          ("qty", parent.TradeQtyEdit) ,
                          ("coupon", parent.TradeCouponEdit) ,
                          ("fee", parent.TradeFeeEdit) ],
            self.DIVIDENDS: [("timestamp", parent.DividendTimestampEdit),
                             ("account_id", parent.DividendAccountWidget),
                             ("asset_id", parent.DividendAssetWidget),
                             ("number", parent.DividendNumberEdit),
                             ("sum", parent.DividendSumEdit),
                             ("note", parent.DividendSumDescription),
                             ("sum_tax", parent.DividendTaxEdit),
                             ("note_tax", parent.DividendTaxDescription)],
            self.TRANSFERS: [("from_acc_id", parent.TransferFromAccountWidget),
                             ("to_acc_id", parent.TransferToAccountWidget),
                             ("fee_acc_id", parent.TransferFeeAccountWidget),
                             ("from_timestamp", parent.TransferFromTimestamp),
                             ("to_timestamp", parent.TransferToTimestamp),
                             ("fee_timestamp", parent.TransferFeeTimestamp),
                             ("from_amount", parent.TransferFromAmount),
                             ("to_amount", parent.TransferToAmount),
                             (
                             "fee_amount", parent.TransferFeeAmount),
                             ("note", parent.TransferNote)]
        }
        self.dialogs = {
            self.ACCOUNT_TYPES: ('account_types',
                                 "Account Types",
                                 [("id", None, 0, None, None),
                                  ("name", "Account Type", ColumnWidth.STRETCH, Qt.AscendingOrder, None)],
                                 None,
                                 None,
                                 False,
                                 None
                                 ),
            self.ACCOUNTS: ('accounts',
                            "Assets",
                            [("id", None, 0, None, None),
                             ("name", "Name", ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                             ("type_id", None, 0, None, None),
                             ("currency_id", "Currency", None, None, ReferenceLookupDelegate),
                             ("active", "Act", 32, None, ReferenceBoolDelegate),
                             ("number", "Account #", None, None, None),
                             ("reconciled_on", "Reconciled @", ColumnWidth.FOR_DATETIME,
                              None, ReferenceTimestampDelegate),
                             ("organization_id", "Bank", None, None, ReferenceLookupDelegate)],
                            "name",
                            ("active", "Show inactive"),
                            False,
                            [("type_id", "account_types", "id", "name", "Account type:"),
                             ("currency_id", "currencies", "id", "name", None),
                             ("organization_id", "agents", "id", "name", None)]
                            ),
            self.ASSETS: ("assets",
                          "Assets",
                          [("id", None, 0, None, None),
                           ("name", "Symbol", None, Qt.AscendingOrder, None),
                           ("type_id", None, 0, None, None),
                           ("full_name", "Name", ColumnWidth.STRETCH, None, None),
                           ("isin", "ISIN", None, None, None),
                           ("web_id", "WebID", None, None, None),
                           ("src_id", "Data source", None, None, ReferenceLookupDelegate)],
                          "full_name",
                          None,
                          False,
                          [("type_id", "asset_types", "id", "name", "Asset type:"),
                           ("src_id", "data_sources", "id", "name", None)]
            ),
            self.PEERS: ("agents_ext",
                          "Peers",
                          [("id", " ", 16, None, ReferenceTreeDelegate),
                           ("pid", None, 0, None, None),
                           ("name", "Name", ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                           ("location", "Location", None, None, None),
                           ("actions_count", "Docs count", None, None, ReferenceIntDelegate),
                           ("children_count", None, None, None, None)],
                          "name",
                          None,
                          True,
                          None
            ),
            self.CATEGORIES: ("categories_ext",
                              "Categories",
                              [("id", " ", 16, None, ReferenceTreeDelegate),
                               ("pid", None, 0, None, None),
                               ("name", "Name", ColumnWidth.STRETCH, Qt.AscendingOrder, None),
                               ("often", "Often", None, None, ReferenceBoolDelegate),
                               ("special", None, 0, None, None),
                               ("children_count", None, None, None, None)],
                              "name",
                              None,
                              True,
                              None
            ),
            self.TAGS: ("tags",
                        "Tags",
                        [("id", None, 0, None, None),
                         ("tag", "Tag", ColumnWidth.STRETCH, Qt.AscendingOrder, None)],
                        "tag",
                        None,
                        False,
                        None
            )
        }
        self.actions = [
            (parent.actionExit,             "triggered()",              QtWidgets.QApplication.instance().quit),
            (parent.action_Load_quotes,     "triggered()",              partial(parent.downloader.showQuoteDownloadDialog, parent)),
            (parent.actionLoad_Statement,   "triggered()",              parent.statements.loadReport),
            (parent.actionBackup,           "triggered()",              parent.Backup),
            (parent.actionRestore,          "triggered()",              parent.Restore),
            (parent.action_Re_build_Ledger, "triggered()",              partial(parent.ledger.showRebuildDialog, parent)),
            (parent.actionAccountTypes,     "triggered()",              partial(self.show_dialog, self.ACCOUNT_TYPES)),
            (parent.actionAccounts,         "triggered()",              partial(self.show_dialog, self.ACCOUNTS)),
            (parent.actionAssets,           "triggered()",              partial(self.show_dialog, self.ASSETS)),
            (parent.actionPeers,            "triggered()",              partial(self.show_dialog, self.PEERS)),
            (parent.actionCategories,       "triggered()",              partial(self.show_dialog, self.CATEGORIES)),
            (parent.actionTags,             "triggered()",              partial(self.show_dialog, self.TAGS)),
            (parent.MakeCategoriesReport,   "triggered()",              partial(parent.reports.create_report, parent, ReportType.IncomeSpending)),
            (parent.MakeDealsReport,        "triggered()",              partial(parent.reports.create_report, parent, ReportType.Deals)),
            (parent.MakePLReport,           "triggered()",              partial(parent.reports.create_report, parent, ReportType.ProfitLoss)),
            (parent.PrepareTaxForms,        "triggered()",              partial(parent.taxes.showTaxesDialog, parent)),
            (parent.BalanceDate,            "dateChanged(QDate)",       parent.onBalanceDateChange),
            (parent.HoldingsDate,           "dateChanged(QDate)",       parent.onHoldingsDateChange),
            (parent.BalancesCurrencyCombo,  "currentIndexChanged(int)", parent.OnBalanceCurrencyChange),
            (parent.HoldingsCurrencyCombo,  "currentIndexChanged(int)", parent.OnHoldingsCurrencyChange),
            (parent.ReportRangeCombo,       "currentIndexChanged(int)", parent.onReportRangeChange),
            (parent.RunReportBtn,           "clicked()",                parent.onRunReport),
            (parent.SaveReportBtn,          "clicked()",                parent.reports.saveReport),
            (parent.ShowInactiveCheckBox,   "stateChanged(int)",        parent.OnBalanceInactiveChange),
            (parent.DateRangeCombo,         "currentIndexChanged(int)", parent.OnOperationsRangeChange),
            (parent.ChooseAccountBtn,       "changed(int)",             parent.operations.setAccountId),
            (parent.SearchString,           "textChanged(QString)",     parent.OnSearchTextChange),
            (parent.AddActionDetail,        "clicked()",                partial(parent.operations.addOperationChild, TransactionType.Action)),
            (parent.RemoveActionDetail,     "clicked()",                partial(parent.operations.deleteOperationChild, TransactionType.Action)),
            (parent.DeleteOperationBtn,     "clicked()",                parent.operations.deleteOperation),
            (parent.CopyOperationBtn,       "clicked()",                parent.operations.copyOperation),
            (parent.SaveOperationBtn,       "clicked()",                parent.operations.commitOperation),
            (parent.RevertOperationBtn,     "clicked()",                parent.operations.revertOperation)
        ]

    def configure(self, i):
        model = UseSqlTable(self.parent.db, self.table_names[i], self.table_view_columns[i],
                            relations=self.table_relations[i])
        if self.views[i]:
            delegates = ConfigureTableView(self.views[i], model, self.table_view_columns[i])
            self.delegates_storage.append(delegates)
            self.views[i].show()
        if self.widget_mappers[i]:
            self.mappers[i] = ConfigureDataMappers(model, self.widget_mappers[i], MapperDelegate)
        else:
            self.mappers[i] = None
        model.select()

    def configure_all(self):
        for table in self.table_names:
            self.configure(table)
        for action in self.actions:
            QObject.connect(action[self.ACTION_SRC], SIGNAL(action[self.ACTION_SIGNAL]), action[self.ACTION_SLOT])

    @Slot()
    def show_dialog(self, dlg_id):
        ReferenceDataDialog(self.parent.db,
                            self.dialogs[dlg_id][self.DLG_TABLE],
                            self.dialogs[dlg_id][self.DLG_COLUMNS],
                            title=self.dialogs[dlg_id][self.DLG_TABLE],
                            search_field=self.dialogs[dlg_id][self.DLG_SEARCH],
                            toggle=self.dialogs[dlg_id][self.DLG_TOGGLE],
                            tree_view=self.dialogs[dlg_id][self.DLG_TREE],
                            relations=self.dialogs[dlg_id][self.DLG_RELATIONS]
                            ).exec_()