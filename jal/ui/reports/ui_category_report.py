# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'category_report.ui'
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
from PySide6.QtWidgets import (QApplication, QDateEdit, QFrame, QGridLayout,
    QHeaderView, QLabel, QSizePolicy, QSpacerItem,
    QTableView, QVBoxLayout, QWidget, QAbstractItemView)

from jal.widgets.helpers import DateRangeCombo
from jal.widgets.reference_selector import CategorySelector

class Ui_CategoryReportWidget(object):
    def setupUi(self, CategoryReportWidget):
        if not CategoryReportWidget.objectName():
            CategoryReportWidget.setObjectName(u"CategoryReportWidget")
        CategoryReportWidget.resize(636, 345)
        self.verticalLayout = QVBoxLayout(CategoryReportWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(CategoryReportWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.ReportRangeCombo = DateRangeCombo(self.ReportParamsFrame)
        self.ReportRangeCombo.setObjectName(u"ReportRangeCombo")

        self.gridLayout.addWidget(self.ReportRangeCombo, 0, 0, 1, 1)

        self.ReportToDate = QDateEdit(self.ReportParamsFrame)
        self.ReportToDate.setObjectName(u"ReportToDate")
        self.ReportToDate.setDateTime(QDateTime(QDate(2020, 11, 19), QTime(21, 0, 0)))
        self.ReportToDate.setCalendarPopup(True)
        self.ReportToDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.ReportToDate, 0, 4, 1, 1)

        self.ReportCategoryEdit = CategorySelector(self.ReportParamsFrame)
        self.ReportCategoryEdit.setObjectName(u"ReportCategoryEdit")

        self.gridLayout.addWidget(self.ReportCategoryEdit, 0, 6, 1, 1)

        self.ReportToLbl = QLabel(self.ReportParamsFrame)
        self.ReportToLbl.setObjectName(u"ReportToLbl")
        self.ReportToLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout.addWidget(self.ReportToLbl, 0, 3, 1, 1)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 7, 1, 1)

        self.ReportFromLbl = QLabel(self.ReportParamsFrame)
        self.ReportFromLbl.setObjectName(u"ReportFromLbl")
        self.ReportFromLbl.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout.addWidget(self.ReportFromLbl, 0, 1, 1, 1)

        self.ReportFromDate = QDateEdit(self.ReportParamsFrame)
        self.ReportFromDate.setObjectName(u"ReportFromDate")
        self.ReportFromDate.setDateTime(QDateTime(QDate(2020, 11, 19), QTime(21, 0, 0)))
        self.ReportFromDate.setCalendarPopup(True)
        self.ReportFromDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.ReportFromDate, 0, 2, 1, 1)

        self.ReportCategoryLbl = QLabel(self.ReportParamsFrame)
        self.ReportCategoryLbl.setObjectName(u"ReportCategoryLbl")

        self.gridLayout.addWidget(self.ReportCategoryLbl, 0, 5, 1, 1)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTableView = QTableView(CategoryReportWidget)
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


        self.retranslateUi(CategoryReportWidget)

        QMetaObject.connectSlotsByName(CategoryReportWidget)
    # setupUi

    def retranslateUi(self, CategoryReportWidget):
        CategoryReportWidget.setWindowTitle(QCoreApplication.translate("CategoryReportWidget", u"Report by category", None))
        self.ReportToDate.setDisplayFormat(QCoreApplication.translate("CategoryReportWidget", u"dd/MM/yyyy", None))
        self.ReportToLbl.setText(QCoreApplication.translate("CategoryReportWidget", u"To:", None))
        self.ReportFromLbl.setText(QCoreApplication.translate("CategoryReportWidget", u"From:", None))
        self.ReportFromDate.setDisplayFormat(QCoreApplication.translate("CategoryReportWidget", u"dd/MM/yyyy", None))
        self.ReportCategoryLbl.setText(QCoreApplication.translate("CategoryReportWidget", u"Category:", None))
    # retranslateUi

