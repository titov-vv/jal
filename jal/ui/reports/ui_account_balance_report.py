# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'account_balance_report.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

from jal.widgets.account_select import AccountButton
from jal.widgets.custom.date_range_selector import DateRangeSelector

class Ui_AccountBalanceHistoryReportWidget(object):
    def setupUi(self, AccountBalanceHistoryReportWidget):
        if not AccountBalanceHistoryReportWidget.objectName():
            AccountBalanceHistoryReportWidget.setObjectName(u"AccountBalanceHistoryReportWidget")
        AccountBalanceHistoryReportWidget.resize(769, 345)
        self.reportLayout = QVBoxLayout(AccountBalanceHistoryReportWidget)
        self.reportLayout.setSpacing(0)
        self.reportLayout.setObjectName(u"reportLayout")
        self.reportLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(AccountBalanceHistoryReportWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.ReportRange = DateRangeSelector(self.ReportParamsFrame)
        self.ReportRange.setObjectName(u"ReportRange")
        self.ReportRange.setProperty(u"ItemsList", u"QTD;YTD;this_year;last_year")

        self.gridLayout.addWidget(self.ReportRange, 0, 0, 1, 1)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 3, 1, 1)

        self.ReportAccountLbl = QLabel(self.ReportParamsFrame)
        self.ReportAccountLbl.setObjectName(u"ReportAccountLbl")

        self.gridLayout.addWidget(self.ReportAccountLbl, 0, 1, 1, 1)

        self.ReportAccountButton = AccountButton(self.ReportParamsFrame)
        self.ReportAccountButton.setObjectName(u"ReportAccountButton")

        self.gridLayout.addWidget(self.ReportAccountButton, 0, 2, 1, 1)

        self.SaveButton = QPushButton(self.ReportParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.gridLayout.addWidget(self.SaveButton, 0, 4, 1, 1)


        self.reportLayout.addWidget(self.ReportParamsFrame)


        self.retranslateUi(AccountBalanceHistoryReportWidget)

        QMetaObject.connectSlotsByName(AccountBalanceHistoryReportWidget)
    # setupUi

    def retranslateUi(self, AccountBalanceHistoryReportWidget):
        AccountBalanceHistoryReportWidget.setWindowTitle(QCoreApplication.translate("AccountBalanceHistoryReportWidget", u"Account balance history chart", None))
        self.ReportAccountLbl.setText(QCoreApplication.translate("AccountBalanceHistoryReportWidget", u"Account:", None))
        self.ReportAccountButton.setText("")
        self.SaveButton.setText(QCoreApplication.translate("AccountBalanceHistoryReportWidget", u"Save...", None))
    # retranslateUi

