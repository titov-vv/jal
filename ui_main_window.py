# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 5.14.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QMetaObject, QObject, QPoint,
    QRect, QSize, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QFont,
    QFontDatabase, QIcon, QLinearGradient, QPalette, QPainter, QPixmap,
    QRadialGradient)
from PySide2.QtWidgets import *

class Ui_LedgerMainWindow(object):
    def setupUi(self, LedgerMainWindow):
        if LedgerMainWindow.objectName():
            LedgerMainWindow.setObjectName(u"LedgerMainWindow")
        LedgerMainWindow.resize(1200, 900)
        LedgerMainWindow.setMinimumSize(QSize(0, 0))
        font = QFont()
        font.setFamily(u"DejaVu Sans")
        LedgerMainWindow.setFont(font)
        self.actionExit = QAction(LedgerMainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.action_Re_build_Ledger = QAction(LedgerMainWindow)
        self.action_Re_build_Ledger.setObjectName(u"action_Re_build_Ledger")
        self.action_Import = QAction(LedgerMainWindow)
        self.action_Import.setObjectName(u"action_Import")
        self.action_Load_quotes = QAction(LedgerMainWindow)
        self.action_Load_quotes.setObjectName(u"action_Load_quotes")
        self.actionLoad_Statement = QAction(LedgerMainWindow)
        self.actionLoad_Statement.setObjectName(u"actionLoad_Statement")
        self.centralwidget = QWidget(LedgerMainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setMaximumSize(QSize(16777215, 16777215))
        font1 = QFont()
        font1.setPointSize(10)
        self.centralwidget.setFont(font1)
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.MainTabs = QTabWidget(self.centralwidget)
        self.MainTabs.setObjectName(u"MainTabs")
        self.MainTabs.setTabPosition(QTabWidget.West)
        self.MainTabs.setTabShape(QTabWidget.Triangular)
        self.TabMain = QWidget()
        self.TabMain.setObjectName(u"TabMain")
        self.horizontalLayout = QHBoxLayout(self.TabMain)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.BalanceOperationsSplitter = QSplitter(self.TabMain)
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
        self.BalanceDate.setCalendarPopup(True)

        self.horizontalLayout_2.addWidget(self.BalanceDate)

        self.CurrencyLbl = QLabel(self.BalanceConfigFrame)
        self.CurrencyLbl.setObjectName(u"CurrencyLbl")
        self.CurrencyLbl.setLayoutDirection(Qt.LeftToRight)
        self.CurrencyLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_2.addWidget(self.CurrencyLbl)

        self.CurrencyCombo = QComboBox(self.BalanceConfigFrame)
        self.CurrencyCombo.setObjectName(u"CurrencyCombo")

        self.horizontalLayout_2.addWidget(self.CurrencyCombo)

        self.ShowInactiveCheckBox = QCheckBox(self.BalanceConfigFrame)
        self.ShowInactiveCheckBox.setObjectName(u"ShowInactiveCheckBox")

        self.horizontalLayout_2.addWidget(self.ShowInactiveCheckBox)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)


        self.verticalLayout.addWidget(self.BalanceConfigFrame)

        self.BalancesTableView = QTableView(self.BalanceBox)
        self.BalancesTableView.setObjectName(u"BalancesTableView")
        self.BalancesTableView.setFrameShape(QFrame.Panel)
        self.BalancesTableView.setGridStyle(Qt.DotLine)
        self.BalancesTableView.setWordWrap(False)

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
        self.DateRangeCombo.setMinimumSize(QSize(100, 0))

        self.horizontalLayout_3.addWidget(self.DateRangeCombo)

        self.AccountLbl = QLabel(self.OperationConfigFrame)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.horizontalLayout_3.addWidget(self.AccountLbl)

        self.ChooseAccountBtn = QPushButton(self.OperationConfigFrame)
        self.ChooseAccountBtn.setObjectName(u"ChooseAccountBtn")

        self.horizontalLayout_3.addWidget(self.ChooseAccountBtn)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)


        self.verticalLayout_2.addWidget(self.OperationConfigFrame)

        self.OperationsDetailsSplitter = QSplitter(self.OperationsBox)
        self.OperationsDetailsSplitter.setObjectName(u"OperationsDetailsSplitter")
        self.OperationsDetailsSplitter.setOrientation(Qt.Vertical)
        self.OperationsTableView = QTableView(self.OperationsDetailsSplitter)
        self.OperationsTableView.setObjectName(u"OperationsTableView")
        self.OperationsDetailsSplitter.addWidget(self.OperationsTableView)
        self.OperationDetails = QFrame(self.OperationsDetailsSplitter)
        self.OperationDetails.setObjectName(u"OperationDetails")
        self.OperationDetails.setMinimumSize(QSize(0, 100))
        self.OperationDetails.setMaximumSize(QSize(16777215, 250))
        self.OperationDetails.setFrameShape(QFrame.Panel)
        self.OperationDetails.setFrameShadow(QFrame.Plain)
        self.OperationDetails.setLineWidth(0)
        self.horizontalLayout_4 = QHBoxLayout(self.OperationDetails)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.OperationsTabs = QTabWidget(self.OperationDetails)
        self.OperationsTabs.setObjectName(u"OperationsTabs")
        self.OperationsTabs.setMinimumSize(QSize(0, 0))
        self.OperationsTabs.setTabPosition(QTabWidget.South)
        self.OperationsTabs.setTabShape(QTabWidget.Triangular)
        self.ActionDetailsTab = QWidget()
        self.ActionDetailsTab.setObjectName(u"ActionDetailsTab")
        self.OperationsTabs.addTab(self.ActionDetailsTab, "")
        self.TradeDetailsTab = QWidget()
        self.TradeDetailsTab.setObjectName(u"TradeDetailsTab")
        self.TradeAccountCombo = QComboBox(self.TradeDetailsTab)
        self.TradeAccountCombo.setObjectName(u"TradeAccountCombo")
        self.TradeAccountCombo.setGeometry(QRect(10, 10, 271, 23))
        self.TradeNumberEdit = QLineEdit(self.TradeDetailsTab)
        self.TradeNumberEdit.setObjectName(u"TradeNumberEdit")
        self.TradeNumberEdit.setGeometry(QRect(10, 40, 271, 23))
        self.OperationsTabs.addTab(self.TradeDetailsTab, "")
        self.DividendDetailsTab = QWidget()
        self.DividendDetailsTab.setObjectName(u"DividendDetailsTab")
        self.gridLayout_2 = QGridLayout(self.DividendDetailsTab)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.DividendSumEdit = QLineEdit(self.DividendDetailsTab)
        self.DividendSumEdit.setObjectName(u"DividendSumEdit")

        self.gridLayout_2.addWidget(self.DividendSumEdit, 5, 3, 1, 1)

        self.DivDateLbl = QLabel(self.DividendDetailsTab)
        self.DivDateLbl.setObjectName(u"DivDateLbl")

        self.gridLayout_2.addWidget(self.DivDateLbl, 1, 0, 1, 1)

        self.SumLbl = QLabel(self.DividendDetailsTab)
        self.SumLbl.setObjectName(u"SumLbl")

        self.gridLayout_2.addWidget(self.SumLbl, 5, 0, 1, 1)

        self.DividendSumDescription = QLineEdit(self.DividendDetailsTab)
        self.DividendSumDescription.setObjectName(u"DividendSumDescription")

        self.gridLayout_2.addWidget(self.DividendSumDescription, 5, 4, 1, 1)

        self.DividendNumberEdit = QLineEdit(self.DividendDetailsTab)
        self.DividendNumberEdit.setObjectName(u"DividendNumberEdit")

        self.gridLayout_2.addWidget(self.DividendNumberEdit, 1, 4, 1, 1)

        self.TaxLbl = QLabel(self.DividendDetailsTab)
        self.TaxLbl.setObjectName(u"TaxLbl")

        self.gridLayout_2.addWidget(self.TaxLbl, 7, 0, 1, 1)

        self.DividendTaxDescription = QLineEdit(self.DividendDetailsTab)
        self.DividendTaxDescription.setObjectName(u"DividendTaxDescription")

        self.gridLayout_2.addWidget(self.DividendTaxDescription, 7, 4, 1, 1)

        self.DividendAccountCombo = QComboBox(self.DividendDetailsTab)
        self.DividendAccountCombo.setObjectName(u"DividendAccountCombo")

        self.gridLayout_2.addWidget(self.DividendAccountCombo, 0, 3, 1, 1)

        self.DividendTaxEdit = QLineEdit(self.DividendDetailsTab)
        self.DividendTaxEdit.setObjectName(u"DividendTaxEdit")

        self.gridLayout_2.addWidget(self.DividendTaxEdit, 7, 3, 1, 1)

        self.DivAccountLbl = QLabel(self.DividendDetailsTab)
        self.DivAccountLbl.setObjectName(u"DivAccountLbl")

        self.gridLayout_2.addWidget(self.DivAccountLbl, 0, 0, 1, 1)

        self.DividendActiveLbl = QLabel(self.DividendDetailsTab)
        self.DividendActiveLbl.setObjectName(u"DividendActiveLbl")

        self.gridLayout_2.addWidget(self.DividendActiveLbl, 4, 4, 1, 1)

        self.label = QLabel(self.DividendDetailsTab)
        self.label.setObjectName(u"label")

        self.gridLayout_2.addWidget(self.label, 4, 0, 1, 1)

        self.DividendTimestampEdit = QDateTimeEdit(self.DividendDetailsTab)
        self.DividendTimestampEdit.setObjectName(u"DividendTimestampEdit")
        self.DividendTimestampEdit.setCalendarPopup(True)

        self.gridLayout_2.addWidget(self.DividendTimestampEdit, 1, 3, 1, 1)

        self.DividendActiveCombo = QComboBox(self.DividendDetailsTab)
        self.DividendActiveCombo.setObjectName(u"DividendActiveCombo")

        self.gridLayout_2.addWidget(self.DividendActiveCombo, 4, 3, 1, 1)

        self.frame = QFrame(self.DividendDetailsTab)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Panel)
        self.frame.setFrameShadow(QFrame.Plain)
        self.frame.setLineWidth(0)
        self.horizontalLayout_5 = QHBoxLayout(self.frame)
        self.horizontalLayout_5.setSpacing(2)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.DividendAppendBtn = QPushButton(self.frame)
        self.DividendAppendBtn.setObjectName(u"DividendAppendBtn")

        self.horizontalLayout_5.addWidget(self.DividendAppendBtn)

        self.DividendRemoveBtn = QPushButton(self.frame)
        self.DividendRemoveBtn.setObjectName(u"DividendRemoveBtn")

        self.horizontalLayout_5.addWidget(self.DividendRemoveBtn)

        self.DividendCopyBtn = QPushButton(self.frame)
        self.DividendCopyBtn.setObjectName(u"DividendCopyBtn")

        self.horizontalLayout_5.addWidget(self.DividendCopyBtn)

        self.DividendCommitBtn = QPushButton(self.frame)
        self.DividendCommitBtn.setObjectName(u"DividendCommitBtn")

        self.horizontalLayout_5.addWidget(self.DividendCommitBtn)


        self.gridLayout_2.addWidget(self.frame, 0, 4, 1, 1)

        self.OperationsTabs.addTab(self.DividendDetailsTab, "")

        self.horizontalLayout_4.addWidget(self.OperationsTabs)

        self.OperationsDetailsSplitter.addWidget(self.OperationDetails)

        self.verticalLayout_2.addWidget(self.OperationsDetailsSplitter)

        self.BalanceOperationsSplitter.addWidget(self.OperationsBox)

        self.horizontalLayout.addWidget(self.BalanceOperationsSplitter)

        self.MainTabs.addTab(self.TabMain, "")
        self.TabTransactions = QWidget()
        self.TabTransactions.setObjectName(u"TabTransactions")
        self.MainTabs.addTab(self.TabTransactions, "")

        self.gridLayout.addWidget(self.MainTabs, 0, 0, 1, 1)

        LedgerMainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(LedgerMainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1200, 20))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menu_DAta = QMenu(self.menubar)
        self.menu_DAta.setObjectName(u"menu_DAta")
        LedgerMainWindow.setMenuBar(self.menubar)
        self.StatusBar = QStatusBar(LedgerMainWindow)
        self.StatusBar.setObjectName(u"StatusBar")
        LedgerMainWindow.setStatusBar(self.StatusBar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menu_DAta.menuAction())
        self.menuFile.addAction(self.actionExit)
        self.menu_DAta.addSeparator()
        self.menu_DAta.addAction(self.action_Load_quotes)
        self.menu_DAta.addAction(self.actionLoad_Statement)
        self.menu_DAta.addSeparator()
        self.menu_DAta.addAction(self.action_Import)
        self.menu_DAta.addAction(self.action_Re_build_Ledger)

        self.retranslateUi(LedgerMainWindow)

        self.MainTabs.setCurrentIndex(0)
        self.OperationsTabs.setCurrentIndex(2)


        QMetaObject.connectSlotsByName(LedgerMainWindow)
    # setupUi

    def retranslateUi(self, LedgerMainWindow):
        LedgerMainWindow.setWindowTitle(QCoreApplication.translate("LedgerMainWindow", u"Ledger", None))
        self.actionExit.setText(QCoreApplication.translate("LedgerMainWindow", u"&Exit", None))
        self.action_Re_build_Ledger.setText(QCoreApplication.translate("LedgerMainWindow", u"&Re-build Ledger", None))
        self.action_Import.setText(QCoreApplication.translate("LedgerMainWindow", u"&Import...", None))
        self.action_Load_quotes.setText(QCoreApplication.translate("LedgerMainWindow", u"Load &quotes", None))
        self.actionLoad_Statement.setText(QCoreApplication.translate("LedgerMainWindow", u"Load &Statement...", None))
        self.BalanceBox.setTitle(QCoreApplication.translate("LedgerMainWindow", u"Balances", None))
        self.BalanceDate.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy", None))
        self.CurrencyLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Sum Currency:", None))
        self.ShowInactiveCheckBox.setText(QCoreApplication.translate("LedgerMainWindow", u"Show &Inactive", None))
        self.OperationsBox.setTitle(QCoreApplication.translate("LedgerMainWindow", u"Operations", None))
        self.DateRangeLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Time range:", None))
        self.DateRangeCombo.setItemText(0, QCoreApplication.translate("LedgerMainWindow", u"last Week", None))
        self.DateRangeCombo.setItemText(1, QCoreApplication.translate("LedgerMainWindow", u"last Month", None))
        self.DateRangeCombo.setItemText(2, QCoreApplication.translate("LedgerMainWindow", u"last Half-year", None))
        self.DateRangeCombo.setItemText(3, QCoreApplication.translate("LedgerMainWindow", u"last Year", None))
        self.DateRangeCombo.setItemText(4, QCoreApplication.translate("LedgerMainWindow", u"All", None))

        self.AccountLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Account:", None))
        self.ChooseAccountBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"All", None))
        self.OperationsTabs.setTabText(self.OperationsTabs.indexOf(self.ActionDetailsTab), QCoreApplication.translate("LedgerMainWindow", u"Income / Spending", None))
        self.OperationsTabs.setTabText(self.OperationsTabs.indexOf(self.TradeDetailsTab), QCoreApplication.translate("LedgerMainWindow", u"Buy / Sell", None))
        self.DivDateLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Timestamp", None))
        self.SumLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Sum", None))
        self.TaxLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Tax", None))
        self.DivAccountLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Account:", None))
        self.DividendActiveLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"TextLabel", None))
        self.label.setText(QCoreApplication.translate("LedgerMainWindow", u"Security", None))
        self.DividendTimestampEdit.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy hh:mm:ss", None))
        self.DividendAppendBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Add", None))
        self.DividendRemoveBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Del", None))
        self.DividendCopyBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Copy", None))
        self.DividendCommitBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Commit", None))
        self.OperationsTabs.setTabText(self.OperationsTabs.indexOf(self.DividendDetailsTab), QCoreApplication.translate("LedgerMainWindow", u"Dividend", None))
        self.MainTabs.setTabText(self.MainTabs.indexOf(self.TabMain), QCoreApplication.translate("LedgerMainWindow", u"Balance", None))
        self.MainTabs.setTabText(self.MainTabs.indexOf(self.TabTransactions), QCoreApplication.translate("LedgerMainWindow", u"Transactions", None))
        self.menuFile.setTitle(QCoreApplication.translate("LedgerMainWindow", u"&File", None))
        self.menu_DAta.setTitle(QCoreApplication.translate("LedgerMainWindow", u"&Data", None))
    # retranslateUi

