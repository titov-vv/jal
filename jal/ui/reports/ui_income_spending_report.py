# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'income_spending_report.ui'
##
## Created by: Qt User Interface Compiler version 6.3.1
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout,
    QHeaderView, QSizePolicy, QSpacerItem, QTreeView,
    QVBoxLayout, QWidget)

from jal.widgets.date_range_selector import DateRangeSelector

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
        self.ReportRange = DateRangeSelector(self.ReportParamsFrame)
        self.ReportRange.setObjectName(u"ReportRange")
        self.ReportRange.setProperty("ItemsList", u"QTD;YTD;this_year;last_year")

        self.horizontalLayout.addWidget(self.ReportRange)

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
    # retranslateUi

