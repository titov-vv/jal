# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'income_spending_report.ui'
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
    QTreeView, QVBoxLayout, QWidget, QAbstractItemView)

from jal.widgets.helpers import DateRangeCombo

class Ui_IncomeSpendingReportWidget(object):
    def setupUi(self, IncomeSpendingReportWidget):
        if not IncomeSpendingReportWidget.objectName():
            IncomeSpendingReportWidget.setObjectName(u"IncomeSpendingReportWidget")
        IncomeSpendingReportWidget.resize(595, 347)
        self.verticalLayout = QVBoxLayout(IncomeSpendingReportWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(IncomeSpendingReportWidget)
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
        self.ReportFromDate.setDateTime(QDateTime(QDate(2020, 11, 18), QTime(21, 0, 0)))
        self.ReportFromDate.setCalendarPopup(True)
        self.ReportFromDate.setTimeSpec(Qt.UTC)

        self.horizontalLayout.addWidget(self.ReportFromDate)

        self.ReportToLbl = QLabel(self.ReportParamsFrame)
        self.ReportToLbl.setObjectName(u"ReportToLbl")
        self.ReportToLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout.addWidget(self.ReportToLbl)

        self.ReportToDate = QDateEdit(self.ReportParamsFrame)
        self.ReportToDate.setObjectName(u"ReportToDate")
        self.ReportToDate.setDateTime(QDateTime(QDate(2020, 11, 18), QTime(21, 0, 0)))
        self.ReportToDate.setCalendarPopup(True)
        self.ReportToDate.setTimeSpec(Qt.UTC)

        self.horizontalLayout.addWidget(self.ReportToDate)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTreeView = QTreeView(IncomeSpendingReportWidget)
        self.ReportTreeView.setObjectName(u"ReportTreeView")
        self.ReportTreeView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ReportTreeView.setAlternatingRowColors(True)
        self.ReportTreeView.header().setStretchLastSection(False)

        self.verticalLayout.addWidget(self.ReportTreeView)


        self.retranslateUi(IncomeSpendingReportWidget)

        QMetaObject.connectSlotsByName(IncomeSpendingReportWidget)
    # setupUi

    def retranslateUi(self, IncomeSpendingReportWidget):
        IncomeSpendingReportWidget.setWindowTitle(QCoreApplication.translate("IncomeSpendingReportWidget", u"Income/Spending", None))
        self.ReportFromLbl.setText(QCoreApplication.translate("IncomeSpendingReportWidget", u"From:", None))
        self.ReportFromDate.setDisplayFormat(QCoreApplication.translate("IncomeSpendingReportWidget", u"dd/MM/yyyy", None))
        self.ReportToLbl.setText(QCoreApplication.translate("IncomeSpendingReportWidget", u"To:", None))
        self.ReportToDate.setDisplayFormat(QCoreApplication.translate("IncomeSpendingReportWidget", u"dd/MM/yyyy", None))
    # retranslateUi

