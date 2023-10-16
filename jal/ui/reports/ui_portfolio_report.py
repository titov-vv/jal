# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'portfolio_report.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateEdit,
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QTreeView,
    QVBoxLayout, QWidget)

from jal.widgets.account_select import CurrencyComboBox

class Ui_PortfolioWidget(object):
    def setupUi(self, PortfolioWidget):
        if not PortfolioWidget.objectName():
            PortfolioWidget.setObjectName(u"PortfolioWidget")
        PortfolioWidget.resize(1066, 589)
        self.verticalLayout = QVBoxLayout(PortfolioWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.PortfolioParamsFrame = QFrame(PortfolioWidget)
        self.PortfolioParamsFrame.setObjectName(u"PortfolioParamsFrame")
        self.PortfolioParamsFrame.setFrameShape(QFrame.Panel)
        self.PortfolioParamsFrame.setFrameShadow(QFrame.Sunken)
        self.horizontalLayout_8 = QHBoxLayout(self.PortfolioParamsFrame)
        self.horizontalLayout_8.setSpacing(6)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(2, 2, 2, 2)
        self.PortfolioDate = QDateEdit(self.PortfolioParamsFrame)
        self.PortfolioDate.setObjectName(u"PortfolioDate")
        self.PortfolioDate.setDateTime(QDateTime(QDate(2020, 11, 24), QTime(0, 0, 0)))
        self.PortfolioDate.setCalendarPopup(True)
        self.PortfolioDate.setTimeSpec(Qt.UTC)

        self.horizontalLayout_8.addWidget(self.PortfolioDate)

        self.GroupLbl = QLabel(self.PortfolioParamsFrame)
        self.GroupLbl.setObjectName(u"GroupLbl")

        self.horizontalLayout_8.addWidget(self.GroupLbl)

        self.GroupCombo = QComboBox(self.PortfolioParamsFrame)
        self.GroupCombo.setObjectName(u"GroupCombo")

        self.horizontalLayout_8.addWidget(self.GroupCombo)

        self.PortfolioCurrencyLbl = QLabel(self.PortfolioParamsFrame)
        self.PortfolioCurrencyLbl.setObjectName(u"PortfolioCurrencyLbl")

        self.horizontalLayout_8.addWidget(self.PortfolioCurrencyLbl)

        self.PortfolioCurrencyCombo = CurrencyComboBox(self.PortfolioParamsFrame)
        self.PortfolioCurrencyCombo.setObjectName(u"PortfolioCurrencyCombo")

        self.horizontalLayout_8.addWidget(self.PortfolioCurrencyCombo)

        self.ShowInactiveAccounts = QCheckBox(self.PortfolioParamsFrame)
        self.ShowInactiveAccounts.setObjectName(u"ShowInactiveAccounts")

        self.horizontalLayout_8.addWidget(self.ShowInactiveAccounts)

        self.horizontalSpacer = QSpacerItem(1411, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer)

        self.SaveButton = QPushButton(self.PortfolioParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.horizontalLayout_8.addWidget(self.SaveButton)


        self.verticalLayout.addWidget(self.PortfolioParamsFrame)

        self.PortfolioTreeView = QTreeView(PortfolioWidget)
        self.PortfolioTreeView.setObjectName(u"PortfolioTreeView")
        self.PortfolioTreeView.setFrameShape(QFrame.Panel)
        self.PortfolioTreeView.setAlternatingRowColors(True)
        self.PortfolioTreeView.setAnimated(True)
        self.PortfolioTreeView.setAllColumnsShowFocus(True)

        self.verticalLayout.addWidget(self.PortfolioTreeView)


        self.retranslateUi(PortfolioWidget)

        QMetaObject.connectSlotsByName(PortfolioWidget)
    # setupUi

    def retranslateUi(self, PortfolioWidget):
        PortfolioWidget.setWindowTitle(QCoreApplication.translate("PortfolioWidget", u"Asset Portfolio", None))
        self.PortfolioDate.setDisplayFormat(QCoreApplication.translate("PortfolioWidget", u"dd/MM/yyyy", None))
        self.GroupLbl.setText(QCoreApplication.translate("PortfolioWidget", u"Group by:", None))
        self.PortfolioCurrencyLbl.setText(QCoreApplication.translate("PortfolioWidget", u"Common currency:", None))
        self.ShowInactiveAccounts.setText(QCoreApplication.translate("PortfolioWidget", u"Show &Inactive accounts", None))
        self.SaveButton.setText(QCoreApplication.translate("PortfolioWidget", u"Save...", None))
    # retranslateUi

