# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'profit_loss_report.ui'
##
## Created by: Qt User Interface Compiler version 6.2.2
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
from PySide6.QtWidgets import (QApplication, QDateEdit, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QSizePolicy, QSpacerItem,
    QTableView, QVBoxLayout, QWidget, QAbstractItemView)

from jal.widgets.account_select import AccountButton
from jal.widgets.helpers import DateRangeCombo

class Ui_ProfitLossReportWidget(object):
    def setupUi(self, ProfitLossReportWidget):
        if not ProfitLossReportWidget.objectName():
            ProfitLossReportWidget.setObjectName(u"ProfitLossReportWidget")
        ProfitLossReportWidget.resize(648, 301)
        self.verticalLayout = QVBoxLayout(ProfitLossReportWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(ProfitLossReportWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.horizontalLayout = QHBoxLayout(self.ReportParamsFrame)
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(2, 2, 2, 2)
        self.ReportRangeCombo = DateRangeCombo(self.ReportParamsFrame)
        self.ReportRangeCombo.setObjectName(u"ReportRangeCombo")

        self.horizontalLayout.addWidget(self.ReportRangeCombo)

        self.ReportFromLbl = QLabel(self.ReportParamsFrame)
        self.ReportFromLbl.setObjectName(u"ReportFromLbl")
        self.ReportFromLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout.addWidget(self.ReportFromLbl)

        self.ReportFromDate = QDateEdit(self.ReportParamsFrame)
        self.ReportFromDate.setObjectName(u"ReportFromDate")
        self.ReportFromDate.setDateTime(QDateTime(QDate(2020, 11, 19), QTime(21, 0, 0)))
        self.ReportFromDate.setCalendarPopup(True)
        self.ReportFromDate.setTimeSpec(Qt.UTC)

        self.horizontalLayout.addWidget(self.ReportFromDate)

        self.ReportToLbl = QLabel(self.ReportParamsFrame)
        self.ReportToLbl.setObjectName(u"ReportToLbl")
        self.ReportToLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout.addWidget(self.ReportToLbl)

        self.ReportToDate = QDateEdit(self.ReportParamsFrame)
        self.ReportToDate.setObjectName(u"ReportToDate")
        self.ReportToDate.setDateTime(QDateTime(QDate(2020, 11, 19), QTime(21, 0, 0)))
        self.ReportToDate.setCalendarPopup(True)
        self.ReportToDate.setTimeSpec(Qt.UTC)

        self.horizontalLayout.addWidget(self.ReportToDate)

        self.ReportAccountLbl = QLabel(self.ReportParamsFrame)
        self.ReportAccountLbl.setObjectName(u"ReportAccountLbl")

        self.horizontalLayout.addWidget(self.ReportAccountLbl)

        self.ReportAccountBtn = AccountButton(self.ReportParamsFrame)
        self.ReportAccountBtn.setObjectName(u"ReportAccountBtn")

        self.horizontalLayout.addWidget(self.ReportAccountBtn)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.ReportFrameSpacer)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTableView = QTableView(ProfitLossReportWidget)
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

        self.verticalLayout.addWidget(self.ReportTableView)


        self.retranslateUi(ProfitLossReportWidget)

        QMetaObject.connectSlotsByName(ProfitLossReportWidget)
    # setupUi

    def retranslateUi(self, ProfitLossReportWidget):
        ProfitLossReportWidget.setWindowTitle(QCoreApplication.translate("ProfitLossReportWidget", u"P&L", None))
        self.ReportFromLbl.setText(QCoreApplication.translate("ProfitLossReportWidget", u"From:", None))
        self.ReportFromDate.setDisplayFormat(QCoreApplication.translate("ProfitLossReportWidget", u"dd/MM/yyyy", None))
        self.ReportToLbl.setText(QCoreApplication.translate("ProfitLossReportWidget", u"To:", None))
        self.ReportToDate.setDisplayFormat(QCoreApplication.translate("ProfitLossReportWidget", u"dd/MM/yyyy", None))
        self.ReportAccountLbl.setText(QCoreApplication.translate("ProfitLossReportWidget", u"Account:", None))
    # retranslateUi

