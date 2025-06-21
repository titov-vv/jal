# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'peer_report.ui'
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
    QHeaderView, QLabel, QSizePolicy, QSpacerItem,
    QSplitter, QVBoxLayout, QWidget)

from jal.widgets.account_select import CurrencyComboBox
from jal.widgets.custom.date_range_selector import DateRangeSelector
from jal.widgets.custom.tableview_with_footer import TableViewWithFooter
from jal.widgets.operations_tabs import JalOperationsTabs
from jal.widgets.reference_selector import PeerSelector

class Ui_PeerReportWidget(object):
    def setupUi(self, PeerReportWidget):
        if not PeerReportWidget.objectName():
            PeerReportWidget.setObjectName(u"PeerReportWidget")
        PeerReportWidget.resize(767, 345)
        self.verticalLayout = QVBoxLayout(PeerReportWidget)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(PeerReportWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.ReportParamsFrame.sizePolicy().hasHeightForWidth())
        self.ReportParamsFrame.setSizePolicy(sizePolicy)
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.ReportPeerEdit = PeerSelector(self.ReportParamsFrame)
        self.ReportPeerEdit.setObjectName(u"ReportPeerEdit")

        self.gridLayout.addWidget(self.ReportPeerEdit, 0, 2, 1, 1)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 5, 1, 1)

        self.ReportRange = DateRangeSelector(self.ReportParamsFrame)
        self.ReportRange.setObjectName(u"ReportRange")
        self.ReportRange.setProperty(u"ItemsList", u"QTD;YTD;this_year;last_year")

        self.gridLayout.addWidget(self.ReportRange, 0, 0, 1, 1)

        self.ReportPeerLbl = QLabel(self.ReportParamsFrame)
        self.ReportPeerLbl.setObjectName(u"ReportPeerLbl")

        self.gridLayout.addWidget(self.ReportPeerLbl, 0, 1, 1, 1)

        self.TotalCurrencyLbl = QLabel(self.ReportParamsFrame)
        self.TotalCurrencyLbl.setObjectName(u"TotalCurrencyLbl")

        self.gridLayout.addWidget(self.TotalCurrencyLbl, 0, 3, 1, 1)

        self.TotalCurrencyCombo = CurrencyComboBox(self.ReportParamsFrame)
        self.TotalCurrencyCombo.setObjectName(u"TotalCurrencyCombo")

        self.gridLayout.addWidget(self.TotalCurrencyCombo, 0, 4, 1, 1)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.splitter = QSplitter(PeerReportWidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Vertical)
        self.ReportTableView = TableViewWithFooter(self.splitter)
        self.ReportTableView.setObjectName(u"ReportTableView")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(4)
        sizePolicy1.setHeightForWidth(self.ReportTableView.sizePolicy().hasHeightForWidth())
        self.ReportTableView.setSizePolicy(sizePolicy1)
        self.ReportTableView.setFrameShape(QFrame.Panel)
        self.ReportTableView.setFrameShadow(QFrame.Sunken)
        self.ReportTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ReportTableView.setAlternatingRowColors(True)
        self.ReportTableView.setGridStyle(Qt.DotLine)
        self.ReportTableView.setWordWrap(False)
        self.splitter.addWidget(self.ReportTableView)
        self.ReportTableView.verticalHeader().setVisible(False)
        self.ReportTableView.verticalHeader().setMinimumSectionSize(20)
        self.ReportTableView.verticalHeader().setDefaultSectionSize(20)
        self.OperationDetails = JalOperationsTabs(self.splitter)
        self.OperationDetails.setObjectName(u"OperationDetails")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(1)
        sizePolicy2.setHeightForWidth(self.OperationDetails.sizePolicy().hasHeightForWidth())
        self.OperationDetails.setSizePolicy(sizePolicy2)
        self.splitter.addWidget(self.OperationDetails)

        self.verticalLayout.addWidget(self.splitter)


        self.retranslateUi(PeerReportWidget)

        QMetaObject.connectSlotsByName(PeerReportWidget)
    # setupUi

    def retranslateUi(self, PeerReportWidget):
        PeerReportWidget.setWindowTitle(QCoreApplication.translate("PeerReportWidget", u"Report by peer", None))
        self.ReportPeerLbl.setText(QCoreApplication.translate("PeerReportWidget", u"Peer:", None))
        self.TotalCurrencyLbl.setText(QCoreApplication.translate("PeerReportWidget", u"Common currency:", None))
    # retranslateUi

