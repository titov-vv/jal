# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'assets_payments_report.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QGridLayout,
    QHeaderView, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)

from jal.widgets.account_select import AccountButton
from jal.widgets.custom.date_range_selector import DateRangeSelector
from jal.widgets.custom.tableview_with_footer import TableViewWithFooter

class Ui_AssetsPaymentsReportWidget(object):
    def setupUi(self, AssetsPaymentsReportWidget):
        if not AssetsPaymentsReportWidget.objectName():
            AssetsPaymentsReportWidget.setObjectName(u"AssetsPaymentsReportWidget")
        AssetsPaymentsReportWidget.resize(769, 338)
        self.verticalLayout = QVBoxLayout(AssetsPaymentsReportWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(AssetsPaymentsReportWidget)
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


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTableView = TableViewWithFooter(AssetsPaymentsReportWidget)
        self.ReportTableView.setObjectName(u"ReportTableView")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(4)
        sizePolicy.setHeightForWidth(self.ReportTableView.sizePolicy().hasHeightForWidth())
        self.ReportTableView.setSizePolicy(sizePolicy)
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


        self.retranslateUi(AssetsPaymentsReportWidget)

        QMetaObject.connectSlotsByName(AssetsPaymentsReportWidget)
    # setupUi

    def retranslateUi(self, AssetsPaymentsReportWidget):
        AssetsPaymentsReportWidget.setWindowTitle(QCoreApplication.translate("AssetsPaymentsReportWidget", u"Assets' payments report for account", None))
        self.ReportAccountLbl.setText(QCoreApplication.translate("AssetsPaymentsReportWidget", u"Account:", None))
        self.ReportAccountButton.setText("")
        self.SaveButton.setText(QCoreApplication.translate("AssetsPaymentsReportWidget", u"Save...", None))
    # retranslateUi

