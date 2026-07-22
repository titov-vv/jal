# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'deposits_report.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDateEdit, QFrame,
    QGridLayout, QHeaderView, QPushButton, QSizePolicy,
    QSpacerItem, QSplitter, QTableView, QVBoxLayout,
    QWidget)

from jal.widgets.custom.tableview_with_footer import TableViewWithFooter

class Ui_DepositsReportWidget(object):
    def setupUi(self, DepositsReportWidget):
        if not DepositsReportWidget.objectName():
            DepositsReportWidget.setObjectName(u"DepositsReportWidget")
        DepositsReportWidget.resize(900, 500)
        self.verticalLayout = QVBoxLayout(DepositsReportWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(DepositsReportWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.DepositsDate = QDateEdit(self.ReportParamsFrame)
        self.DepositsDate.setObjectName(u"DepositsDate")
        self.DepositsDate.setCalendarPopup(True)
        self.DepositsDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.DepositsDate, 0, 0, 1, 1)

        self.NewButton = QPushButton(self.ReportParamsFrame)
        self.NewButton.setObjectName(u"NewButton")

        self.gridLayout.addWidget(self.NewButton, 0, 1, 1, 1)

        self.PutButton = QPushButton(self.ReportParamsFrame)
        self.PutButton.setObjectName(u"PutButton")

        self.gridLayout.addWidget(self.PutButton, 0, 2, 1, 1)

        self.GetButton = QPushButton(self.ReportParamsFrame)
        self.GetButton.setObjectName(u"GetButton")

        self.gridLayout.addWidget(self.GetButton, 0, 3, 1, 1)

        self.InterestButton = QPushButton(self.ReportParamsFrame)
        self.InterestButton.setObjectName(u"InterestButton")

        self.gridLayout.addWidget(self.InterestButton, 0, 4, 1, 1)

        self.CloseButton = QPushButton(self.ReportParamsFrame)
        self.CloseButton.setObjectName(u"CloseButton")

        self.gridLayout.addWidget(self.CloseButton, 0, 5, 1, 1)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 6, 1, 1)

        self.SaveButton = QPushButton(self.ReportParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.gridLayout.addWidget(self.SaveButton, 0, 7, 1, 1)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.splitter = QSplitter(DepositsReportWidget)
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
        self.ReportTableView.verticalHeader().setDefaultSectionSize(20)
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
        self.DetailsTableView.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.splitter)


        self.retranslateUi(DepositsReportWidget)

        QMetaObject.connectSlotsByName(DepositsReportWidget)
    # setupUi

    def retranslateUi(self, DepositsReportWidget):
        DepositsReportWidget.setWindowTitle(QCoreApplication.translate("DepositsReportWidget", u"Deposits", None))
        self.DepositsDate.setDisplayFormat(QCoreApplication.translate("DepositsReportWidget", u"dd/MM/yyyy", None))
#if QT_CONFIG(tooltip)
        self.NewButton.setToolTip(QCoreApplication.translate("DepositsReportWidget", u"Open a new deposit", None))
#endif // QT_CONFIG(tooltip)
        self.NewButton.setText(QCoreApplication.translate("DepositsReportWidget", u"New...", None))
#if QT_CONFIG(tooltip)
        self.PutButton.setToolTip(QCoreApplication.translate("DepositsReportWidget", u"Put money into the selected deposit", None))
#endif // QT_CONFIG(tooltip)
        self.PutButton.setText(QCoreApplication.translate("DepositsReportWidget", u"Put...", None))
#if QT_CONFIG(tooltip)
        self.GetButton.setToolTip(QCoreApplication.translate("DepositsReportWidget", u"Take money out of the selected deposit", None))
#endif // QT_CONFIG(tooltip)
        self.GetButton.setText(QCoreApplication.translate("DepositsReportWidget", u"Get...", None))
#if QT_CONFIG(tooltip)
        self.InterestButton.setToolTip(QCoreApplication.translate("DepositsReportWidget", u"Record interest credited to the selected deposit", None))
#endif // QT_CONFIG(tooltip)
        self.InterestButton.setText(QCoreApplication.translate("DepositsReportWidget", u"Interest...", None))
#if QT_CONFIG(tooltip)
        self.CloseButton.setToolTip(QCoreApplication.translate("DepositsReportWidget", u"Close the selected deposit and return its money", None))
#endif // QT_CONFIG(tooltip)
        self.CloseButton.setText(QCoreApplication.translate("DepositsReportWidget", u"Close...", None))
        self.SaveButton.setText(QCoreApplication.translate("DepositsReportWidget", u"Save...", None))
    # retranslateUi

