# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'income_spending_report.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QTreeView, QVBoxLayout,
    QWidget)

from jal.widgets.account_select import CurrencyComboBox
from jal.widgets.custom.date_range_selector import DateRangeSelector

class Ui_IncomeSpendingReportWidget(object):
    def setupUi(self, IncomeSpendingReportWidget):
        if not IncomeSpendingReportWidget.objectName():
            IncomeSpendingReportWidget.setObjectName(u"IncomeSpendingReportWidget")
        IncomeSpendingReportWidget.resize(768, 347)
        self.verticalLayout = QVBoxLayout(IncomeSpendingReportWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.ReportParamsFrame = QFrame(IncomeSpendingReportWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.horizontalLayout = QHBoxLayout(self.ReportParamsFrame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.ReportRange = DateRangeSelector(self.ReportParamsFrame)
        self.ReportRange.setObjectName(u"ReportRange")
        self.ReportRange.setProperty(u"ItemsList", u"QTD;YTD;this_year;last_year")

        self.horizontalLayout.addWidget(self.ReportRange)

        self.periodGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.periodGroupSpacer)

        self.PeriodLbl = QLabel(self.ReportParamsFrame)
        self.PeriodLbl.setObjectName(u"PeriodLbl")

        self.horizontalLayout.addWidget(self.PeriodLbl)

        self.PeriodComboBox = QComboBox(self.ReportParamsFrame)
        self.PeriodComboBox.addItem("")
        self.PeriodComboBox.addItem("")
        self.PeriodComboBox.setObjectName(u"PeriodComboBox")

        self.horizontalLayout.addWidget(self.PeriodComboBox)

        self.currencyGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.currencyGroupSpacer)

        self.CurrencyLbl = QLabel(self.ReportParamsFrame)
        self.CurrencyLbl.setObjectName(u"CurrencyLbl")

        self.horizontalLayout.addWidget(self.CurrencyLbl)

        self.CurrencyCombo = CurrencyComboBox(self.ReportParamsFrame)
        self.CurrencyCombo.setObjectName(u"CurrencyCombo")

        self.horizontalLayout.addWidget(self.CurrencyCombo)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.SaveButton = QPushButton(self.ReportParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.horizontalLayout.addWidget(self.SaveButton)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTreeView = QTreeView(IncomeSpendingReportWidget)
        self.ReportTreeView.setObjectName(u"ReportTreeView")
        self.ReportTreeView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ReportTreeView.setAlternatingRowColors(True)
        self.ReportTreeView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.ReportTreeView.header().setStretchLastSection(False)

        self.verticalLayout.addWidget(self.ReportTreeView)

#if QT_CONFIG(shortcut)
        self.PeriodLbl.setBuddy(self.PeriodComboBox)
        self.CurrencyLbl.setBuddy(self.CurrencyCombo)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.ReportRange, self.PeriodComboBox)
        QWidget.setTabOrder(self.PeriodComboBox, self.CurrencyCombo)
        QWidget.setTabOrder(self.CurrencyCombo, self.SaveButton)
        QWidget.setTabOrder(self.SaveButton, self.ReportTreeView)

        self.retranslateUi(IncomeSpendingReportWidget)

        QMetaObject.connectSlotsByName(IncomeSpendingReportWidget)
    # setupUi

    def retranslateUi(self, IncomeSpendingReportWidget):
        IncomeSpendingReportWidget.setWindowTitle(QCoreApplication.translate("IncomeSpendingReportWidget", u"Income & spending", None))
        self.PeriodLbl.setText(QCoreApplication.translate("IncomeSpendingReportWidget", u"&Periodicity:", None))
        self.PeriodComboBox.setItemText(0, QCoreApplication.translate("IncomeSpendingReportWidget", u"Monthly", None))
        self.PeriodComboBox.setItemText(1, QCoreApplication.translate("IncomeSpendingReportWidget", u"Weekly", None))

        self.CurrencyLbl.setText(QCoreApplication.translate("IncomeSpendingReportWidget", u"&Currency:", None))
        self.SaveButton.setText(QCoreApplication.translate("IncomeSpendingReportWidget", u"Save...", None))
    # retranslateUi

