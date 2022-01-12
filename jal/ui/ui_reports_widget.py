# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'reports_widget.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateEdit,
    QFrame, QGridLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QTableView,
    QTreeView, QVBoxLayout, QWidget, QAbstractItemView)

from jal.widgets.account_select import AccountButton
from jal.widgets.reference_selector import CategorySelector

class Ui_ReportsWidget(object):
    def setupUi(self, ReportsWidget):
        if not ReportsWidget.objectName():
            ReportsWidget.setObjectName(u"ReportsWidget")
        ReportsWidget.resize(928, 423)
        self.verticalLayout = QVBoxLayout(ReportsWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(ReportsWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 10, 1, 1)

        self.ReportAccountBtn = AccountButton(self.ReportParamsFrame)
        self.ReportAccountBtn.setObjectName(u"ReportAccountBtn")

        self.gridLayout.addWidget(self.ReportAccountBtn, 1, 2, 1, 1)

        self.ReportCategoryEdit = CategorySelector(self.ReportParamsFrame)
        self.ReportCategoryEdit.setObjectName(u"ReportCategoryEdit")

        self.gridLayout.addWidget(self.ReportCategoryEdit, 0, 9, 1, 1)

        self.ReportTypeLbl = QLabel(self.ReportParamsFrame)
        self.ReportTypeLbl.setObjectName(u"ReportTypeLbl")

        self.gridLayout.addWidget(self.ReportTypeLbl, 0, 0, 1, 1)

        self.ReportToDate = QDateEdit(self.ReportParamsFrame)
        self.ReportToDate.setObjectName(u"ReportToDate")
        self.ReportToDate.setDateTime(QDateTime(QDate(2020, 11, 23), QTime(21, 0, 0)))
        self.ReportToDate.setCalendarPopup(True)
        self.ReportToDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.ReportToDate, 1, 5, 1, 1)

        self.ReportAccountLbl = QLabel(self.ReportParamsFrame)
        self.ReportAccountLbl.setObjectName(u"ReportAccountLbl")

        self.gridLayout.addWidget(self.ReportAccountLbl, 1, 0, 1, 1)

        self.line_2 = QFrame(self.ReportParamsFrame)
        self.line_2.setObjectName(u"line_2")
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.line_2.sizePolicy().hasHeightForWidth())
        self.line_2.setSizePolicy(sizePolicy)
        self.line_2.setFrameShadow(QFrame.Sunken)
        self.line_2.setFrameShape(QFrame.VLine)

        self.gridLayout.addWidget(self.line_2, 0, 3, 2, 1)

        self.ReportToLbl = QLabel(self.ReportParamsFrame)
        self.ReportToLbl.setObjectName(u"ReportToLbl")
        self.ReportToLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout.addWidget(self.ReportToLbl, 1, 4, 1, 1)

        self.ReportFromLbl = QLabel(self.ReportParamsFrame)
        self.ReportFromLbl.setObjectName(u"ReportFromLbl")
        self.ReportFromLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout.addWidget(self.ReportFromLbl, 0, 4, 1, 1)

        self.ReportGroupCheck = QCheckBox(self.ReportParamsFrame)
        self.ReportGroupCheck.setObjectName(u"ReportGroupCheck")

        self.gridLayout.addWidget(self.ReportGroupCheck, 1, 6, 1, 1)

        self.ReportTypeCombo = QComboBox(self.ReportParamsFrame)
        self.ReportTypeCombo.addItem("")
        self.ReportTypeCombo.addItem("")
        self.ReportTypeCombo.addItem("")
        self.ReportTypeCombo.addItem("")
        self.ReportTypeCombo.setObjectName(u"ReportTypeCombo")

        self.gridLayout.addWidget(self.ReportTypeCombo, 0, 2, 1, 1)

        self.SaveReportBtn = QPushButton(self.ReportParamsFrame)
        self.SaveReportBtn.setObjectName(u"SaveReportBtn")

        self.gridLayout.addWidget(self.SaveReportBtn, 1, 11, 1, 1)

        self.RunReportBtn = QPushButton(self.ReportParamsFrame)
        self.RunReportBtn.setObjectName(u"RunReportBtn")

        self.gridLayout.addWidget(self.RunReportBtn, 0, 11, 1, 1)

        self.ReportCategoryLbl = QLabel(self.ReportParamsFrame)
        self.ReportCategoryLbl.setObjectName(u"ReportCategoryLbl")

        self.gridLayout.addWidget(self.ReportCategoryLbl, 0, 8, 1, 1)

        self.ReportRangeCombo = QComboBox(self.ReportParamsFrame)
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.addItem("")
        self.ReportRangeCombo.setObjectName(u"ReportRangeCombo")

        self.gridLayout.addWidget(self.ReportRangeCombo, 0, 6, 1, 1)

        self.ReportFromDate = QDateEdit(self.ReportParamsFrame)
        self.ReportFromDate.setObjectName(u"ReportFromDate")
        self.ReportFromDate.setDateTime(QDateTime(QDate(2020, 11, 23), QTime(21, 0, 0)))
        self.ReportFromDate.setCalendarPopup(True)
        self.ReportFromDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.ReportFromDate, 0, 5, 1, 1)

        self.line_3 = QFrame(self.ReportParamsFrame)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.VLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.gridLayout.addWidget(self.line_3, 0, 7, 2, 1)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTableView = QTableView(ReportsWidget)
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

        self.ReportTreeView = QTreeView(ReportsWidget)
        self.ReportTreeView.setObjectName(u"ReportTreeView")
        self.ReportTreeView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ReportTreeView.setAlternatingRowColors(True)
        self.ReportTreeView.header().setStretchLastSection(False)

        self.verticalLayout.addWidget(self.ReportTreeView)


        self.retranslateUi(ReportsWidget)

        QMetaObject.connectSlotsByName(ReportsWidget)
    # setupUi

    def retranslateUi(self, ReportsWidget):
        ReportsWidget.setWindowTitle(QCoreApplication.translate("ReportsWidget", u"Reports", None))
        self.ReportTypeLbl.setText(QCoreApplication.translate("ReportsWidget", u"Report:", None))
        self.ReportToDate.setDisplayFormat(QCoreApplication.translate("ReportsWidget", u"dd/MM/yyyy", None))
        self.ReportAccountLbl.setText(QCoreApplication.translate("ReportsWidget", u"Account:", None))
        self.ReportToLbl.setText(QCoreApplication.translate("ReportsWidget", u"To:", None))
        self.ReportFromLbl.setText(QCoreApplication.translate("ReportsWidget", u"From:", None))
        self.ReportGroupCheck.setText(QCoreApplication.translate("ReportsWidget", u"Group dates", None))
        self.ReportTypeCombo.setItemText(0, QCoreApplication.translate("ReportsWidget", u"Income / Spending", None))
        self.ReportTypeCombo.setItemText(1, QCoreApplication.translate("ReportsWidget", u"Profit / Loss", None))
        self.ReportTypeCombo.setItemText(2, QCoreApplication.translate("ReportsWidget", u"Deals", None))
        self.ReportTypeCombo.setItemText(3, QCoreApplication.translate("ReportsWidget", u"By Category", None))

        self.SaveReportBtn.setText(QCoreApplication.translate("ReportsWidget", u"Save", None))
        self.RunReportBtn.setText(QCoreApplication.translate("ReportsWidget", u"Run", None))
        self.ReportCategoryLbl.setText(QCoreApplication.translate("ReportsWidget", u"Category:", None))
        self.ReportRangeCombo.setItemText(0, QCoreApplication.translate("ReportsWidget", u"Custom range", None))
        self.ReportRangeCombo.setItemText(1, QCoreApplication.translate("ReportsWidget", u"Quarter to date", None))
        self.ReportRangeCombo.setItemText(2, QCoreApplication.translate("ReportsWidget", u"Year to date", None))
        self.ReportRangeCombo.setItemText(3, QCoreApplication.translate("ReportsWidget", u"This year", None))
        self.ReportRangeCombo.setItemText(4, QCoreApplication.translate("ReportsWidget", u"Previous year", None))

        self.ReportFromDate.setDisplayFormat(QCoreApplication.translate("ReportsWidget", u"dd/MM/yyyy", None))
    # retranslateUi

