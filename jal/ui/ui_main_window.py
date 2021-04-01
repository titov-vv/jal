# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from jal.widgets.account_select import AccountButton
from jal.widgets.log_viewer import LogViewer
from jal.widgets.account_select import CurrencyComboBox
from jal.widgets.reference_selector import CategorySelector
from jal.widgets.dividend_widget import DividendWidget
from jal.widgets.trade_widget import TradeWidget
from jal.widgets.transfer_widget import TransferWidget
from jal.widgets.corporate_action_widget import CorporateActionWidget
from jal.widgets.income_spending_widget import IncomeSpendingWidget


class Ui_JAL_MainWindow(object):
    def setupUi(self, JAL_MainWindow):
        if not JAL_MainWindow.objectName():
            JAL_MainWindow.setObjectName(u"JAL_MainWindow")
        JAL_MainWindow.resize(1700, 900)
        JAL_MainWindow.setMinimumSize(QSize(0, 0))
        self.actionExit = QAction(JAL_MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionExit.setMenuRole(QAction.QuitRole)
        self.action_Re_build_Ledger = QAction(JAL_MainWindow)
        self.action_Re_build_Ledger.setObjectName(u"action_Re_build_Ledger")
        self.action_Load_quotes = QAction(JAL_MainWindow)
        self.action_Load_quotes.setObjectName(u"action_Load_quotes")
        self.actionImportStatement = QAction(JAL_MainWindow)
        self.actionImportStatement.setObjectName(u"actionImportStatement")
        self.actionAccountTypes = QAction(JAL_MainWindow)
        self.actionAccountTypes.setObjectName(u"actionAccountTypes")
        self.actionAccounts = QAction(JAL_MainWindow)
        self.actionAccounts.setObjectName(u"actionAccounts")
        self.actionAssets = QAction(JAL_MainWindow)
        self.actionAssets.setObjectName(u"actionAssets")
        self.actionPeers = QAction(JAL_MainWindow)
        self.actionPeers.setObjectName(u"actionPeers")
        self.actionCategories = QAction(JAL_MainWindow)
        self.actionCategories.setObjectName(u"actionCategories")
        self.actionBackup = QAction(JAL_MainWindow)
        self.actionBackup.setObjectName(u"actionBackup")
        self.actionRestore = QAction(JAL_MainWindow)
        self.actionRestore.setObjectName(u"actionRestore")
        self.PrepareTaxForms = QAction(JAL_MainWindow)
        self.PrepareTaxForms.setObjectName(u"PrepareTaxForms")
        self.MakeDealsReport = QAction(JAL_MainWindow)
        self.MakeDealsReport.setObjectName(u"MakeDealsReport")
        self.actionTags = QAction(JAL_MainWindow)
        self.actionTags.setObjectName(u"actionTags")
        self.MakePLReport = QAction(JAL_MainWindow)
        self.MakePLReport.setObjectName(u"MakePLReport")
        self.MakeCategoriesReport = QAction(JAL_MainWindow)
        self.MakeCategoriesReport.setObjectName(u"MakeCategoriesReport")
        self.actionImportSlipRU = QAction(JAL_MainWindow)
        self.actionImportSlipRU.setObjectName(u"actionImportSlipRU")
        self.actionCountries = QAction(JAL_MainWindow)
        self.actionCountries.setObjectName(u"actionCountries")
        self.actionQuotes = QAction(JAL_MainWindow)
        self.actionQuotes.setObjectName(u"actionQuotes")
        self.centralwidget = QWidget(JAL_MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setMaximumSize(QSize(16777215, 16777215))
        self.verticalLayout_6 = QVBoxLayout(self.centralwidget)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.MainTabs = QTabWidget(self.centralwidget)
        self.MainTabs.setObjectName(u"MainTabs")
        self.MainTabs.setTabPosition(QTabWidget.West)
        self.MainTabs.setTabShape(QTabWidget.Triangular)
        self.BalanceTransactionTab = QWidget()
        self.BalanceTransactionTab.setObjectName(u"BalanceTransactionTab")
        self.horizontalLayout = QHBoxLayout(self.BalanceTransactionTab)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.BalanceOperationsSplitter = QSplitter(self.BalanceTransactionTab)
        self.BalanceOperationsSplitter.setObjectName(u"BalanceOperationsSplitter")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.BalanceOperationsSplitter.sizePolicy().hasHeightForWidth())
        self.BalanceOperationsSplitter.setSizePolicy(sizePolicy)
        self.BalanceOperationsSplitter.setOrientation(Qt.Horizontal)
        self.BalanceBox = QGroupBox(self.BalanceOperationsSplitter)
        self.BalanceBox.setObjectName(u"BalanceBox")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(1)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.BalanceBox.sizePolicy().hasHeightForWidth())
        self.BalanceBox.setSizePolicy(sizePolicy1)
        self.BalanceBox.setMaximumSize(QSize(16777215, 16777215))
        self.verticalLayout = QVBoxLayout(self.BalanceBox)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.BalanceConfigFrame = QFrame(self.BalanceBox)
        self.BalanceConfigFrame.setObjectName(u"BalanceConfigFrame")
        self.BalanceConfigFrame.setMinimumSize(QSize(408, 0))
        self.BalanceConfigFrame.setMaximumSize(QSize(16777215, 44))
        self.BalanceConfigFrame.setFrameShape(QFrame.Panel)
        self.BalanceConfigFrame.setFrameShadow(QFrame.Plain)
        self.BalanceConfigFrame.setLineWidth(0)
        self.horizontalLayout_2 = QHBoxLayout(self.BalanceConfigFrame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(2, 2, 2, 2)
        self.BalanceDate = QDateEdit(self.BalanceConfigFrame)
        self.BalanceDate.setObjectName(u"BalanceDate")
        self.BalanceDate.setDateTime(QDateTime(QDate(2020, 12, 5), QTime(21, 0, 0)))
        self.BalanceDate.setCalendarPopup(True)
        self.BalanceDate.setTimeSpec(Qt.UTC)

        self.horizontalLayout_2.addWidget(self.BalanceDate)

        self.CurrencyLbl = QLabel(self.BalanceConfigFrame)
        self.CurrencyLbl.setObjectName(u"CurrencyLbl")
        self.CurrencyLbl.setLayoutDirection(Qt.LeftToRight)
        self.CurrencyLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_2.addWidget(self.CurrencyLbl)

        self.BalancesCurrencyCombo = CurrencyComboBox(self.BalanceConfigFrame)
        self.BalancesCurrencyCombo.setObjectName(u"BalancesCurrencyCombo")

        self.horizontalLayout_2.addWidget(self.BalancesCurrencyCombo)

        self.ShowInactiveCheckBox = QCheckBox(self.BalanceConfigFrame)
        self.ShowInactiveCheckBox.setObjectName(u"ShowInactiveCheckBox")

        self.horizontalLayout_2.addWidget(self.ShowInactiveCheckBox)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)


        self.verticalLayout.addWidget(self.BalanceConfigFrame)

        self.BalancesTableView = QTableView(self.BalanceBox)
        self.BalancesTableView.setObjectName(u"BalancesTableView")
        self.BalancesTableView.setFrameShape(QFrame.Panel)
        self.BalancesTableView.setEditTriggers(QAbstractItemView.EditKeyPressed|QAbstractItemView.SelectedClicked)
        self.BalancesTableView.setAlternatingRowColors(True)
        self.BalancesTableView.setSelectionMode(QAbstractItemView.NoSelection)
        self.BalancesTableView.setGridStyle(Qt.DotLine)
        self.BalancesTableView.setWordWrap(False)
        self.BalancesTableView.verticalHeader().setVisible(False)
        self.BalancesTableView.verticalHeader().setMinimumSectionSize(20)
        self.BalancesTableView.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.BalancesTableView)

        self.BalanceOperationsSplitter.addWidget(self.BalanceBox)
        self.OperationsBox = QGroupBox(self.BalanceOperationsSplitter)
        self.OperationsBox.setObjectName(u"OperationsBox")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy2.setHorizontalStretch(4)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.OperationsBox.sizePolicy().hasHeightForWidth())
        self.OperationsBox.setSizePolicy(sizePolicy2)
        self.OperationsBox.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.verticalLayout_2 = QVBoxLayout(self.OperationsBox)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.OperationConfigFrame = QFrame(self.OperationsBox)
        self.OperationConfigFrame.setObjectName(u"OperationConfigFrame")
        self.OperationConfigFrame.setEnabled(True)
        self.OperationConfigFrame.setMinimumSize(QSize(0, 0))
        self.OperationConfigFrame.setFrameShape(QFrame.Panel)
        self.OperationConfigFrame.setFrameShadow(QFrame.Plain)
        self.OperationConfigFrame.setLineWidth(0)
        self.horizontalLayout_3 = QHBoxLayout(self.OperationConfigFrame)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(2, 2, 2, 2)
        self.DateRangeLbl = QLabel(self.OperationConfigFrame)
        self.DateRangeLbl.setObjectName(u"DateRangeLbl")

        self.horizontalLayout_3.addWidget(self.DateRangeLbl)

        self.DateRangeCombo = QComboBox(self.OperationConfigFrame)
        self.DateRangeCombo.addItem("")
        self.DateRangeCombo.addItem("")
        self.DateRangeCombo.addItem("")
        self.DateRangeCombo.addItem("")
        self.DateRangeCombo.addItem("")
        self.DateRangeCombo.setObjectName(u"DateRangeCombo")

        self.horizontalLayout_3.addWidget(self.DateRangeCombo)

        self.AccountLbl = QLabel(self.OperationConfigFrame)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.horizontalLayout_3.addWidget(self.AccountLbl)

        self.ChooseAccountBtn = AccountButton(self.OperationConfigFrame)
        self.ChooseAccountBtn.setObjectName(u"ChooseAccountBtn")

        self.horizontalLayout_3.addWidget(self.ChooseAccountBtn)

        self.SearchLbl = QLabel(self.OperationConfigFrame)
        self.SearchLbl.setObjectName(u"SearchLbl")

        self.horizontalLayout_3.addWidget(self.SearchLbl)

        self.SearchString = QLineEdit(self.OperationConfigFrame)
        self.SearchString.setObjectName(u"SearchString")

        self.horizontalLayout_3.addWidget(self.SearchString)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)


        self.verticalLayout_2.addWidget(self.OperationConfigFrame)

        self.OperationsDetailsSplitter = QSplitter(self.OperationsBox)
        self.OperationsDetailsSplitter.setObjectName(u"OperationsDetailsSplitter")
        self.OperationsDetailsSplitter.setOrientation(Qt.Vertical)
        self.OperationsTableView = QTableView(self.OperationsDetailsSplitter)
        self.OperationsTableView.setObjectName(u"OperationsTableView")
        sizePolicy3 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(4)
        sizePolicy3.setHeightForWidth(self.OperationsTableView.sizePolicy().hasHeightForWidth())
        self.OperationsTableView.setSizePolicy(sizePolicy3)
        self.OperationsTableView.setAlternatingRowColors(True)
        self.OperationsTableView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.OperationsTableView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.OperationsTableView.setWordWrap(False)
        self.OperationsDetailsSplitter.addWidget(self.OperationsTableView)
        self.OperationsTableView.verticalHeader().setVisible(False)
        self.OperationsTableView.verticalHeader().setMinimumSectionSize(20)
        self.OperationsTableView.verticalHeader().setDefaultSectionSize(20)
        self.OperationDetails = QFrame(self.OperationsDetailsSplitter)
        self.OperationDetails.setObjectName(u"OperationDetails")
        sizePolicy4 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(1)
        sizePolicy4.setHeightForWidth(self.OperationDetails.sizePolicy().hasHeightForWidth())
        self.OperationDetails.setSizePolicy(sizePolicy4)
        self.OperationDetails.setMinimumSize(QSize(0, 100))
        self.OperationDetails.setMaximumSize(QSize(16777215, 300))
        self.OperationDetails.setFrameShape(QFrame.Panel)
        self.OperationDetails.setFrameShadow(QFrame.Plain)
        self.OperationDetails.setLineWidth(0)
        self.horizontalLayout_4 = QHBoxLayout(self.OperationDetails)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.OperationsTabs = QStackedWidget(self.OperationDetails)
        self.OperationsTabs.setObjectName(u"OperationsTabs")
        self.NoOperation = QWidget()
        self.NoOperation.setObjectName(u"NoOperation")
        self.OperationsTabs.addWidget(self.NoOperation)
        self.IncomeSpending = IncomeSpendingWidget()
        self.IncomeSpending.setObjectName(u"IncomeSpending")
        self.OperationsTabs.addWidget(self.IncomeSpending)
        self.Dividend = DividendWidget()
        self.Dividend.setObjectName(u"Dividend")
        self.OperationsTabs.addWidget(self.Dividend)
        self.Trade = TradeWidget()
        self.Trade.setObjectName(u"Trade")
        self.OperationsTabs.addWidget(self.Trade)
        self.Transfer = TransferWidget()
        self.Transfer.setObjectName(u"Transfer")
        self.OperationsTabs.addWidget(self.Transfer)
        self.CorporateAction = CorporateActionWidget()
        self.CorporateAction.setObjectName(u"CorporateAction")
        self.OperationsTabs.addWidget(self.CorporateAction)

        self.horizontalLayout_4.addWidget(self.OperationsTabs)

        self.OperationsButtons = QFrame(self.OperationDetails)
        self.OperationsButtons.setObjectName(u"OperationsButtons")
        self.OperationsButtons.setMinimumSize(QSize(100, 0))
        self.OperationsButtons.setFrameShape(QFrame.Panel)
        self.OperationsButtons.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_3 = QVBoxLayout(self.OperationsButtons)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.NewOperationBtn = QPushButton(self.OperationsButtons)
        self.NewOperationBtn.setObjectName(u"NewOperationBtn")

        self.verticalLayout_3.addWidget(self.NewOperationBtn)

        self.CopyOperationBtn = QPushButton(self.OperationsButtons)
        self.CopyOperationBtn.setObjectName(u"CopyOperationBtn")

        self.verticalLayout_3.addWidget(self.CopyOperationBtn)

        self.DeleteOperationBtn = QPushButton(self.OperationsButtons)
        self.DeleteOperationBtn.setObjectName(u"DeleteOperationBtn")

        self.verticalLayout_3.addWidget(self.DeleteOperationBtn)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer_4)


        self.horizontalLayout_4.addWidget(self.OperationsButtons)

        self.OperationsDetailsSplitter.addWidget(self.OperationDetails)

        self.verticalLayout_2.addWidget(self.OperationsDetailsSplitter)

        self.BalanceOperationsSplitter.addWidget(self.OperationsBox)

        self.horizontalLayout.addWidget(self.BalanceOperationsSplitter)

        self.MainTabs.addTab(self.BalanceTransactionTab, "")
        self.HoldingsTab = QWidget()
        self.HoldingsTab.setObjectName(u"HoldingsTab")
        self.verticalLayout_4 = QVBoxLayout(self.HoldingsTab)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.HoldingsParamsFrame = QFrame(self.HoldingsTab)
        self.HoldingsParamsFrame.setObjectName(u"HoldingsParamsFrame")
        self.HoldingsParamsFrame.setFrameShape(QFrame.Panel)
        self.HoldingsParamsFrame.setFrameShadow(QFrame.Sunken)
        self.horizontalLayout_7 = QHBoxLayout(self.HoldingsParamsFrame)
        self.horizontalLayout_7.setSpacing(6)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(2, 2, 2, 2)
        self.HoldingsDate = QDateEdit(self.HoldingsParamsFrame)
        self.HoldingsDate.setObjectName(u"HoldingsDate")
        self.HoldingsDate.setDateTime(QDateTime(QDate(2020, 12, 5), QTime(21, 0, 0)))
        self.HoldingsDate.setCalendarPopup(True)
        self.HoldingsDate.setTimeSpec(Qt.UTC)

        self.horizontalLayout_7.addWidget(self.HoldingsDate)

        self.HoldingsCurrencyLbl = QLabel(self.HoldingsParamsFrame)
        self.HoldingsCurrencyLbl.setObjectName(u"HoldingsCurrencyLbl")

        self.horizontalLayout_7.addWidget(self.HoldingsCurrencyLbl)

        self.HoldingsCurrencyCombo = CurrencyComboBox(self.HoldingsParamsFrame)
        self.HoldingsCurrencyCombo.setObjectName(u"HoldingsCurrencyCombo")

        self.horizontalLayout_7.addWidget(self.HoldingsCurrencyCombo)

        self.horizontalSpacer_3 = QSpacerItem(1411, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_7.addItem(self.horizontalSpacer_3)


        self.verticalLayout_4.addWidget(self.HoldingsParamsFrame)

        self.HoldingsTableView = QTreeView(self.HoldingsTab)
        self.HoldingsTableView.setObjectName(u"HoldingsTableView")
        self.HoldingsTableView.setFrameShape(QFrame.Panel)
        self.HoldingsTableView.setAlternatingRowColors(True)
        self.HoldingsTableView.setAnimated(True)
        self.HoldingsTableView.setAllColumnsShowFocus(True)

        self.verticalLayout_4.addWidget(self.HoldingsTableView)

        self.MainTabs.addTab(self.HoldingsTab, "")
        self.ReportsTab = QWidget()
        self.ReportsTab.setObjectName(u"ReportsTab")
        self.verticalLayout_7 = QVBoxLayout(self.ReportsTab)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(self.ReportsTab)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 10, 1, 1)

        self.ReportAccountBtn = AccountButton(self.ReportParamsFrame)
        self.ReportAccountBtn.setObjectName(u"ReportAccountBtn")

        self.gridLayout.addWidget(self.ReportAccountBtn, 1, 2, 1, 1)

        self.ReportCategoryEdit = CategorySelector(self.ReportParamsFrame)
        self.ReportCategoryEdit.setObjectName(u"ReportCategoryEdit")

        self.gridLayout.addWidget(self.ReportCategoryEdit, 0, 9, 1, 1)

        self.ReportTypeLbl = QLabel(self.ReportParamsFrame)
        self.ReportTypeLbl.setObjectName(u"ReportTypeLbl")

        self.gridLayout.addWidget(self.ReportTypeLbl, 0, 0, 1, 1)

        self.ReportToDate = QDateEdit(self.ReportParamsFrame)
        self.ReportToDate.setObjectName(u"ReportToDate")
        self.ReportToDate.setDateTime(QDateTime(QDate(2020, 12, 5), QTime(21, 0, 0)))
        self.ReportToDate.setCalendarPopup(True)
        self.ReportToDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.ReportToDate, 1, 5, 1, 1)

        self.ReportAccountLbl = QLabel(self.ReportParamsFrame)
        self.ReportAccountLbl.setObjectName(u"ReportAccountLbl")

        self.gridLayout.addWidget(self.ReportAccountLbl, 1, 0, 1, 1)

        self.line_2 = QFrame(self.ReportParamsFrame)
        self.line_2.setObjectName(u"line_2")
        sizePolicy5 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.line_2.sizePolicy().hasHeightForWidth())
        self.line_2.setSizePolicy(sizePolicy5)
        self.line_2.setFrameShadow(QFrame.Sunken)
        self.line_2.setFrameShape(QFrame.VLine)

        self.gridLayout.addWidget(self.line_2, 0, 3, 2, 1)

        self.ReportToLbl = QLabel(self.ReportParamsFrame)
        self.ReportToLbl.setObjectName(u"ReportToLbl")
        self.ReportToLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout.addWidget(self.ReportToLbl, 1, 4, 1, 1)

        self.ReportFromLbl = QLabel(self.ReportParamsFrame)
        self.ReportFromLbl.setObjectName(u"ReportFromLbl")
        self.ReportFromLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout.addWidget(self.ReportFromLbl, 0, 4, 1, 1)

        self.ReportGroupCheck = QCheckBox(self.ReportParamsFrame)
        self.ReportGroupCheck.setObjectName(u"ReportGroupCheck")

        self.gridLayout.addWidget(self.ReportGroupCheck, 1, 6, 1, 1)

        self.ReportTypeCombo = QComboBox(self.ReportParamsFrame)
        self.ReportTypeCombo.addItem("")
        self.ReportTypeCombo.addItem("")
        self.ReportTypeCombo.addItem("")
        self.ReportTypeCombo.addItem("")
        self.ReportTypeCombo.setObjectName(u"ReportTypeCombo")

        self.gridLayout.addWidget(self.ReportTypeCombo, 0, 2, 1, 1)

        self.SaveReportBtn = QPushButton(self.ReportParamsFrame)
        self.SaveReportBtn.setObjectName(u"SaveReportBtn")

        self.gridLayout.addWidget(self.SaveReportBtn, 1, 11, 1, 1)

        self.RunReportBtn = QPushButton(self.ReportParamsFrame)
        self.RunReportBtn.setObjectName(u"RunReportBtn")

        self.gridLayout.addWidget(self.RunReportBtn, 0, 11, 1, 1)

        self.ReportCategoryLbl = QLabel(self.ReportParamsFrame)
        self.ReportCategoryLbl.setObjectName(u"ReportCategoryLbl")

        self.gridLayout.addWidget(self.ReportCategoryLbl, 0, 8, 1, 1)

        self.ReportRangeCombo = QComboBox(self.ReportParamsFrame)
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.setObjectName(u"ReportRangeCombo")

        self.gridLayout.addWidget(self.ReportRangeCombo, 0, 6, 1, 1)

        self.ReportFromDate = QDateEdit(self.ReportParamsFrame)
        self.ReportFromDate.setObjectName(u"ReportFromDate")
        self.ReportFromDate.setDateTime(QDateTime(QDate(2020, 12, 5), QTime(21, 0, 0)))
        self.ReportFromDate.setCalendarPopup(True)
        self.ReportFromDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.ReportFromDate, 0, 5, 1, 1)

        self.line_3 = QFrame(self.ReportParamsFrame)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.VLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.gridLayout.addWidget(self.line_3, 0, 7, 2, 1)


        self.verticalLayout_7.addWidget(self.ReportParamsFrame)

        self.ReportTableView = QTableView(self.ReportsTab)
        self.ReportTableView.setObjectName(u"ReportTableView")
        self.ReportTableView.setFrameShape(QFrame.Panel)
        self.ReportTableView.setFrameShadow(QFrame.Sunken)
        self.ReportTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ReportTableView.setAlternatingRowColors(True)
        self.ReportTableView.setGridStyle(Qt.DotLine)
        self.ReportTableView.setWordWrap(False)
        self.ReportTableView.verticalHeader().setVisible(False)
        self.ReportTableView.verticalHeader().setMinimumSectionSize(20)
        self.ReportTableView.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout_7.addWidget(self.ReportTableView)

        self.ReportTreeView = QTreeView(self.ReportsTab)
        self.ReportTreeView.setObjectName(u"ReportTreeView")
        self.ReportTreeView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ReportTreeView.setAlternatingRowColors(True)
        self.ReportTreeView.header().setStretchLastSection(False)

        self.verticalLayout_7.addWidget(self.ReportTreeView)

        self.MainTabs.addTab(self.ReportsTab, "")
        self.LoggingTab = QWidget()
        self.LoggingTab.setObjectName(u"LoggingTab")
        self.verticalLayout_5 = QVBoxLayout(self.LoggingTab)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.Logs = LogViewer(self.LoggingTab)
        self.Logs.setObjectName(u"Logs")

        self.verticalLayout_5.addWidget(self.Logs)

        self.MainTabs.addTab(self.LoggingTab, "")

        self.verticalLayout_6.addWidget(self.MainTabs)

        JAL_MainWindow.setCentralWidget(self.centralwidget)
        self.MainMenu = QMenuBar(JAL_MainWindow)
        self.MainMenu.setObjectName(u"MainMenu")
        self.MainMenu.setGeometry(QRect(0, 0, 1700, 22))
        self.menuFile = QMenu(self.MainMenu)
        self.menuFile.setObjectName(u"menuFile")
        self.menu_DAta = QMenu(self.MainMenu)
        self.menu_DAta.setObjectName(u"menu_DAta")
        self.menuPredefined_data = QMenu(self.menu_DAta)
        self.menuPredefined_data.setObjectName(u"menuPredefined_data")
        self.menuLoad = QMenu(self.MainMenu)
        self.menuLoad.setObjectName(u"menuLoad")
        self.menu_Reports = QMenu(self.MainMenu)
        self.menu_Reports.setObjectName(u"menu_Reports")
        self.menuLanguage = QMenu(self.MainMenu)
        self.menuLanguage.setObjectName(u"menuLanguage")
        self.menuImport = QMenu(self.MainMenu)
        self.menuImport.setObjectName(u"menuImport")
        self.menuStatement = QMenu(self.menuImport)
        self.menuStatement.setObjectName(u"menuStatement")
        JAL_MainWindow.setMenuBar(self.MainMenu)
        self.StatusBar = QStatusBar(JAL_MainWindow)
        self.StatusBar.setObjectName(u"StatusBar")
        JAL_MainWindow.setStatusBar(self.StatusBar)

        self.MainMenu.addAction(self.menuFile.menuAction())
        self.MainMenu.addAction(self.menu_DAta.menuAction())
        self.MainMenu.addAction(self.menuLoad.menuAction())
        self.MainMenu.addAction(self.menuImport.menuAction())
        self.MainMenu.addAction(self.menu_Reports.menuAction())
        self.MainMenu.addAction(self.menuLanguage.menuAction())
        self.menuFile.addAction(self.actionExit)
        self.menu_DAta.addSeparator()
        self.menu_DAta.addAction(self.actionAccounts)
        self.menu_DAta.addAction(self.actionAssets)
        self.menu_DAta.addAction(self.actionPeers)
        self.menu_DAta.addAction(self.actionCategories)
        self.menu_DAta.addAction(self.actionTags)
        self.menu_DAta.addAction(self.actionCountries)
        self.menu_DAta.addAction(self.actionQuotes)
        self.menu_DAta.addAction(self.menuPredefined_data.menuAction())
        self.menu_DAta.addSeparator()
        self.menu_DAta.addAction(self.actionBackup)
        self.menu_DAta.addAction(self.actionRestore)
        self.menu_DAta.addAction(self.action_Re_build_Ledger)
        self.menuPredefined_data.addAction(self.actionAccountTypes)
        self.menuLoad.addAction(self.action_Load_quotes)
        self.menu_Reports.addAction(self.PrepareTaxForms)
        self.menuImport.addAction(self.actionImportSlipRU)
        self.menuImport.addAction(self.menuStatement.menuAction())

        self.retranslateUi(JAL_MainWindow)

        self.MainTabs.setCurrentIndex(0)
        self.OperationsTabs.setCurrentIndex(5)


        QMetaObject.connectSlotsByName(JAL_MainWindow)
    # setupUi

    def retranslateUi(self, JAL_MainWindow):
        JAL_MainWindow.setWindowTitle(QCoreApplication.translate("JAL_MainWindow", u"jal", None))
        self.actionExit.setText(QCoreApplication.translate("JAL_MainWindow", u"&Exit", None))
        self.action_Re_build_Ledger.setText(QCoreApplication.translate("JAL_MainWindow", u"Re-build &Ledger...", None))
        self.action_Load_quotes.setText(QCoreApplication.translate("JAL_MainWindow", u"Load &Quotes...", None))
        self.actionImportStatement.setText(QCoreApplication.translate("JAL_MainWindow", u"&Broker statement...", None))
        self.actionAccountTypes.setText(QCoreApplication.translate("JAL_MainWindow", u"Account &Types", None))
        self.actionAccounts.setText(QCoreApplication.translate("JAL_MainWindow", u"&Accounts", None))
        self.actionAssets.setText(QCoreApplication.translate("JAL_MainWindow", u"A&ssets", None))
        self.actionPeers.setText(QCoreApplication.translate("JAL_MainWindow", u"&Peers", None))
        self.actionCategories.setText(QCoreApplication.translate("JAL_MainWindow", u"&Categories", None))
        self.actionBackup.setText(QCoreApplication.translate("JAL_MainWindow", u"&Backup...", None))
        self.actionRestore.setText(QCoreApplication.translate("JAL_MainWindow", u"&Restore...", None))
        self.PrepareTaxForms.setText(QCoreApplication.translate("JAL_MainWindow", u"&Tax report [RU]", None))
        self.MakeDealsReport.setText(QCoreApplication.translate("JAL_MainWindow", u"&Deals report", None))
        self.actionTags.setText(QCoreApplication.translate("JAL_MainWindow", u"&Tags", None))
        self.MakePLReport.setText(QCoreApplication.translate("JAL_MainWindow", u"&Profit/Loss report", None))
        self.MakeCategoriesReport.setText(QCoreApplication.translate("JAL_MainWindow", u"&Income/Spending report", None))
        self.actionImportSlipRU.setText(QCoreApplication.translate("JAL_MainWindow", u"Slip [RU]...", None))
        self.actionCountries.setText(QCoreApplication.translate("JAL_MainWindow", u"C&ountries", None))
        self.actionQuotes.setText(QCoreApplication.translate("JAL_MainWindow", u"&Quotes", None))
        self.BalanceBox.setTitle(QCoreApplication.translate("JAL_MainWindow", u"Balances", None))
        self.BalanceDate.setDisplayFormat(QCoreApplication.translate("JAL_MainWindow", u"dd/MM/yyyy", None))
        self.CurrencyLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"Sum Currency:", None))
        self.ShowInactiveCheckBox.setText(QCoreApplication.translate("JAL_MainWindow", u"Show &Inactive", None))
        self.OperationsBox.setTitle(QCoreApplication.translate("JAL_MainWindow", u"Operations", None))
        self.DateRangeLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"Time range:", None))
        self.DateRangeCombo.setItemText(0, QCoreApplication.translate("JAL_MainWindow", u"Week", None))
        self.DateRangeCombo.setItemText(1, QCoreApplication.translate("JAL_MainWindow", u"Month", None))
        self.DateRangeCombo.setItemText(2, QCoreApplication.translate("JAL_MainWindow", u"Quarter", None))
        self.DateRangeCombo.setItemText(3, QCoreApplication.translate("JAL_MainWindow", u"Year", None))
        self.DateRangeCombo.setItemText(4, QCoreApplication.translate("JAL_MainWindow", u"All", None))

        self.AccountLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"Account:", None))
        self.SearchLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"Search:", None))
        self.NewOperationBtn.setText(QCoreApplication.translate("JAL_MainWindow", u"New", None))
        self.CopyOperationBtn.setText(QCoreApplication.translate("JAL_MainWindow", u"Copy", None))
        self.DeleteOperationBtn.setText(QCoreApplication.translate("JAL_MainWindow", u"Del", None))
        self.MainTabs.setTabText(self.MainTabs.indexOf(self.BalanceTransactionTab), QCoreApplication.translate("JAL_MainWindow", u"Balance && Operations", None))
        self.HoldingsDate.setDisplayFormat(QCoreApplication.translate("JAL_MainWindow", u"dd/MM/yyyy", None))
        self.HoldingsCurrencyLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"Common currency:", None))
        self.MainTabs.setTabText(self.MainTabs.indexOf(self.HoldingsTab), QCoreApplication.translate("JAL_MainWindow", u"Holdings", None))
        self.ReportTypeLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"Report:", None))
        self.ReportToDate.setDisplayFormat(QCoreApplication.translate("JAL_MainWindow", u"dd/MM/yyyy", None))
        self.ReportAccountLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"Account:", None))
        self.ReportToLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"To:", None))
        self.ReportFromLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"From:", None))
        self.ReportGroupCheck.setText(QCoreApplication.translate("JAL_MainWindow", u"Group dates", None))
        self.ReportTypeCombo.setItemText(0, QCoreApplication.translate("JAL_MainWindow", u"Income / Spending", None))
        self.ReportTypeCombo.setItemText(1, QCoreApplication.translate("JAL_MainWindow", u"Profit / Loss", None))
        self.ReportTypeCombo.setItemText(2, QCoreApplication.translate("JAL_MainWindow", u"Deals", None))
        self.ReportTypeCombo.setItemText(3, QCoreApplication.translate("JAL_MainWindow", u"By Category", None))

        self.SaveReportBtn.setText(QCoreApplication.translate("JAL_MainWindow", u"Save", None))
        self.RunReportBtn.setText(QCoreApplication.translate("JAL_MainWindow", u"Run", None))
        self.ReportCategoryLbl.setText(QCoreApplication.translate("JAL_MainWindow", u"Category:", None))
        self.ReportRangeCombo.setItemText(0, QCoreApplication.translate("JAL_MainWindow", u"Custom range", None))
        self.ReportRangeCombo.setItemText(1, QCoreApplication.translate("JAL_MainWindow", u"Quarter to date", None))
        self.ReportRangeCombo.setItemText(2, QCoreApplication.translate("JAL_MainWindow", u"Year to date", None))
        self.ReportRangeCombo.setItemText(3, QCoreApplication.translate("JAL_MainWindow", u"This year", None))
        self.ReportRangeCombo.setItemText(4, QCoreApplication.translate("JAL_MainWindow", u"Previous year", None))

        self.ReportFromDate.setDisplayFormat(QCoreApplication.translate("JAL_MainWindow", u"dd/MM/yyyy", None))
        self.MainTabs.setTabText(self.MainTabs.indexOf(self.ReportsTab), QCoreApplication.translate("JAL_MainWindow", u"Reports", None))
        self.MainTabs.setTabText(self.MainTabs.indexOf(self.LoggingTab), QCoreApplication.translate("JAL_MainWindow", u"Log messages", None))
        self.menuFile.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&File", None))
        self.menu_DAta.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Data", None))
        self.menuPredefined_data.setTitle(QCoreApplication.translate("JAL_MainWindow", u"Predefined data", None))
        self.menuLoad.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Load", None))
        self.menu_Reports.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Reports", None))
        self.menuLanguage.setTitle(QCoreApplication.translate("JAL_MainWindow", u"L&anguage", None))
        self.menuImport.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Import", None))
        self.menuStatement.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Statement", None))
    # retranslateUi

