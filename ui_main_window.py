# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 5.14.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QMetaObject, QObject, QPoint,
    QRect, QSize, QUrl, Qt, QDate)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QFont,
    QFontDatabase, QIcon, QLinearGradient, QPalette, QPainter, QPixmap,
    QRadialGradient)
from PySide2.QtWidgets import *

from CustomUI.account_select import AccountSelector
from CustomUI.active_select import ActiveSelector
from CustomUI.account_select import AccountButton

class Ui_LedgerMainWindow(object):
    def setupUi(self, LedgerMainWindow):
        if LedgerMainWindow.objectName():
            LedgerMainWindow.setObjectName(u"LedgerMainWindow")
        LedgerMainWindow.resize(1700, 900)
        LedgerMainWindow.setMinimumSize(QSize(0, 0))
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
        self.BalancesTableView.setAlternatingRowColors(True)
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
        self.DateRangeCombo.setMinimumSize(QSize(100, 0))

        self.horizontalLayout_3.addWidget(self.DateRangeCombo)

        self.AccountLbl = QLabel(self.OperationConfigFrame)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.horizontalLayout_3.addWidget(self.AccountLbl)

        self.ChooseAccountBtn = AccountButton(self.OperationConfigFrame)
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
        self.OperationsTableView.setAlternatingRowColors(True)
        self.OperationsTableView.setWordWrap(False)
        self.OperationsDetailsSplitter.addWidget(self.OperationsTableView)
        self.OperationsTableView.verticalHeader().setVisible(False)
        self.OperationsTableView.verticalHeader().setMinimumSectionSize(1)
        self.OperationsTableView.verticalHeader().setDefaultSectionSize(1)
        self.OperationDetails = QFrame(self.OperationsDetailsSplitter)
        self.OperationDetails.setObjectName(u"OperationDetails")
        self.OperationDetails.setMinimumSize(QSize(0, 100))
        self.OperationDetails.setMaximumSize(QSize(16777215, 300))
        self.OperationDetails.setFrameShape(QFrame.Panel)
        self.OperationDetails.setFrameShadow(QFrame.Plain)
        self.OperationDetails.setLineWidth(0)
        self.horizontalLayout_4 = QHBoxLayout(self.OperationDetails)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.OperationsTabs = QTabWidget(self.OperationDetails)
        self.OperationsTabs.setObjectName(u"OperationsTabs")
        self.OperationsTabs.setEnabled(True)
        self.OperationsTabs.setMinimumSize(QSize(0, 0))
        self.OperationsTabs.setTabPosition(QTabWidget.South)
        self.OperationsTabs.setTabShape(QTabWidget.Triangular)
        self.ActionDetailsTab = QWidget()
        self.ActionDetailsTab.setObjectName(u"ActionDetailsTab")
        self.gridLayout_4 = QGridLayout(self.ActionDetailsTab)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.gridLayout_4.setContentsMargins(2, 2, 2, 2)
        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_4.addItem(self.verticalSpacer_3, 0, 0, 1, 1)

        self.ActionDetailsTableView = QTableView(self.ActionDetailsTab)
        self.ActionDetailsTableView.setObjectName(u"ActionDetailsTableView")
        self.ActionDetailsTableView.setAlternatingRowColors(True)
        self.ActionDetailsTableView.verticalHeader().setVisible(False)
        self.ActionDetailsTableView.verticalHeader().setMinimumSectionSize(20)
        self.ActionDetailsTableView.verticalHeader().setDefaultSectionSize(20)

        self.gridLayout_4.addWidget(self.ActionDetailsTableView, 3, 0, 1, 3)

        self.ActionPeerEdit = QLineEdit(self.ActionDetailsTab)
        self.ActionPeerEdit.setObjectName(u"ActionPeerEdit")

        self.gridLayout_4.addWidget(self.ActionPeerEdit, 2, 2, 1, 1)

        self.ActionAccountWidget = AccountSelector(self.ActionDetailsTab)
        self.ActionAccountWidget.setObjectName(u"ActionAccountWidget")

        self.gridLayout_4.addWidget(self.ActionAccountWidget, 1, 2, 1, 1)

        self.ActionTimestampEdit = QDateTimeEdit(self.ActionDetailsTab)
        self.ActionTimestampEdit.setObjectName(u"ActionTimestampEdit")
        self.ActionTimestampEdit.setCalendarPopup(True)

        self.gridLayout_4.addWidget(self.ActionTimestampEdit, 1, 0, 1, 1)

        self.frame = QFrame(self.ActionDetailsTab)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_6 = QHBoxLayout(self.frame)
        self.horizontalLayout_6.setSpacing(8)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.AddActionDetail = QPushButton(self.frame)
        self.AddActionDetail.setObjectName(u"AddActionDetail")

        self.horizontalLayout_6.addWidget(self.AddActionDetail)

        self.RemoveActionDetail = QPushButton(self.frame)
        self.RemoveActionDetail.setObjectName(u"RemoveActionDetail")

        self.horizontalLayout_6.addWidget(self.RemoveActionDetail)


        self.gridLayout_4.addWidget(self.frame, 2, 0, 1, 1)

        self.OperationsTabs.addTab(self.ActionDetailsTab, "")
        self.TradeDetailsTab = QWidget()
        self.TradeDetailsTab.setObjectName(u"TradeDetailsTab")
        self.gridLayout_3 = QGridLayout(self.TradeDetailsTab)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(2, 2, 2, 2)
        self.TradePriceLbl = QLabel(self.TradeDetailsTab)
        self.TradePriceLbl.setObjectName(u"TradePriceLbl")

        self.gridLayout_3.addWidget(self.TradePriceLbl, 6, 0, 1, 1)

        self.TradeQtyEdit = QLineEdit(self.TradeDetailsTab)
        self.TradeQtyEdit.setObjectName(u"TradeQtyEdit")

        self.gridLayout_3.addWidget(self.TradeQtyEdit, 6, 3, 1, 1)

        self.TradeActiveLbl = QLabel(self.TradeDetailsTab)
        self.TradeActiveLbl.setObjectName(u"TradeActiveLbl")

        self.gridLayout_3.addWidget(self.TradeActiveLbl, 5, 0, 1, 1)

        self.TradeExchangeFeeEdit = QLineEdit(self.TradeDetailsTab)
        self.TradeExchangeFeeEdit.setObjectName(u"TradeExchangeFeeEdit")

        self.gridLayout_3.addWidget(self.TradeExchangeFeeEdit, 7, 3, 1, 1)

        self.FeeLbl = QLabel(self.TradeDetailsTab)
        self.FeeLbl.setObjectName(u"FeeLbl")

        self.gridLayout_3.addWidget(self.FeeLbl, 7, 0, 1, 1)

        self.TradeTimestampLbl = QLabel(self.TradeDetailsTab)
        self.TradeTimestampLbl.setObjectName(u"TradeTimestampLbl")

        self.gridLayout_3.addWidget(self.TradeTimestampLbl, 2, 0, 1, 1)

        self.TradeAccountLbl = QLabel(self.TradeDetailsTab)
        self.TradeAccountLbl.setObjectName(u"TradeAccountLbl")

        self.gridLayout_3.addWidget(self.TradeAccountLbl, 1, 0, 1, 1)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_3.addItem(self.verticalSpacer_2, 0, 0, 1, 1)

        self.TradeBrokerFeeEdit = QLineEdit(self.TradeDetailsTab)
        self.TradeBrokerFeeEdit.setObjectName(u"TradeBrokerFeeEdit")

        self.gridLayout_3.addWidget(self.TradeBrokerFeeEdit, 7, 2, 1, 1)

        self.TradePriceEdit = QLineEdit(self.TradeDetailsTab)
        self.TradePriceEdit.setObjectName(u"TradePriceEdit")

        self.gridLayout_3.addWidget(self.TradePriceEdit, 6, 2, 1, 1)

        self.TradeNumberEdit = QLineEdit(self.TradeDetailsTab)
        self.TradeNumberEdit.setObjectName(u"TradeNumberEdit")

        self.gridLayout_3.addWidget(self.TradeNumberEdit, 2, 3, 1, 1)

        self.TradeTimestampEdit = QDateTimeEdit(self.TradeDetailsTab)
        self.TradeTimestampEdit.setObjectName(u"TradeTimestampEdit")
        self.TradeTimestampEdit.setCalendarPopup(True)

        self.gridLayout_3.addWidget(self.TradeTimestampEdit, 2, 1, 1, 1)

        self.TradeSettlementEdit = QDateEdit(self.TradeDetailsTab)
        self.TradeSettlementEdit.setObjectName(u"TradeSettlementEdit")
        self.TradeSettlementEdit.setMinimumDate(QDate(2000, 1, 1))
        self.TradeSettlementEdit.setCalendarPopup(True)

        self.gridLayout_3.addWidget(self.TradeSettlementEdit, 2, 2, 1, 1)

        self.TradeCouponEdit = QLineEdit(self.TradeDetailsTab)
        self.TradeCouponEdit.setObjectName(u"TradeCouponEdit")

        self.gridLayout_3.addWidget(self.TradeCouponEdit, 7, 1, 1, 1)

        self.TradeAccountWidget = AccountSelector(self.TradeDetailsTab)
        self.TradeAccountWidget.setObjectName(u"TradeAccountWidget")

        self.gridLayout_3.addWidget(self.TradeAccountWidget, 1, 1, 1, 2)

        self.TradeActiveWidget = ActiveSelector(self.TradeDetailsTab)
        self.TradeActiveWidget.setObjectName(u"TradeActiveWidget")

        self.gridLayout_3.addWidget(self.TradeActiveWidget, 5, 1, 1, 2)

        self.TypeGroupFrame = QFrame(self.TradeDetailsTab)
        self.TypeGroupFrame.setObjectName(u"TypeGroupFrame")
        self.TypeGroupFrame.setFrameShape(QFrame.StyledPanel)
        self.TypeGroupFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.TypeGroupFrame)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(9, 0, 9, 0)
        self.BuyRadioBtn = QRadioButton(self.TypeGroupFrame)
        self.BuyRadioBtn.setObjectName(u"BuyRadioBtn")

        self.horizontalLayout_5.addWidget(self.BuyRadioBtn)

        self.SellRadioBtn = QRadioButton(self.TypeGroupFrame)
        self.SellRadioBtn.setObjectName(u"SellRadioBtn")

        self.horizontalLayout_5.addWidget(self.SellRadioBtn)


        self.gridLayout_3.addWidget(self.TypeGroupFrame, 1, 3, 1, 1)

        self.OperationsTabs.addTab(self.TradeDetailsTab, "")
        self.DividendDetailsTab = QWidget()
        self.DividendDetailsTab.setObjectName(u"DividendDetailsTab")
        self.gridLayout_2 = QGridLayout(self.DividendDetailsTab)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(2, 2, 2, 2)
        self.DividendSumEdit = QLineEdit(self.DividendDetailsTab)
        self.DividendSumEdit.setObjectName(u"DividendSumEdit")

        self.gridLayout_2.addWidget(self.DividendSumEdit, 7, 1, 1, 1)

        self.SumLbl = QLabel(self.DividendDetailsTab)
        self.SumLbl.setObjectName(u"SumLbl")

        self.gridLayout_2.addWidget(self.SumLbl, 7, 0, 1, 1)

        self.TaxLbl = QLabel(self.DividendDetailsTab)
        self.TaxLbl.setObjectName(u"TaxLbl")

        self.gridLayout_2.addWidget(self.TaxLbl, 8, 0, 1, 1)

        self.DivAccountLbl = QLabel(self.DividendDetailsTab)
        self.DivAccountLbl.setObjectName(u"DivAccountLbl")

        self.gridLayout_2.addWidget(self.DivAccountLbl, 1, 0, 1, 1)

        self.label = QLabel(self.DividendDetailsTab)
        self.label.setObjectName(u"label")

        self.gridLayout_2.addWidget(self.label, 6, 0, 1, 1)

        self.DividendTaxDescription = QLineEdit(self.DividendDetailsTab)
        self.DividendTaxDescription.setObjectName(u"DividendTaxDescription")

        self.gridLayout_2.addWidget(self.DividendTaxDescription, 8, 2, 1, 1)

        self.DividendTaxEdit = QLineEdit(self.DividendDetailsTab)
        self.DividendTaxEdit.setObjectName(u"DividendTaxEdit")

        self.gridLayout_2.addWidget(self.DividendTaxEdit, 8, 1, 1, 1)

        self.DividendSumDescription = QLineEdit(self.DividendDetailsTab)
        self.DividendSumDescription.setObjectName(u"DividendSumDescription")

        self.gridLayout_2.addWidget(self.DividendSumDescription, 7, 2, 1, 1)

        self.DividendNumberEdit = QLineEdit(self.DividendDetailsTab)
        self.DividendNumberEdit.setObjectName(u"DividendNumberEdit")

        self.gridLayout_2.addWidget(self.DividendNumberEdit, 3, 2, 1, 1)

        self.DividendTimestampEdit = QDateTimeEdit(self.DividendDetailsTab)
        self.DividendTimestampEdit.setObjectName(u"DividendTimestampEdit")
        self.DividendTimestampEdit.setCalendarPopup(True)

        self.gridLayout_2.addWidget(self.DividendTimestampEdit, 3, 1, 1, 1)

        self.DividendAccountWidget = AccountSelector(self.DividendDetailsTab)
        self.DividendAccountWidget.setObjectName(u"DividendAccountWidget")

        self.gridLayout_2.addWidget(self.DividendAccountWidget, 1, 1, 1, 1)

        self.DivDateLbl = QLabel(self.DividendDetailsTab)
        self.DivDateLbl.setObjectName(u"DivDateLbl")

        self.gridLayout_2.addWidget(self.DivDateLbl, 3, 0, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_2.addItem(self.verticalSpacer, 0, 0, 1, 1)

        self.DividendActiveWidget = ActiveSelector(self.DividendDetailsTab)
        self.DividendActiveWidget.setObjectName(u"DividendActiveWidget")

        self.gridLayout_2.addWidget(self.DividendActiveWidget, 6, 1, 1, 2)

        self.OperationsTabs.addTab(self.DividendDetailsTab, "")
        self.TransferDetailsTab = QWidget()
        self.TransferDetailsTab.setObjectName(u"TransferDetailsTab")
        self.gridLayout_5 = QGridLayout(self.TransferDetailsTab)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.TransferFeeAccountWidget = AccountSelector(self.TransferDetailsTab)
        self.TransferFeeAccountWidget.setObjectName(u"TransferFeeAccountWidget")

        self.gridLayout_5.addWidget(self.TransferFeeAccountWidget, 3, 1, 1, 1)

        self.TransferFromAccountWidget = AccountSelector(self.TransferDetailsTab)
        self.TransferFromAccountWidget.setObjectName(u"TransferFromAccountWidget")

        self.gridLayout_5.addWidget(self.TransferFromAccountWidget, 1, 1, 1, 1)

        self.TransferFeeTimestamp = QDateTimeEdit(self.TransferDetailsTab)
        self.TransferFeeTimestamp.setObjectName(u"TransferFeeTimestamp")
        self.TransferFeeTimestamp.setMinimumDate(QDate(2000, 1, 1))
        self.TransferFeeTimestamp.setCalendarPopup(True)

        self.gridLayout_5.addWidget(self.TransferFeeTimestamp, 3, 0, 1, 1)

        self.TransferToAccountWidget = AccountSelector(self.TransferDetailsTab)
        self.TransferToAccountWidget.setObjectName(u"TransferToAccountWidget")

        self.gridLayout_5.addWidget(self.TransferToAccountWidget, 2, 1, 1, 1)

        self.TransferFeeAmount = QLineEdit(self.TransferDetailsTab)
        self.TransferFeeAmount.setObjectName(u"TransferFeeAmount")

        self.gridLayout_5.addWidget(self.TransferFeeAmount, 3, 2, 1, 1)

        self.TransferToTimestamp = QDateTimeEdit(self.TransferDetailsTab)
        self.TransferToTimestamp.setObjectName(u"TransferToTimestamp")
        self.TransferToTimestamp.setCalendarPopup(True)

        self.gridLayout_5.addWidget(self.TransferToTimestamp, 2, 0, 1, 1)

        self.TransferFromTimestamp = QDateTimeEdit(self.TransferDetailsTab)
        self.TransferFromTimestamp.setObjectName(u"TransferFromTimestamp")
        self.TransferFromTimestamp.setCalendarPopup(True)

        self.gridLayout_5.addWidget(self.TransferFromTimestamp, 1, 0, 1, 1)

        self.TransferFromAmount = QLineEdit(self.TransferDetailsTab)
        self.TransferFromAmount.setObjectName(u"TransferFromAmount")

        self.gridLayout_5.addWidget(self.TransferFromAmount, 1, 2, 1, 1)

        self.TransferToAmount = QLineEdit(self.TransferDetailsTab)
        self.TransferToAmount.setObjectName(u"TransferToAmount")

        self.gridLayout_5.addWidget(self.TransferToAmount, 2, 2, 1, 1)

        self.verticalSpacer_5 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_5.addItem(self.verticalSpacer_5, 0, 0, 1, 1)

        self.TransferNote = QLineEdit(self.TransferDetailsTab)
        self.TransferNote.setObjectName(u"TransferNote")

        self.gridLayout_5.addWidget(self.TransferNote, 4, 0, 1, 3)

        self.OperationsTabs.addTab(self.TransferDetailsTab, "")

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

        self.DeleteOperationBtn = QPushButton(self.OperationsButtons)
        self.DeleteOperationBtn.setObjectName(u"DeleteOperationBtn")

        self.verticalLayout_3.addWidget(self.DeleteOperationBtn)

        self.CopyOperationBtn = QPushButton(self.OperationsButtons)
        self.CopyOperationBtn.setObjectName(u"CopyOperationBtn")

        self.verticalLayout_3.addWidget(self.CopyOperationBtn)

        self.SaveOperationBtn = QPushButton(self.OperationsButtons)
        self.SaveOperationBtn.setObjectName(u"SaveOperationBtn")

        self.verticalLayout_3.addWidget(self.SaveOperationBtn)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer_4)


        self.horizontalLayout_4.addWidget(self.OperationsButtons)

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
        self.menubar.setGeometry(QRect(0, 0, 1700, 22))
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
        self.OperationsTabs.setCurrentIndex(0)


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
        self.ActionTimestampEdit.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy hh:mm:ss", None))
        self.AddActionDetail.setText(QCoreApplication.translate("LedgerMainWindow", u" + ", None))
        self.RemoveActionDetail.setText(QCoreApplication.translate("LedgerMainWindow", u" \u2014 ", None))
        self.OperationsTabs.setTabText(self.OperationsTabs.indexOf(self.ActionDetailsTab), QCoreApplication.translate("LedgerMainWindow", u"Income / Spending", None))
        self.TradePriceLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Price / Qty", None))
        self.TradeActiveLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Security", None))
        self.FeeLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Coupon / Fee", None))
        self.TradeTimestampLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Timestamp", None))
        self.TradeAccountLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Account", None))
        self.TradeTimestampEdit.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy hh:mm:ss", None))
        self.TradeSettlementEdit.setSpecialValueText(QCoreApplication.translate("LedgerMainWindow", u"N/A", None))
        self.TradeSettlementEdit.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy", None))
        self.BuyRadioBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Buy", None))
        self.SellRadioBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Sell", None))
        self.OperationsTabs.setTabText(self.OperationsTabs.indexOf(self.TradeDetailsTab), QCoreApplication.translate("LedgerMainWindow", u"Buy / Sell", None))
        self.SumLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Sum", None))
        self.TaxLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Tax", None))
        self.DivAccountLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Account:", None))
        self.label.setText(QCoreApplication.translate("LedgerMainWindow", u"Security", None))
        self.DividendTimestampEdit.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy hh:mm:ss", None))
        self.DivDateLbl.setText(QCoreApplication.translate("LedgerMainWindow", u"Timestamp", None))
        self.OperationsTabs.setTabText(self.OperationsTabs.indexOf(self.DividendDetailsTab), QCoreApplication.translate("LedgerMainWindow", u"Dividend", None))
        self.TransferFeeTimestamp.setSpecialValueText(QCoreApplication.translate("LedgerMainWindow", u"N/A", None))
        self.TransferFeeTimestamp.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy hh:mm:ss", None))
        self.TransferToTimestamp.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy hh:mm:ss", None))
        self.TransferFromTimestamp.setDisplayFormat(QCoreApplication.translate("LedgerMainWindow", u"dd/MM/yyyy hh:mm:ss", None))
        self.OperationsTabs.setTabText(self.OperationsTabs.indexOf(self.TransferDetailsTab), QCoreApplication.translate("LedgerMainWindow", u"Transfer", None))
        self.NewOperationBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"New", None))
        self.DeleteOperationBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Del", None))
        self.CopyOperationBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Copy", None))
        self.SaveOperationBtn.setText(QCoreApplication.translate("LedgerMainWindow", u"Save", None))
        self.MainTabs.setTabText(self.MainTabs.indexOf(self.TabMain), QCoreApplication.translate("LedgerMainWindow", u"Balance", None))
        self.MainTabs.setTabText(self.MainTabs.indexOf(self.TabTransactions), QCoreApplication.translate("LedgerMainWindow", u"Transactions", None))
        self.menuFile.setTitle(QCoreApplication.translate("LedgerMainWindow", u"&File", None))
        self.menu_DAta.setTitle(QCoreApplication.translate("LedgerMainWindow", u"&Data", None))
    # retranslateUi

