# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'staking_report.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDateEdit,
    QFrame, QGridLayout, QHeaderView, QPushButton,
    QSizePolicy, QSpacerItem, QSplitter, QTableView,
    QVBoxLayout, QWidget)

from jal.widgets.account_select import CurrencyComboBox
from jal.widgets.custom.tableview_with_footer import TableViewWithFooter

class Ui_StakingReportWidget(object):
    def setupUi(self, StakingReportWidget):
        if not StakingReportWidget.objectName():
            StakingReportWidget.setObjectName(u"StakingReportWidget")
        StakingReportWidget.resize(900, 500)
        self.verticalLayout = QVBoxLayout(StakingReportWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(StakingReportWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.ReportDate = QDateEdit(self.ReportParamsFrame)
        self.ReportDate.setObjectName(u"ReportDate")
        self.ReportDate.setCalendarPopup(True)
        self.ReportDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.ReportDate, 0, 0, 1, 1)

        self.ReportCurrencyCombo = CurrencyComboBox(self.ReportParamsFrame)
        self.ReportCurrencyCombo.setObjectName(u"ReportCurrencyCombo")

        self.gridLayout.addWidget(self.ReportCurrencyCombo, 0, 1, 1, 1)

        self.ClosedCheck = QCheckBox(self.ReportParamsFrame)
        self.ClosedCheck.setObjectName(u"ClosedCheck")

        self.gridLayout.addWidget(self.ClosedCheck, 0, 2, 1, 1)

        self.CloseButton = QPushButton(self.ReportParamsFrame)
        self.CloseButton.setObjectName(u"CloseButton")

        self.gridLayout.addWidget(self.CloseButton, 0, 3, 1, 1)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 4, 1, 1)

        self.SaveButton = QPushButton(self.ReportParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.gridLayout.addWidget(self.SaveButton, 0, 5, 1, 1)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.splitter = QSplitter(StakingReportWidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Vertical)
        self.ReportTableView = TableViewWithFooter(self.splitter)
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
        self.ReportTableView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ReportTableView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ReportTableView.setGridStyle(Qt.DotLine)
        self.ReportTableView.setWordWrap(False)
        self.splitter.addWidget(self.ReportTableView)
        self.ReportTableView.verticalHeader().setVisible(False)
        self.ReportTableView.verticalHeader().setMinimumSectionSize(20)
        self.DetailsTableView = QTableView(self.splitter)
        self.DetailsTableView.setObjectName(u"DetailsTableView")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(3)
        sizePolicy1.setHeightForWidth(self.DetailsTableView.sizePolicy().hasHeightForWidth())
        self.DetailsTableView.setSizePolicy(sizePolicy1)
        self.DetailsTableView.setFrameShape(QFrame.Panel)
        self.DetailsTableView.setFrameShadow(QFrame.Sunken)
        self.DetailsTableView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.DetailsTableView.setAlternatingRowColors(True)
        self.DetailsTableView.setGridStyle(Qt.DotLine)
        self.DetailsTableView.setWordWrap(False)
        self.splitter.addWidget(self.DetailsTableView)
        self.DetailsTableView.verticalHeader().setVisible(False)
        self.DetailsTableView.verticalHeader().setMinimumSectionSize(20)

        self.verticalLayout.addWidget(self.splitter)


        self.retranslateUi(StakingReportWidget)

        QMetaObject.connectSlotsByName(StakingReportWidget)
    # setupUi

    def retranslateUi(self, StakingReportWidget):
        StakingReportWidget.setWindowTitle(QCoreApplication.translate("StakingReportWidget", u"Staked positions", None))
        self.ReportDate.setDisplayFormat(QCoreApplication.translate("StakingReportWidget", u"dd/MM/yyyy", None))
#if QT_CONFIG(tooltip)
        self.ClosedCheck.setToolTip(QCoreApplication.translate("StakingReportWidget", u"Also show positions that were emptied and closed", None))
#endif // QT_CONFIG(tooltip)
        self.ClosedCheck.setText(QCoreApplication.translate("StakingReportWidget", u"Show closed", None))
#if QT_CONFIG(tooltip)
        self.CloseButton.setToolTip(QCoreApplication.translate("StakingReportWidget", u"Close the selected position once it holds nothing", None))
#endif // QT_CONFIG(tooltip)
        self.CloseButton.setText(QCoreApplication.translate("StakingReportWidget", u"Close...", None))
        self.SaveButton.setText(QCoreApplication.translate("StakingReportWidget", u"Save...", None))
    # retranslateUi

