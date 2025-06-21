# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
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
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QMenuBar,
    QSizePolicy, QSplitter, QStatusBar, QVBoxLayout,
    QWidget)

from jal.widgets.custom.log_viewer import LogViewer
from jal.widgets.mdi import TabbedMdiArea

class Ui_JAL_MainWindow(object):
    def setupUi(self, JAL_MainWindow):
        if not JAL_MainWindow.objectName():
            JAL_MainWindow.setObjectName(u"JAL_MainWindow")
        JAL_MainWindow.resize(835, 436)
        JAL_MainWindow.setMinimumSize(QSize(0, 0))
        self.actionExit = QAction(JAL_MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionExit.setMenuRole(QAction.QuitRole)
        self.action_Re_build_Ledger = QAction(JAL_MainWindow)
        self.action_Re_build_Ledger.setObjectName(u"action_Re_build_Ledger")
        self.action_LoadQuotes = QAction(JAL_MainWindow)
        self.action_LoadQuotes.setObjectName(u"action_LoadQuotes")
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
        self.actionTags = QAction(JAL_MainWindow)
        self.actionTags.setObjectName(u"actionTags")
        self.actionImportShopReceipt = QAction(JAL_MainWindow)
        self.actionImportShopReceipt.setObjectName(u"actionImportShopReceipt")
        self.actionQuotes = QAction(JAL_MainWindow)
        self.actionQuotes.setObjectName(u"actionQuotes")
        self.actionOperations = QAction(JAL_MainWindow)
        self.actionOperations.setObjectName(u"actionOperations")
        self.PrepareFlowReport = QAction(JAL_MainWindow)
        self.PrepareFlowReport.setObjectName(u"PrepareFlowReport")
        self.actionBaseCurrency = QAction(JAL_MainWindow)
        self.actionBaseCurrency.setObjectName(u"actionBaseCurrency")
        self.actionCleanAll = QAction(JAL_MainWindow)
        self.actionCleanAll.setObjectName(u"actionCleanAll")
        self.centralwidget = QWidget(JAL_MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setMaximumSize(QSize(16777215, 16777215))
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.centralwidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Vertical)
        self.mdiArea = TabbedMdiArea(self.splitter)
        self.mdiArea.setObjectName(u"mdiArea")
        self.splitter.addWidget(self.mdiArea)
        self.Logs = LogViewer(self.splitter)
        self.Logs.setObjectName(u"Logs")
        self.splitter.addWidget(self.Logs)

        self.verticalLayout.addWidget(self.splitter)

        JAL_MainWindow.setCentralWidget(self.centralwidget)
        self.MainMenu = QMenuBar(JAL_MainWindow)
        self.MainMenu.setObjectName(u"MainMenu")
        self.MainMenu.setGeometry(QRect(0, 0, 835, 23))
        self.menuMain = QMenu(self.MainMenu)
        self.menuMain.setObjectName(u"menuMain")
        self.menu_Data = QMenu(self.MainMenu)
        self.menu_Data.setObjectName(u"menu_Data")
        self.menu_Export = QMenu(self.MainMenu)
        self.menu_Export.setObjectName(u"menu_Export")
        self.menuLanguage = QMenu(self.MainMenu)
        self.menuLanguage.setObjectName(u"menuLanguage")
        self.menuImport = QMenu(self.MainMenu)
        self.menuImport.setObjectName(u"menuImport")
        self.menuStatement = QMenu(self.menuImport)
        self.menuStatement.setObjectName(u"menuStatement")
        self.menuReports = QMenu(self.MainMenu)
        self.menuReports.setObjectName(u"menuReports")
        JAL_MainWindow.setMenuBar(self.MainMenu)
        self.StatusBar = QStatusBar(JAL_MainWindow)
        self.StatusBar.setObjectName(u"StatusBar")
        JAL_MainWindow.setStatusBar(self.StatusBar)

        self.MainMenu.addAction(self.menuMain.menuAction())
        self.MainMenu.addAction(self.menu_Data.menuAction())
        self.MainMenu.addAction(self.menuReports.menuAction())
        self.MainMenu.addAction(self.menuImport.menuAction())
        self.MainMenu.addAction(self.menu_Export.menuAction())
        self.MainMenu.addAction(self.menuLanguage.menuAction())
        self.menuMain.addAction(self.actionOperations)
        self.menuMain.addAction(self.actionExit)
        self.menu_Data.addSeparator()
        self.menu_Data.addAction(self.action_Re_build_Ledger)
        self.menu_Data.addSeparator()
        self.menu_Data.addAction(self.actionAccounts)
        self.menu_Data.addAction(self.actionAssets)
        self.menu_Data.addAction(self.actionPeers)
        self.menu_Data.addAction(self.actionCategories)
        self.menu_Data.addAction(self.actionTags)
        self.menu_Data.addAction(self.actionQuotes)
        self.menu_Data.addSeparator()
        self.menu_Data.addAction(self.actionBaseCurrency)
        self.menu_Data.addSeparator()
        self.menu_Data.addAction(self.actionBackup)
        self.menu_Data.addAction(self.actionRestore)
        self.menu_Data.addSeparator()
        self.menu_Data.addAction(self.actionCleanAll)
        self.menu_Export.addAction(self.PrepareTaxForms)
        self.menu_Export.addAction(self.PrepareFlowReport)
        self.menuImport.addAction(self.action_LoadQuotes)
        self.menuImport.addAction(self.menuStatement.menuAction())
        self.menuImport.addAction(self.actionImportShopReceipt)

        self.retranslateUi(JAL_MainWindow)

        QMetaObject.connectSlotsByName(JAL_MainWindow)
    # setupUi

    def retranslateUi(self, JAL_MainWindow):
        JAL_MainWindow.setWindowTitle(QCoreApplication.translate("JAL_MainWindow", u"jal", None))
        self.actionExit.setText(QCoreApplication.translate("JAL_MainWindow", u"&Exit", None))
        self.action_Re_build_Ledger.setText(QCoreApplication.translate("JAL_MainWindow", u"Re-build &Ledger...", None))
        self.action_LoadQuotes.setText(QCoreApplication.translate("JAL_MainWindow", u"&Quotes...", None))
        self.actionAccounts.setText(QCoreApplication.translate("JAL_MainWindow", u"&Accounts", None))
        self.actionAssets.setText(QCoreApplication.translate("JAL_MainWindow", u"A&ssets", None))
        self.actionPeers.setText(QCoreApplication.translate("JAL_MainWindow", u"&Peers", None))
        self.actionCategories.setText(QCoreApplication.translate("JAL_MainWindow", u"&Categories", None))
        self.actionBackup.setText(QCoreApplication.translate("JAL_MainWindow", u"&Backup...", None))
        self.actionRestore.setText(QCoreApplication.translate("JAL_MainWindow", u"&Restore...", None))
        self.PrepareTaxForms.setText(QCoreApplication.translate("JAL_MainWindow", u"Investment &tax report", None))
        self.actionTags.setText(QCoreApplication.translate("JAL_MainWindow", u"&Tags", None))
        self.actionImportShopReceipt.setText(QCoreApplication.translate("JAL_MainWindow", u"&Receipt...", None))
        self.actionQuotes.setText(QCoreApplication.translate("JAL_MainWindow", u"&Quotes", None))
        self.actionOperations.setText(QCoreApplication.translate("JAL_MainWindow", u"&Operations", None))
        self.PrepareFlowReport.setText(QCoreApplication.translate("JAL_MainWindow", u"Foreign accounts &flow report", None))
        self.actionBaseCurrency.setText(QCoreApplication.translate("JAL_MainWindow", u"&Base Currency", None))
        self.actionCleanAll.setText(QCoreApplication.translate("JAL_MainWindow", u"Clean All", None))
        self.menuMain.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Main", None))
        self.menu_Data.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Data", None))
        self.menu_Export.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Export", None))
        self.menuLanguage.setTitle(QCoreApplication.translate("JAL_MainWindow", u"L&anguage", None))
        self.menuImport.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Import", None))
        self.menuStatement.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Statement", None))
        self.menuReports.setTitle(QCoreApplication.translate("JAL_MainWindow", u"&Reports", None))
    # retranslateUi

