# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'deals_report.ui'
##
## Created by: Qt User Interface Compiler version 6.2.4
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QSizePolicy,
    QSpacerItem, QTableView, QVBoxLayout, QWidget)

from jal.widgets.account_select import AccountButton
from jal.widgets.date_range_selector import DateRangeSelector

class Ui_DealsReportWidget(object):
    def setupUi(self, DealsReportWidget):
        if not DealsReportWidget.objectName():
            DealsReportWidget.setObjectName(u"DealsReportWidget")
        DealsReportWidget.resize(821, 280)
        self.verticalLayout = QVBoxLayout(DealsReportWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(DealsReportWidget)
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

        self.ReportGroupCheck = QCheckBox(self.ReportParamsFrame)
        self.ReportGroupCheck.setObjectName(u"ReportGroupCheck")

        self.horizontalLayout.addWidget(self.ReportGroupCheck)

        self.ReportAccountLbl = QLabel(self.ReportParamsFrame)
        self.ReportAccountLbl.setObjectName(u"ReportAccountLbl")

        self.horizontalLayout.addWidget(self.ReportAccountLbl)

        self.ReportAccountBtn = AccountButton(self.ReportParamsFrame)
        self.ReportAccountBtn.setObjectName(u"ReportAccountBtn")

        self.horizontalLayout.addWidget(self.ReportAccountBtn)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.ReportFrameSpacer)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTableView = QTableView(DealsReportWidget)
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


        self.retranslateUi(DealsReportWidget)

        QMetaObject.connectSlotsByName(DealsReportWidget)
    # setupUi

    def retranslateUi(self, DealsReportWidget):
        DealsReportWidget.setWindowTitle(QCoreApplication.translate("DealsReportWidget", u"Deals", None))
        self.ReportGroupCheck.setText(QCoreApplication.translate("DealsReportWidget", u"Group dates", None))
        self.ReportAccountLbl.setText(QCoreApplication.translate("DealsReportWidget", u"Account:", None))
    # retranslateUi

