# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'deals_report.ui'
##
## Created by: Qt User Interface Compiler version 6.6.0
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QTreeView, QVBoxLayout,
    QWidget)

from jal.widgets.account_select import AccountButton
from jal.widgets.custom.date_range_selector import DateRangeSelector

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

        self.GroupLbl = QLabel(self.ReportParamsFrame)
        self.GroupLbl.setObjectName(u"GroupLbl")

        self.horizontalLayout.addWidget(self.GroupLbl)

        self.GroupCombo = QComboBox(self.ReportParamsFrame)
        self.GroupCombo.setObjectName(u"GroupCombo")

        self.horizontalLayout.addWidget(self.GroupCombo)

        self.ReportAccountLbl = QLabel(self.ReportParamsFrame)
        self.ReportAccountLbl.setObjectName(u"ReportAccountLbl")

        self.horizontalLayout.addWidget(self.ReportAccountLbl)

        self.ReportAccountBtn = AccountButton(self.ReportParamsFrame)
        self.ReportAccountBtn.setObjectName(u"ReportAccountBtn")

        self.horizontalLayout.addWidget(self.ReportAccountBtn)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.ReportFrameSpacer)

        self.SaveButton = QPushButton(self.ReportParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.horizontalLayout.addWidget(self.SaveButton)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTreeView = QTreeView(DealsReportWidget)
        self.ReportTreeView.setObjectName(u"ReportTreeView")
        self.ReportTreeView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ReportTreeView.setAlternatingRowColors(True)
        self.ReportTreeView.header().setStretchLastSection(False)

        self.verticalLayout.addWidget(self.ReportTreeView)


        self.retranslateUi(DealsReportWidget)

        QMetaObject.connectSlotsByName(DealsReportWidget)
    # setupUi

    def retranslateUi(self, DealsReportWidget):
        DealsReportWidget.setWindowTitle(QCoreApplication.translate("DealsReportWidget", u"Deals", None))
        self.GroupLbl.setText(QCoreApplication.translate("DealsReportWidget", u"Group by:", None))
        self.ReportAccountLbl.setText(QCoreApplication.translate("DealsReportWidget", u"Account:", None))
        self.SaveButton.setText(QCoreApplication.translate("DealsReportWidget", u"Save...", None))
    # retranslateUi

