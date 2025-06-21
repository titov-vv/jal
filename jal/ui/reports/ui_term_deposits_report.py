# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'term_deposits_report.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDateEdit, QFrame,
    QGridLayout, QHeaderView, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)

from jal.widgets.custom.tableview_with_footer import TableViewWithFooter

class Ui_TermDepositsReportWidget(object):
    def setupUi(self, TermDepositsReportWidget):
        if not TermDepositsReportWidget.objectName():
            TermDepositsReportWidget.setObjectName(u"TermDepositsReportWidget")
        TermDepositsReportWidget.resize(769, 338)
        self.verticalLayout = QVBoxLayout(TermDepositsReportWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(TermDepositsReportWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Panel)
        self.ReportParamsFrame.setFrameShadow(QFrame.Sunken)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 1, 1, 1)

        self.SaveButton = QPushButton(self.ReportParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.gridLayout.addWidget(self.SaveButton, 0, 2, 1, 1)

        self.DepositsDate = QDateEdit(self.ReportParamsFrame)
        self.DepositsDate.setObjectName(u"DepositsDate")
        self.DepositsDate.setDateTime(QDateTime(QDate(2020, 11, 24), QTime(0, 0, 0)))
        self.DepositsDate.setCalendarPopup(True)
        self.DepositsDate.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.DepositsDate, 0, 0, 1, 1)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTableView = TableViewWithFooter(TermDepositsReportWidget)
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


        self.retranslateUi(TermDepositsReportWidget)

        QMetaObject.connectSlotsByName(TermDepositsReportWidget)
    # setupUi

    def retranslateUi(self, TermDepositsReportWidget):
        TermDepositsReportWidget.setWindowTitle(QCoreApplication.translate("TermDepositsReportWidget", u"Term deposits report", None))
        self.SaveButton.setText(QCoreApplication.translate("TermDepositsReportWidget", u"Save...", None))
        self.DepositsDate.setDisplayFormat(QCoreApplication.translate("TermDepositsReportWidget", u"dd/MM/yyyy", None))
    # retranslateUi

