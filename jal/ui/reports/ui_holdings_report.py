# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'holdings_report.ui'
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
from PySide6.QtWidgets import (QApplication, QDateEdit, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QSizePolicy, QSpacerItem,
    QTreeView, QVBoxLayout, QWidget)

from jal.widgets.account_select import CurrencyComboBox

class Ui_HoldingsWidget(object):
    def setupUi(self, HoldingsWidget):
        if not HoldingsWidget.objectName():
            HoldingsWidget.setObjectName(u"HoldingsWidget")
        HoldingsWidget.resize(1066, 589)
        self.verticalLayout = QVBoxLayout(HoldingsWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.HoldingsParamsFrame = QFrame(HoldingsWidget)
        self.HoldingsParamsFrame.setObjectName(u"HoldingsParamsFrame")
        self.HoldingsParamsFrame.setFrameShape(QFrame.Panel)
        self.HoldingsParamsFrame.setFrameShadow(QFrame.Sunken)
        self.horizontalLayout_8 = QHBoxLayout(self.HoldingsParamsFrame)
        self.horizontalLayout_8.setSpacing(6)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(2, 2, 2, 2)
        self.HoldingsDate = QDateEdit(self.HoldingsParamsFrame)
        self.HoldingsDate.setObjectName(u"HoldingsDate")
        self.HoldingsDate.setDateTime(QDateTime(QDate(2020, 11, 24), QTime(21, 0, 0)))
        self.HoldingsDate.setCalendarPopup(True)
        self.HoldingsDate.setTimeSpec(Qt.UTC)

        self.horizontalLayout_8.addWidget(self.HoldingsDate)

        self.HoldingsCurrencyLbl = QLabel(self.HoldingsParamsFrame)
        self.HoldingsCurrencyLbl.setObjectName(u"HoldingsCurrencyLbl")

        self.horizontalLayout_8.addWidget(self.HoldingsCurrencyLbl)

        self.HoldingsCurrencyCombo = CurrencyComboBox(self.HoldingsParamsFrame)
        self.HoldingsCurrencyCombo.setObjectName(u"HoldingsCurrencyCombo")

        self.horizontalLayout_8.addWidget(self.HoldingsCurrencyCombo)

        self.horizontalSpacer = QSpacerItem(1411, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer)


        self.verticalLayout.addWidget(self.HoldingsParamsFrame)

        self.HoldingsTableView = QTreeView(HoldingsWidget)
        self.HoldingsTableView.setObjectName(u"HoldingsTableView")
        self.HoldingsTableView.setFrameShape(QFrame.Panel)
        self.HoldingsTableView.setAlternatingRowColors(True)
        self.HoldingsTableView.setAnimated(True)
        self.HoldingsTableView.setAllColumnsShowFocus(True)

        self.verticalLayout.addWidget(self.HoldingsTableView)


        self.retranslateUi(HoldingsWidget)

        QMetaObject.connectSlotsByName(HoldingsWidget)
    # setupUi

    def retranslateUi(self, HoldingsWidget):
        HoldingsWidget.setWindowTitle(QCoreApplication.translate("HoldingsWidget", u"Holdings", None))
        self.HoldingsDate.setDisplayFormat(QCoreApplication.translate("HoldingsWidget", u"dd/MM/yyyy", None))
        self.HoldingsCurrencyLbl.setText(QCoreApplication.translate("HoldingsWidget", u"Common currency:", None))
    # retranslateUi

