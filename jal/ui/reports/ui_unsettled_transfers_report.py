# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'unsettled_transfers_report.ui'
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
    QFrame, QGridLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

from jal.widgets.account_select import CurrencyComboBox
from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter

class Ui_UnsettledTransfersWidget(object):
    def setupUi(self, UnsettledTransfersWidget):
        if not UnsettledTransfersWidget.objectName():
            UnsettledTransfersWidget.setObjectName(u"UnsettledTransfersWidget")
        UnsettledTransfersWidget.resize(900, 500)
        self.verticalLayout = QVBoxLayout(UnsettledTransfersWidget)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ReportParamsFrame = QFrame(UnsettledTransfersWidget)
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

        self.ReportCurrencyLbl = QLabel(self.ReportParamsFrame)
        self.ReportCurrencyLbl.setObjectName(u"ReportCurrencyLbl")

        self.gridLayout.addWidget(self.ReportCurrencyLbl, 0, 1, 1, 1)

        self.ReportCurrencyCombo = CurrencyComboBox(self.ReportParamsFrame)
        self.ReportCurrencyCombo.setObjectName(u"ReportCurrencyCombo")

        self.gridLayout.addWidget(self.ReportCurrencyCombo, 0, 2, 1, 1)

        self.BasisGapsCheck = QCheckBox(self.ReportParamsFrame)
        self.BasisGapsCheck.setObjectName(u"BasisGapsCheck")

        self.gridLayout.addWidget(self.BasisGapsCheck, 0, 3, 1, 1)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 4, 1, 1)

        self.SettleButton = QPushButton(self.ReportParamsFrame)
        self.SettleButton.setObjectName(u"SettleButton")

        self.gridLayout.addWidget(self.SettleButton, 0, 5, 1, 1)

        self.AssignButton = QPushButton(self.ReportParamsFrame)
        self.AssignButton.setObjectName(u"AssignButton")

        self.gridLayout.addWidget(self.AssignButton, 0, 6, 1, 1)

        self.MatchButton = QPushButton(self.ReportParamsFrame)
        self.MatchButton.setObjectName(u"MatchButton")

        self.gridLayout.addWidget(self.MatchButton, 0, 7, 1, 1)

        self.SwapButton = QPushButton(self.ReportParamsFrame)
        self.SwapButton.setObjectName(u"SwapButton")

        self.gridLayout.addWidget(self.SwapButton, 0, 8, 1, 1)

        self.BridgeButton = QPushButton(self.ReportParamsFrame)
        self.BridgeButton.setObjectName(u"BridgeButton")

        self.gridLayout.addWidget(self.BridgeButton, 0, 9, 1, 1)

        self.DustButton = QPushButton(self.ReportParamsFrame)
        self.DustButton.setObjectName(u"DustButton")

        self.gridLayout.addWidget(self.DustButton, 0, 10, 1, 1)

        self.SaveButton = QPushButton(self.ReportParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.gridLayout.addWidget(self.SaveButton, 0, 11, 1, 1)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTreeView = TreeViewWithFooter(UnsettledTransfersWidget)
        self.ReportTreeView.setObjectName(u"ReportTreeView")
        self.ReportTreeView.setFrameShape(QFrame.Panel)
        self.ReportTreeView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ReportTreeView.setAlternatingRowColors(True)
        self.ReportTreeView.setAllColumnsShowFocus(True)
        self.ReportTreeView.setRootIsDecorated(False)
        self.ReportTreeView.header().setStretchLastSection(False)

        self.verticalLayout.addWidget(self.ReportTreeView)


        self.retranslateUi(UnsettledTransfersWidget)

        QMetaObject.connectSlotsByName(UnsettledTransfersWidget)
    # setupUi

    def retranslateUi(self, UnsettledTransfersWidget):
        UnsettledTransfersWidget.setWindowTitle(QCoreApplication.translate("UnsettledTransfersWidget", u"Unsettled transfers", None))
#if QT_CONFIG(tooltip)
        self.ReportDate.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Legs that are still unsettled as of this date", None))
#endif // QT_CONFIG(tooltip)
        self.ReportDate.setDisplayFormat(QCoreApplication.translate("UnsettledTransfersWidget", u"dd/MM/yyyy", None))
        self.ReportCurrencyLbl.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Currency:", None))
#if QT_CONFIG(tooltip)
        self.BasisGapsCheck.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Also list settled transfers whose asset arrived with no cost basis", None))
#endif // QT_CONFIG(tooltip)
        self.BasisGapsCheck.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Without cost basis", None))
#if QT_CONFIG(tooltip)
        self.SettleButton.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Settle every leg that its transaction hash or the address it names pairs unambiguously", None))
#endif // QT_CONFIG(tooltip)
        self.SettleButton.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Settle", None))
#if QT_CONFIG(tooltip)
        self.AssignButton.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Name the account at the end a leg doesn't know", None))
#endif // QT_CONFIG(tooltip)
        self.AssignButton.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Assign...", None))
#if QT_CONFIG(tooltip)
        self.MatchButton.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Pair a leg that was sent with the arrival it belongs to", None))
#endif // QT_CONFIG(tooltip)
        self.MatchButton.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Match...", None))
#if QT_CONFIG(tooltip)
        self.SwapButton.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Replace a leg and the one it was exchanged with by the swap they are", None))
#endif // QT_CONFIG(tooltip)
        self.SwapButton.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Swap...", None))
#if QT_CONFIG(tooltip)
        self.BridgeButton.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Replace a leg and the arrival it crossed chains as by the bridge they are", None))
#endif // QT_CONFIG(tooltip)
        self.BridgeButton.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Bridge...", None))
#if QT_CONFIG(tooltip)
        self.DustButton.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Write off a leg nobody sent as the dust attack it is", None))
#endif // QT_CONFIG(tooltip)
        self.DustButton.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Dust", None))
        self.SaveButton.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Save...", None))
    # retranslateUi

