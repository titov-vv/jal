# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'operations_widget.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
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
    QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QSplitter, QTableView, QTreeView, QVBoxLayout,
    QWidget)

from jal.widgets.account_select import CurrencyComboBox
from jal.widgets.custom.date_range_selector import DateRangeSelector
from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter
from jal.widgets.operations_tabs import JalOperationsTabs

class Ui_OperationsWidget(object):
    def setupUi(self, OperationsWidget):
        if not OperationsWidget.objectName():
            OperationsWidget.setObjectName(u"OperationsWidget")
        OperationsWidget.resize(1232, 552)
        self.verticalLayout_4 = QVBoxLayout(OperationsWidget)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.BalanceOperationsSplitter = QSplitter(OperationsWidget)
        self.BalanceOperationsSplitter.setObjectName(u"BalanceOperationsSplitter")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.BalanceOperationsSplitter.sizePolicy().hasHeightForWidth())
        self.BalanceOperationsSplitter.setSizePolicy(sizePolicy)
        self.BalanceOperationsSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.BalanceBox = QGroupBox(self.BalanceOperationsSplitter)
        self.BalanceBox.setObjectName(u"BalanceBox")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(1)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.BalanceBox.sizePolicy().hasHeightForWidth())
        self.BalanceBox.setSizePolicy(sizePolicy1)
        self.verticalLayout = QVBoxLayout(self.BalanceBox)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.BalanceFrameTop = QWidget(self.BalanceBox)
        self.BalanceFrameTop.setObjectName(u"BalanceFrameTop")
        self.horizontalLayout_2 = QHBoxLayout(self.BalanceFrameTop)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(6, 6, 6, 6)
        self.BalanceDate = QDateEdit(self.BalanceFrameTop)
        self.BalanceDate.setObjectName(u"BalanceDate")
        self.BalanceDate.setDateTime(QDateTime(QDate(2020, 11, 19), QTime(0, 0, 0)))
        self.BalanceDate.setCalendarPopup(True)
        self.BalanceDate.setTimeSpec(Qt.TimeSpec.UTC)

        self.horizontalLayout_2.addWidget(self.BalanceDate)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)

        self.BalancesCurrencyCombo = CurrencyComboBox(self.BalanceFrameTop)
        self.BalancesCurrencyCombo.setObjectName(u"BalancesCurrencyCombo")

        self.horizontalLayout_2.addWidget(self.BalancesCurrencyCombo)


        self.verticalLayout.addWidget(self.BalanceFrameTop)

        self.BalancesTreeView = TreeViewWithFooter(self.BalanceBox)
        self.BalancesTreeView.setObjectName(u"BalancesTreeView")

        self.verticalLayout.addWidget(self.BalancesTreeView)

        self.BalanceOperationsSplitter.addWidget(self.BalanceBox)
        self.OperationsBox = QGroupBox(self.BalanceOperationsSplitter)
        self.OperationsBox.setObjectName(u"OperationsBox")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(4)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.OperationsBox.sizePolicy().hasHeightForWidth())
        self.OperationsBox.setSizePolicy(sizePolicy2)
        self.OperationsBox.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.verticalLayout_2 = QVBoxLayout(self.OperationsBox)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.OperationsDetailsSplitter = QSplitter(self.OperationsBox)
        self.OperationsDetailsSplitter.setObjectName(u"OperationsDetailsSplitter")
        self.OperationsDetailsSplitter.setOrientation(Qt.Orientation.Vertical)
        self.PositionsOperationsSplitter = QSplitter(self.OperationsDetailsSplitter)
        self.PositionsOperationsSplitter.setObjectName(u"PositionsOperationsSplitter")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(4)
        sizePolicy3.setHeightForWidth(self.PositionsOperationsSplitter.sizePolicy().hasHeightForWidth())
        self.PositionsOperationsSplitter.setSizePolicy(sizePolicy3)
        self.PositionsOperationsSplitter.setOrientation(Qt.Orientation.Vertical)
        self.PositionsOperationsSplitter.setChildrenCollapsible(False)
        self.PositionsPane = QWidget(self.PositionsOperationsSplitter)
        self.PositionsPane.setObjectName(u"PositionsPane")
        self.PositionsPane.setVisible(False)
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(1)
        sizePolicy4.setHeightForWidth(self.PositionsPane.sizePolicy().hasHeightForWidth())
        self.PositionsPane.setSizePolicy(sizePolicy4)
        self.positionsPaneLayout = QHBoxLayout(self.PositionsPane)
        self.positionsPaneLayout.setObjectName(u"positionsPaneLayout")
        self.positionsPaneLayout.setContentsMargins(0, 0, 10, 0)
        self.PositionsTreeView = QTreeView(self.PositionsPane)
        self.PositionsTreeView.setObjectName(u"PositionsTreeView")
        self.PositionsTreeView.setAlternatingRowColors(True)
        self.PositionsTreeView.setAllColumnsShowFocus(True)

        self.positionsPaneLayout.addWidget(self.PositionsTreeView)

        self.PositionsButtons = QFrame(self.PositionsPane)
        self.PositionsButtons.setObjectName(u"PositionsButtons")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.PositionsButtons.sizePolicy().hasHeightForWidth())
        self.PositionsButtons.setSizePolicy(sizePolicy5)
        self.positionsButtonsLayout = QVBoxLayout(self.PositionsButtons)
        self.positionsButtonsLayout.setObjectName(u"positionsButtonsLayout")
        self.PositionsCollapseBtn = QPushButton(self.PositionsButtons)
        self.PositionsCollapseBtn.setObjectName(u"PositionsCollapseBtn")
        self.PositionsCollapseBtn.setMinimumSize(QSize(46, 0))

        self.positionsButtonsLayout.addWidget(self.PositionsCollapseBtn)

        self.positionsButtonsSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.positionsButtonsLayout.addItem(self.positionsButtonsSpacer)


        self.positionsPaneLayout.addWidget(self.PositionsButtons)

        self.PositionsOperationsSplitter.addWidget(self.PositionsPane)
        self.OperationsPane = QWidget(self.PositionsOperationsSplitter)
        self.OperationsPane.setObjectName(u"OperationsPane")
        sizePolicy6 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(2)
        sizePolicy6.setHeightForWidth(self.OperationsPane.sizePolicy().hasHeightForWidth())
        self.OperationsPane.setSizePolicy(sizePolicy6)
        self.operationsPaneLayout = QHBoxLayout(self.OperationsPane)
        self.operationsPaneLayout.setObjectName(u"operationsPaneLayout")
        self.operationsPaneLayout.setContentsMargins(0, 0, 10, 0)
        self.operationsListLayout = QVBoxLayout()
        self.operationsListLayout.setObjectName(u"operationsListLayout")
        self.OperationConfigFrame = QWidget(self.OperationsPane)
        self.OperationConfigFrame.setObjectName(u"OperationConfigFrame")
        self.OperationConfigFrame.setEnabled(True)
        self.horizontalLayout_3 = QHBoxLayout(self.OperationConfigFrame)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 6, 0, 6)
        self.DateRange = DateRangeSelector(self.OperationConfigFrame)
        self.DateRange.setObjectName(u"DateRange")
        self.DateRange.setProperty(u"ItemsList", u"week;month;quarter;year;all")

        self.horizontalLayout_3.addWidget(self.DateRange)

        self.searchGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.searchGroupSpacer)

        self.SearchLbl = QLabel(self.OperationConfigFrame)
        self.SearchLbl.setObjectName(u"SearchLbl")

        self.horizontalLayout_3.addWidget(self.SearchLbl)

        self.SearchString = QLineEdit(self.OperationConfigFrame)
        self.SearchString.setObjectName(u"SearchString")

        self.horizontalLayout_3.addWidget(self.SearchString)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)

        self.ResetAccountBtn = QPushButton(self.OperationConfigFrame)
        self.ResetAccountBtn.setObjectName(u"ResetAccountBtn")
        self.ResetAccountBtn.setVisible(False)

        self.horizontalLayout_3.addWidget(self.ResetAccountBtn)


        self.operationsListLayout.addWidget(self.OperationConfigFrame)

        self.OperationsTableView = QTableView(self.OperationsPane)
        self.OperationsTableView.setObjectName(u"OperationsTableView")
        sizePolicy7 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy7.setHorizontalStretch(0)
        sizePolicy7.setVerticalStretch(0)
        sizePolicy7.setHeightForWidth(self.OperationsTableView.sizePolicy().hasHeightForWidth())
        self.OperationsTableView.setSizePolicy(sizePolicy7)
        self.OperationsTableView.setAlternatingRowColors(True)
        self.OperationsTableView.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.OperationsTableView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.OperationsTableView.setWordWrap(False)
        self.OperationsTableView.verticalHeader().setVisible(False)
        self.OperationsTableView.verticalHeader().setMinimumSectionSize(20)

        self.operationsListLayout.addWidget(self.OperationsTableView)


        self.operationsPaneLayout.addLayout(self.operationsListLayout)

        self.OperationsPaneButtons = QFrame(self.OperationsPane)
        self.OperationsPaneButtons.setObjectName(u"OperationsPaneButtons")
        sizePolicy5.setHeightForWidth(self.OperationsPaneButtons.sizePolicy().hasHeightForWidth())
        self.OperationsPaneButtons.setSizePolicy(sizePolicy5)
        self.operationsPaneButtonsLayout = QVBoxLayout(self.OperationsPaneButtons)
        self.operationsPaneButtonsLayout.setObjectName(u"operationsPaneButtonsLayout")
        self.OperationsCollapseBtn = QPushButton(self.OperationsPaneButtons)
        self.OperationsCollapseBtn.setObjectName(u"OperationsCollapseBtn")
        self.OperationsCollapseBtn.setMinimumSize(QSize(46, 0))

        self.operationsPaneButtonsLayout.addWidget(self.OperationsCollapseBtn)

        self.operationsPaneButtonsSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.operationsPaneButtonsLayout.addItem(self.operationsPaneButtonsSpacer)

        self.DetailsToggleBtn = QPushButton(self.OperationsPaneButtons)
        self.DetailsToggleBtn.setObjectName(u"DetailsToggleBtn")
        self.DetailsToggleBtn.setMinimumSize(QSize(46, 0))
        self.DetailsToggleBtn.setCheckable(True)
        self.DetailsToggleBtn.setChecked(True)

        self.operationsPaneButtonsLayout.addWidget(self.DetailsToggleBtn)


        self.operationsPaneLayout.addWidget(self.OperationsPaneButtons)

        self.PositionsOperationsSplitter.addWidget(self.OperationsPane)
        self.OperationsDetailsSplitter.addWidget(self.PositionsOperationsSplitter)
        self.OperationDetails = QFrame(self.OperationsDetailsSplitter)
        self.OperationDetails.setObjectName(u"OperationDetails")
        sizePolicy8 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy8.setHorizontalStretch(0)
        sizePolicy8.setVerticalStretch(1)
        sizePolicy8.setHeightForWidth(self.OperationDetails.sizePolicy().hasHeightForWidth())
        self.OperationDetails.setSizePolicy(sizePolicy8)
        self.OperationDetails.setMinimumSize(QSize(0, 100))
        self.OperationDetails.setFrameShape(QFrame.Shape.StyledPanel)
        self.horizontalLayout_4 = QHBoxLayout(self.OperationDetails)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.OperationsTabs = JalOperationsTabs(self.OperationDetails)
        self.OperationsTabs.setObjectName(u"OperationsTabs")
        sizePolicy9 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy9.setHorizontalStretch(0)
        sizePolicy9.setVerticalStretch(0)
        sizePolicy9.setHeightForWidth(self.OperationsTabs.sizePolicy().hasHeightForWidth())
        self.OperationsTabs.setSizePolicy(sizePolicy9)

        self.horizontalLayout_4.addWidget(self.OperationsTabs)

        self.OperationsButtons = QFrame(self.OperationDetails)
        self.OperationsButtons.setObjectName(u"OperationsButtons")
        sizePolicy5.setHeightForWidth(self.OperationsButtons.sizePolicy().hasHeightForWidth())
        self.OperationsButtons.setSizePolicy(sizePolicy5)
        self.verticalLayout_3 = QVBoxLayout(self.OperationsButtons)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.NewOperationBtn = QPushButton(self.OperationsButtons)
        self.NewOperationBtn.setObjectName(u"NewOperationBtn")

        self.verticalLayout_3.addWidget(self.NewOperationBtn)

        self.CopyOperationBtn = QPushButton(self.OperationsButtons)
        self.CopyOperationBtn.setObjectName(u"CopyOperationBtn")

        self.verticalLayout_3.addWidget(self.CopyOperationBtn)

        self.DeleteOperationBtn = QPushButton(self.OperationsButtons)
        self.DeleteOperationBtn.setObjectName(u"DeleteOperationBtn")

        self.verticalLayout_3.addWidget(self.DeleteOperationBtn)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer_4)


        self.horizontalLayout_4.addWidget(self.OperationsButtons)

        self.OperationsDetailsSplitter.addWidget(self.OperationDetails)

        self.verticalLayout_2.addWidget(self.OperationsDetailsSplitter)

        self.BalanceOperationsSplitter.addWidget(self.OperationsBox)

        self.verticalLayout_4.addWidget(self.BalanceOperationsSplitter)

#if QT_CONFIG(shortcut)
        self.SearchLbl.setBuddy(self.SearchString)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.BalanceDate, self.BalancesCurrencyCombo)
        QWidget.setTabOrder(self.BalancesCurrencyCombo, self.BalancesTreeView)
        QWidget.setTabOrder(self.BalancesTreeView, self.PositionsTreeView)
        QWidget.setTabOrder(self.PositionsTreeView, self.PositionsCollapseBtn)
        QWidget.setTabOrder(self.PositionsCollapseBtn, self.DateRange)
        QWidget.setTabOrder(self.DateRange, self.SearchString)
        QWidget.setTabOrder(self.SearchString, self.ResetAccountBtn)
        QWidget.setTabOrder(self.ResetAccountBtn, self.OperationsTableView)
        QWidget.setTabOrder(self.OperationsTableView, self.OperationsCollapseBtn)
        QWidget.setTabOrder(self.OperationsCollapseBtn, self.DetailsToggleBtn)
        QWidget.setTabOrder(self.DetailsToggleBtn, self.OperationsTabs)
        QWidget.setTabOrder(self.OperationsTabs, self.NewOperationBtn)
        QWidget.setTabOrder(self.NewOperationBtn, self.CopyOperationBtn)
        QWidget.setTabOrder(self.CopyOperationBtn, self.DeleteOperationBtn)

        self.retranslateUi(OperationsWidget)

        QMetaObject.connectSlotsByName(OperationsWidget)
    # setupUi

    def retranslateUi(self, OperationsWidget):
        OperationsWidget.setWindowTitle(QCoreApplication.translate("OperationsWidget", u"Operations & Balances", None))
        self.BalanceBox.setTitle(QCoreApplication.translate("OperationsWidget", u"Balances", None))
        self.BalanceDate.setDisplayFormat(QCoreApplication.translate("OperationsWidget", u"dd/MM/yyyy", None))
        self.OperationsBox.setTitle(QCoreApplication.translate("OperationsWidget", u"Operations", None))
#if QT_CONFIG(tooltip)
        self.PositionsCollapseBtn.setToolTip(QCoreApplication.translate("OperationsWidget", u"Hide positions", None))
#endif // QT_CONFIG(tooltip)
        self.PositionsCollapseBtn.setText("")
        self.SearchLbl.setText(QCoreApplication.translate("OperationsWidget", u"S&earch:", None))
#if QT_CONFIG(tooltip)
        self.ResetAccountBtn.setToolTip(QCoreApplication.translate("OperationsWidget", u"Show all accounts", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.OperationsCollapseBtn.setToolTip(QCoreApplication.translate("OperationsWidget", u"Hide operations", None))
#endif // QT_CONFIG(tooltip)
        self.OperationsCollapseBtn.setText("")
#if QT_CONFIG(tooltip)
        self.DetailsToggleBtn.setToolTip(QCoreApplication.translate("OperationsWidget", u"Show or hide operation details", None))
#endif // QT_CONFIG(tooltip)
        self.DetailsToggleBtn.setText("")
#if QT_CONFIG(tooltip)
        self.NewOperationBtn.setToolTip(QCoreApplication.translate("OperationsWidget", u"New operation", None))
#endif // QT_CONFIG(tooltip)
        self.NewOperationBtn.setText("")
#if QT_CONFIG(tooltip)
        self.CopyOperationBtn.setToolTip(QCoreApplication.translate("OperationsWidget", u"Copy operation", None))
#endif // QT_CONFIG(tooltip)
        self.CopyOperationBtn.setText("")
#if QT_CONFIG(tooltip)
        self.DeleteOperationBtn.setToolTip(QCoreApplication.translate("OperationsWidget", u"Delete operation", None))
#endif // QT_CONFIG(tooltip)
        self.DeleteOperationBtn.setText("")
    # retranslateUi

