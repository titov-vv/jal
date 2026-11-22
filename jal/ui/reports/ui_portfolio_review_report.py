# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'portfolio_review_report.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
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
    QHeaderView, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QSplitter, QTableView, QVBoxLayout,
    QWidget)

from jal.widgets.operations_tabs import JalOperationsTabs

class Ui_PortfolioReviewWidget(object):
    def setupUi(self, PortfolioReviewWidget):
        if not PortfolioReviewWidget.objectName():
            PortfolioReviewWidget.setObjectName(u"PortfolioReviewWidget")
        PortfolioReviewWidget.resize(767, 408)
        self.verticalLayout = QVBoxLayout(PortfolioReviewWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.ReportParamsFrame = QFrame(PortfolioReviewWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.horizontalLayout = QHBoxLayout(self.ReportParamsFrame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.SummaryLbl = QLabel(self.ReportParamsFrame)
        self.SummaryLbl.setObjectName(u"SummaryLbl")

        self.horizontalLayout.addWidget(self.SummaryLbl)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.ReportFrameSpacer)

        self.RefreshButton = QPushButton(self.ReportParamsFrame)
        self.RefreshButton.setObjectName(u"RefreshButton")

        self.horizontalLayout.addWidget(self.RefreshButton)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.splitter = QSplitter(PortfolioReviewWidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Vertical)
        self.ReportTableView = QTableView(self.splitter)
        self.ReportTableView.setObjectName(u"ReportTableView")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(4)
        sizePolicy.setHeightForWidth(self.ReportTableView.sizePolicy().hasHeightForWidth())
        self.ReportTableView.setSizePolicy(sizePolicy)
        self.ReportTableView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ReportTableView.setAlternatingRowColors(True)
        self.ReportTableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ReportTableView.setGridStyle(Qt.PenStyle.DotLine)
        self.ReportTableView.setWordWrap(False)
        self.splitter.addWidget(self.ReportTableView)
        self.ReportTableView.verticalHeader().setVisible(False)
        self.ReportTableView.verticalHeader().setMinimumSectionSize(20)
        self.OperationDetails = JalOperationsTabs(self.splitter)
        self.OperationDetails.setObjectName(u"OperationDetails")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(1)
        sizePolicy1.setHeightForWidth(self.OperationDetails.sizePolicy().hasHeightForWidth())
        self.OperationDetails.setSizePolicy(sizePolicy1)
        self.splitter.addWidget(self.OperationDetails)

        self.verticalLayout.addWidget(self.splitter)

        QWidget.setTabOrder(self.RefreshButton, self.ReportTableView)
        QWidget.setTabOrder(self.ReportTableView, self.OperationDetails)

        self.retranslateUi(PortfolioReviewWidget)

        QMetaObject.connectSlotsByName(PortfolioReviewWidget)
    # setupUi

    def retranslateUi(self, PortfolioReviewWidget):
        PortfolioReviewWidget.setWindowTitle(QCoreApplication.translate("PortfolioReviewWidget", u"Portfolio assignments to review", None))
        self.RefreshButton.setText(QCoreApplication.translate("PortfolioReviewWidget", u"&Refresh", None))
    # retranslateUi

