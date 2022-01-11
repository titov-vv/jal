# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.2.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateEdit,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMenu, QMenuBar,
    QPushButton, QSizePolicy, QSpacerItem, QStatusBar,
    QTabWidget, QTableView, QTreeView, QVBoxLayout,
    QWidget, QAbstractItemView)

from jal.widgets.account_select import AccountButton
from jal.widgets.reference_selector import CategorySelector
from jal.widgets.tabbed_mdi_area import TabbedMdiArea

class Ui_JAL_MainWindow(object):
    def setupUi(self, JAL_MainWindow):
        if not JAL_MainWindow.objectName():
            JAL_MainWindow.setObjectName(u"JAL_MainWindow")
        JAL_MainWindow.resize(1482, 583)
        JAL_MainWindow.setMinimumSize(QSize(0, 0))
        self.actionExit = QAction(JAL_MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionExit.setMenuRole(QAction.QuitRole)
        self.action_Re_build_Ledger = QAction(JAL_MainWindow)
        self.action_Re_build_Ledger.setObjectName(u"action_Re_build_Ledger")
        self.action_LoadQuotes = QAction(JAL_MainWindow)
        self.action_LoadQuotes.setObjectName(u"action_LoadQuotes")
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
        self.verticalLayout_6.setSpacing(0)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.MainTabs = QTabWidget(self.centralwidget)
        self.MainTabs.setObjectName(u"MainTabs")
        self.MainTabs.setTabPosition(QTabWidget.West)
        self.MainTabs.setTabShape(QTabWidget.Triangular)
        self.MainTabs.setDocumentMode(False)
        self.MainTabs.setTabsClosable(True)
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
        self.ReportToDate.setDateTime(QDateTime(QDate(2020, 11, 28), QTime(21, 0, 0)))
        self.ReportToDate.setCalendarPopup(True)
        self.ReportToDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.ReportToDate, 1, 5, 1, 1)

        self.ReportAccountLbl = QLabel(self.ReportParamsFrame)
        self.ReportAccountLbl.setObjectName(u"ReportAccountLbl")

        self.gridLayout.addWidget(self.ReportAccountLbl, 1, 0, 1, 1)

        self.line_2 = QFrame(self.ReportParamsFrame)
        self.line_2.setObjectName(u"line_2")
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.line_2.sizePolicy().hasHeightForWidth())
        self.line_2.setSizePolicy(sizePolicy)
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
        self.ReportFromDate.setDateTime(QDateTime(QDate(2020, 11, 28), QTime(21, 0, 0)))
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

        self.verticalLayout_6.addWidget(self.MainTabs)

        self.mdiArea = TabbedMdiArea(self.centralwidget)
        self.mdiArea.setObjectName(u"mdiArea")

        self.verticalLayout_6.addWidget(self.mdiArea)

        JAL_MainWindow.setCentralWidget(self.centralwidget)
        self.MainMenu = QMenuBar(JAL_MainWindow)
        self.MainMenu.setObjectName(u"MainMenu")
        self.MainMenu.setGeometry(QRect(0, 0, 1482, 23))
        self.menuFile = QMenu(self.MainMenu)
        self.menuFile.setObjectName(u"menuFile")
        self.menu_Data = QMenu(self.MainMenu)
        self.menu_Data.setObjectName(u"menu_Data")
        self.menuPredefined_data = QMenu(self.menu_Data)
        self.menuPredefined_data.setObjectName(u"menuPredefined_data")
        self.menu_Export = QMenu(self.MainMenu)
        self.menu_Export.setObjectName(u"menu_Export")
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
        self.MainMenu.addAction(self.menu_Data.menuAction())
        self.MainMenu.addAction(self.menuImport.menuAction())
        self.MainMenu.addAction(self.menu_Export.menuAction())
        self.MainMenu.addAction(self.menuLanguage.menuAction())
        self.menuFile.addAction(self.actionExit)
        self.menu_Data.addSeparator()
        self.menu_Data.addAction(self.actionAccounts)
        self.menu_Data.addAction(self.actionAssets)
        self.menu_Data.addAction(self.actionPeers)
        self.menu_Data.addAction(self.actionCategories)
        self.menu_Data.addAction(self.actionTags)
        self.menu_Data.addAction(self.actionCountries)
        self.menu_Data.addAction(self.actionQuotes)
        self.menu_Data.addAction(self.menuPredefined_data.menuAction())
        self.menu_Data.addSeparator()
        self.menu_Data.addAction(self.actionBackup)
        self.menu_Data.addAction(self.actionRestore)
        self.menu_Data.addSeparator()
        self.menu_Data.addAction(self.action_Re_build_Ledger)
        self.menuPredefined_data.addAction(self.actionAccountTypes)
        self.menu_Export.addAction(self.PrepareTaxForms)
        self.menuImport.addAction(self.action_LoadQuotes)
        self.menuImport.addAction(self.menuStatement.menuAction())
        self.menuImport.addAction(self.actionImportSlipRU)

        self.retranslateUi(JAL_MainWindow)

        self.MainTabs.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(JAL_MainWindow)
    # setupUi

    def retranslateUi(self, JAL_MainWindow):
        JAL_MainWindow.setWindowTitle(QCoreApplication.translate("JAL_MainWindow", u"jal", None))
        self.actionExit.setText(QCoreApplication.translate("JAL_MainWindow", u"&Exit", None))
        self.action_Re_build_Ledger.setText(QCoreApplication.translate("JAL_MainWindow", u"Re-build &Ledger...", None))
        self.action_LoadQuotes.setText(QCoreApplication.translate("JAL_MainWindow", u"&Quotes...", None))
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
        self.menuFile.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&File", None))
        self.menu_Data.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Data", None))
        self.menuPredefined_data.setTitle(QCoreApplication.translate("JAL_MainWindow", u"Predefined data", None))
        self.menu_Export.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Export", None))
        self.menuLanguage.setTitle(QCoreApplication.translate("JAL_MainWindow", u"L&anguage", None))
        self.menuImport.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Import", None))
        self.menuStatement.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Statement", None))
    # retranslateUi

