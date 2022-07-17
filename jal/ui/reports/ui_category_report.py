# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'category_report.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QGridLayout,
    QHeaderView, QLabel, QSizePolicy, QSpacerItem,
    QTableView, QVBoxLayout, QWidget)

from jal.widgets.date_range_selector import DateRangeSelector
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
        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 3, 1, 1)

        self.ReportRange = DateRangeSelector(self.ReportParamsFrame)
        self.ReportRange.setObjectName(u"ReportRange")
        self.ReportRange.setProperty("ItemsList", u"QTD;YTD;this_year;last_year")

        self.gridLayout.addWidget(self.ReportRange, 0, 0, 1, 1)

        self.ReportCategoryLbl = QLabel(self.ReportParamsFrame)
        self.ReportCategoryLbl.setObjectName(u"ReportCategoryLbl")

        self.gridLayout.addWidget(self.ReportCategoryLbl, 0, 1, 1, 1)

        self.ReportCategoryEdit = CategorySelector(self.ReportParamsFrame)
        self.ReportCategoryEdit.setObjectName(u"ReportCategoryEdit")

        self.gridLayout.addWidget(self.ReportCategoryEdit, 0, 2, 1, 1)


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
        self.ReportCategoryLbl.setText(QCoreApplication.translate("CategoryReportWidget", u"Category:", None))
    # retranslateUi

