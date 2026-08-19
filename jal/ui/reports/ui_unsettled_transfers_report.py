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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDateEdit, QFrame, QGridLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QToolButton, QVBoxLayout, QWidget)

from jal.widgets.account_select import CurrencyComboBox
from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter

class Ui_UnsettledTransfersWidget(object):
    def setupUi(self, UnsettledTransfersWidget):
        if not UnsettledTransfersWidget.objectName():
            UnsettledTransfersWidget.setObjectName(u"UnsettledTransfersWidget")
        UnsettledTransfersWidget.resize(1329, 500)
        self.verticalLayout = QVBoxLayout(UnsettledTransfersWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.ReportParamsFrame = QFrame(UnsettledTransfersWidget)
        self.ReportParamsFrame.setObjectName(u"ReportParamsFrame")
        self.ReportParamsFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.gridLayout = QGridLayout(self.ReportParamsFrame)
        self.gridLayout.setObjectName(u"gridLayout")
        self.ReportDate = QDateEdit(self.ReportParamsFrame)
        self.ReportDate.setObjectName(u"ReportDate")
        self.ReportDate.setCalendarPopup(True)
        self.ReportDate.setTimeSpec(Qt.TimeSpec.UTC)

        self.gridLayout.addWidget(self.ReportDate, 0, 0, 1, 1)

        self.ReportCurrencyLbl = QLabel(self.ReportParamsFrame)
        self.ReportCurrencyLbl.setObjectName(u"ReportCurrencyLbl")

        self.gridLayout.addWidget(self.ReportCurrencyLbl, 0, 2, 1, 1)

        self.ReportCurrencyCombo = CurrencyComboBox(self.ReportParamsFrame)
        self.ReportCurrencyCombo.setObjectName(u"ReportCurrencyCombo")

        self.gridLayout.addWidget(self.ReportCurrencyCombo, 0, 3, 1, 1)

        self.BasisGapsCheck = QCheckBox(self.ReportParamsFrame)
        self.BasisGapsCheck.setObjectName(u"BasisGapsCheck")

        self.gridLayout.addWidget(self.BasisGapsCheck, 0, 4, 1, 1)

        self.UnsolicitedCheck = QCheckBox(self.ReportParamsFrame)
        self.UnsolicitedCheck.setObjectName(u"UnsolicitedCheck")

        self.gridLayout.addWidget(self.UnsolicitedCheck, 0, 5, 1, 1)

        self.FilterLbl = QLabel(self.ReportParamsFrame)
        self.FilterLbl.setObjectName(u"FilterLbl")

        self.gridLayout.addWidget(self.FilterLbl, 0, 7, 1, 1)

        self.FilterEdit = QLineEdit(self.ReportParamsFrame)
        self.FilterEdit.setObjectName(u"FilterEdit")
        self.FilterEdit.setClearButtonEnabled(True)

        self.gridLayout.addWidget(self.FilterEdit, 0, 8, 1, 1)

        self.GroupLbl = QLabel(self.ReportParamsFrame)
        self.GroupLbl.setObjectName(u"GroupLbl")

        self.gridLayout.addWidget(self.GroupLbl, 0, 10, 1, 1)

        self.GroupCombo = QComboBox(self.ReportParamsFrame)
        self.GroupCombo.setObjectName(u"GroupCombo")

        self.gridLayout.addWidget(self.GroupCombo, 0, 11, 1, 1)

        self.ReportFrameSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.ReportFrameSpacer, 0, 12, 1, 1)

        self.SettleButton = QPushButton(self.ReportParamsFrame)
        self.SettleButton.setObjectName(u"SettleButton")

        self.gridLayout.addWidget(self.SettleButton, 0, 13, 1, 1)

        self.AssignButton = QPushButton(self.ReportParamsFrame)
        self.AssignButton.setObjectName(u"AssignButton")

        self.gridLayout.addWidget(self.AssignButton, 0, 14, 1, 1)

        self.MatchButton = QPushButton(self.ReportParamsFrame)
        self.MatchButton.setObjectName(u"MatchButton")

        self.gridLayout.addWidget(self.MatchButton, 0, 15, 1, 1)

        self.SwapButton = QPushButton(self.ReportParamsFrame)
        self.SwapButton.setObjectName(u"SwapButton")

        self.gridLayout.addWidget(self.SwapButton, 0, 16, 1, 1)

        self.BridgeButton = QPushButton(self.ReportParamsFrame)
        self.BridgeButton.setObjectName(u"BridgeButton")

        self.gridLayout.addWidget(self.BridgeButton, 0, 17, 1, 1)

        self.DustButton = QPushButton(self.ReportParamsFrame)
        self.DustButton.setObjectName(u"DustButton")

        self.gridLayout.addWidget(self.DustButton, 0, 18, 1, 1)

        self.SaveButton = QPushButton(self.ReportParamsFrame)
        self.SaveButton.setObjectName(u"SaveButton")

        self.gridLayout.addWidget(self.SaveButton, 0, 19, 1, 1)

        self.LegendButton = QToolButton(self.ReportParamsFrame)
        self.LegendButton.setObjectName(u"LegendButton")
        self.LegendButton.setAutoRaise(True)

        self.gridLayout.addWidget(self.LegendButton, 0, 20, 1, 1)

        self.currencyGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.currencyGroupSpacer, 0, 1, 1, 1)

        self.filterGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.filterGroupSpacer, 0, 6, 1, 1)

        self.groupGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.groupGroupSpacer, 0, 9, 1, 1)


        self.verticalLayout.addWidget(self.ReportParamsFrame)

        self.ReportTreeView = TreeViewWithFooter(UnsettledTransfersWidget)
        self.ReportTreeView.setObjectName(u"ReportTreeView")
        self.ReportTreeView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ReportTreeView.setAlternatingRowColors(True)
        self.ReportTreeView.setRootIsDecorated(False)
        self.ReportTreeView.setAllColumnsShowFocus(True)
        self.ReportTreeView.header().setStretchLastSection(False)

        self.verticalLayout.addWidget(self.ReportTreeView)

#if QT_CONFIG(shortcut)
        self.ReportCurrencyLbl.setBuddy(self.ReportCurrencyCombo)
        self.FilterLbl.setBuddy(self.FilterEdit)
        self.GroupLbl.setBuddy(self.GroupCombo)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.ReportDate, self.ReportCurrencyCombo)
        QWidget.setTabOrder(self.ReportCurrencyCombo, self.BasisGapsCheck)
        QWidget.setTabOrder(self.BasisGapsCheck, self.UnsolicitedCheck)
        QWidget.setTabOrder(self.UnsolicitedCheck, self.FilterEdit)
        QWidget.setTabOrder(self.FilterEdit, self.GroupCombo)
        QWidget.setTabOrder(self.GroupCombo, self.SettleButton)
        QWidget.setTabOrder(self.SettleButton, self.AssignButton)
        QWidget.setTabOrder(self.AssignButton, self.MatchButton)
        QWidget.setTabOrder(self.MatchButton, self.SwapButton)
        QWidget.setTabOrder(self.SwapButton, self.BridgeButton)
        QWidget.setTabOrder(self.BridgeButton, self.DustButton)
        QWidget.setTabOrder(self.DustButton, self.SaveButton)
        QWidget.setTabOrder(self.SaveButton, self.LegendButton)
        QWidget.setTabOrder(self.LegendButton, self.ReportTreeView)

        self.retranslateUi(UnsettledTransfersWidget)

        QMetaObject.connectSlotsByName(UnsettledTransfersWidget)
    # setupUi

    def retranslateUi(self, UnsettledTransfersWidget):
        UnsettledTransfersWidget.setWindowTitle(QCoreApplication.translate("UnsettledTransfersWidget", u"Unsettled transfers", None))
#if QT_CONFIG(tooltip)
        self.ReportDate.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Legs that are still unsettled as of this date", None))
#endif // QT_CONFIG(tooltip)
        self.ReportDate.setDisplayFormat(QCoreApplication.translate("UnsettledTransfersWidget", u"dd/MM/yyyy", None))
        self.ReportCurrencyLbl.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"&Currency:", None))
#if QT_CONFIG(tooltip)
        self.BasisGapsCheck.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Also list settled transfers whose asset arrived with no cost basis", None))
#endif // QT_CONFIG(tooltip)
        self.BasisGapsCheck.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Without cost basis", None))
#if QT_CONFIG(tooltip)
        self.UnsolicitedCheck.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Hide the arrivals nobody sent - poisoning attacks and suspected airdrops, which no settlement will ever pair", None))
#endif // QT_CONFIG(tooltip)
        self.UnsolicitedCheck.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"Hide unsolicited", None))
        self.FilterLbl.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"&Filter:", None))
#if QT_CONFIG(tooltip)
        self.FilterEdit.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"Show only the legs whose asset, account, counterparty, reference or note contains this text", None))
#endif // QT_CONFIG(tooltip)
        self.FilterEdit.setPlaceholderText(QCoreApplication.translate("UnsettledTransfersWidget", u"asset, account, protocol...", None))
        self.GroupLbl.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"&Group by:", None))
#if QT_CONFIG(tooltip)
        self.GroupCombo.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"File the legs under a common heading, with the money in transit totalled for each", None))
#endif // QT_CONFIG(tooltip)
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
#if QT_CONFIG(tooltip)
        self.LegendButton.setToolTip(QCoreApplication.translate("UnsettledTransfersWidget", u"What the row colors mean", None))
#endif // QT_CONFIG(tooltip)
        self.LegendButton.setText(QCoreApplication.translate("UnsettledTransfersWidget", u"?", None))
    # retranslateUi

