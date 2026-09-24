# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'receipt_import_dlg.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
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
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QDateTimeEdit,
    QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
    QHeaderView, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpacerItem, QTableView, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

from jal.widgets.reference_selector import ReferenceSelectorWidget

class Ui_ImportShopReceiptDlg(object):
    def setupUi(self, ImportShopReceiptDlg):
        if not ImportShopReceiptDlg.objectName():
            ImportShopReceiptDlg.setObjectName(u"ImportShopReceiptDlg")
        ImportShopReceiptDlg.resize(850, 760)
        self.verticalLayout = QVBoxLayout(ImportShopReceiptDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.InboxGroup = QGroupBox(ImportShopReceiptDlg)
        self.InboxGroup.setObjectName(u"InboxGroup")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.InboxGroup.sizePolicy().hasHeightForWidth())
        self.InboxGroup.setSizePolicy(sizePolicy)
        self.gridLayout_3 = QGridLayout(self.InboxGroup)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.InboxList = QTableWidget(self.InboxGroup)
        if (self.InboxList.columnCount() < 3):
            self.InboxList.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.InboxList.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.InboxList.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.InboxList.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        self.InboxList.setObjectName(u"InboxList")
        self.InboxList.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.InboxList.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.InboxList.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.InboxList.setColumnCount(3)
        self.InboxList.horizontalHeader().setStretchLastSection(True)
        self.InboxList.verticalHeader().setVisible(False)
        self.InboxList.verticalHeader().setMinimumSectionSize(20)

        self.gridLayout_3.addWidget(self.InboxList, 0, 0, 4, 1)

        self.InboxLoadBtn = QPushButton(self.InboxGroup)
        self.InboxLoadBtn.setObjectName(u"InboxLoadBtn")

        self.gridLayout_3.addWidget(self.InboxLoadBtn, 0, 1, 1, 1)

        self.InboxRefreshBtn = QPushButton(self.InboxGroup)
        self.InboxRefreshBtn.setObjectName(u"InboxRefreshBtn")

        self.gridLayout_3.addWidget(self.InboxRefreshBtn, 1, 1, 1, 1)

        self.InboxSkipBtn = QPushButton(self.InboxGroup)
        self.InboxSkipBtn.setObjectName(u"InboxSkipBtn")

        self.gridLayout_3.addWidget(self.InboxSkipBtn, 2, 1, 1, 1)

        self.inboxButtonsSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_3.addItem(self.inboxButtonsSpacer, 3, 1, 1, 1)

        self.InboxFolderLbl = QLabel(self.InboxGroup)
        self.InboxFolderLbl.setObjectName(u"InboxFolderLbl")

        self.gridLayout_3.addWidget(self.InboxFolderLbl, 4, 0, 1, 2)


        self.verticalLayout.addWidget(self.InboxGroup)

        self.ReceiptGroup = QGroupBox(ImportShopReceiptDlg)
        self.ReceiptGroup.setObjectName(u"ReceiptGroup")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.ReceiptGroup.sizePolicy().hasHeightForWidth())
        self.ReceiptGroup.setSizePolicy(sizePolicy1)
        self.gridLayout = QGridLayout(self.ReceiptGroup)
        self.gridLayout.setObjectName(u"gridLayout")
        self.SlipDateTime = QDateTimeEdit(self.ReceiptGroup)
        self.SlipDateTime.setObjectName(u"SlipDateTime")
        self.SlipDateTime.setTimeSpec(Qt.TimeSpec.UTC)

        self.gridLayout.addWidget(self.SlipDateTime, 2, 1, 1, 1)

        self.DateTimeLbl = QLabel(self.ReceiptGroup)
        self.DateTimeLbl.setObjectName(u"DateTimeLbl")

        self.gridLayout.addWidget(self.DateTimeLbl, 1, 1, 1, 1)

        self.CorrespondenceLbl = QLabel(self.ReceiptGroup)
        self.CorrespondenceLbl.setObjectName(u"CorrespondenceLbl")

        self.gridLayout.addWidget(self.CorrespondenceLbl, 3, 3, 1, 1)

        self.PeerEdit = ReferenceSelectorWidget(self.ReceiptGroup)
        self.PeerEdit.setObjectName(u"PeerEdit")

        self.gridLayout.addWidget(self.PeerEdit, 3, 4, 1, 1)

        self.PeerLbl = QLabel(self.ReceiptGroup)
        self.PeerLbl.setObjectName(u"PeerLbl")

        self.gridLayout.addWidget(self.PeerLbl, 3, 0, 1, 1)

        self.SlipShopName = QLineEdit(self.ReceiptGroup)
        self.SlipShopName.setObjectName(u"SlipShopName")
        self.SlipShopName.setEnabled(False)

        self.gridLayout.addWidget(self.SlipShopName, 3, 1, 1, 1)

        self.LinesLbl = QLabel(self.ReceiptGroup)
        self.LinesLbl.setObjectName(u"LinesLbl")
        self.LinesLbl.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)

        self.gridLayout.addWidget(self.LinesLbl, 4, 0, 1, 1)

        self.AccountLbl = QLabel(self.ReceiptGroup)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.gridLayout.addWidget(self.AccountLbl, 1, 4, 1, 1)

        self.AccountEdit = ReferenceSelectorWidget(self.ReceiptGroup)
        self.AccountEdit.setObjectName(u"AccountEdit")

        self.gridLayout.addWidget(self.AccountEdit, 2, 4, 1, 1)

        self.LinesTableView = QTableView(self.ReceiptGroup)
        self.LinesTableView.setObjectName(u"LinesTableView")
        self.LinesTableView.verticalHeader().setVisible(False)
        self.LinesTableView.verticalHeader().setMinimumSectionSize(20)

        self.gridLayout.addWidget(self.LinesTableView, 4, 1, 1, 5)

        self.AssignTagBtn = QPushButton(self.ReceiptGroup)
        self.AssignTagBtn.setObjectName(u"AssignTagBtn")

        self.gridLayout.addWidget(self.AssignTagBtn, 3, 5, 1, 1)

        self.accountGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.accountGroupSpacer, 1, 2, 1, 1)


        self.verticalLayout.addWidget(self.ReceiptGroup)

        self.DialogButtonBox = QDialogButtonBox(ImportShopReceiptDlg)
        self.DialogButtonBox.setObjectName(u"DialogButtonBox")
        self.DialogButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.DialogButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.verticalLayout.addWidget(self.DialogButtonBox)

#if QT_CONFIG(shortcut)
        self.PeerLbl.setBuddy(self.SlipShopName)
        self.LinesLbl.setBuddy(self.LinesTableView)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.InboxList, self.InboxLoadBtn)
        QWidget.setTabOrder(self.InboxLoadBtn, self.InboxRefreshBtn)
        QWidget.setTabOrder(self.InboxRefreshBtn, self.InboxSkipBtn)
        QWidget.setTabOrder(self.InboxSkipBtn, self.SlipDateTime)
        QWidget.setTabOrder(self.SlipDateTime, self.PeerEdit)
        QWidget.setTabOrder(self.PeerEdit, self.SlipShopName)
        QWidget.setTabOrder(self.SlipShopName, self.AccountEdit)
        QWidget.setTabOrder(self.AccountEdit, self.LinesTableView)
        QWidget.setTabOrder(self.LinesTableView, self.AssignTagBtn)
        QWidget.setTabOrder(self.AssignTagBtn, self.DialogButtonBox)

        self.retranslateUi(ImportShopReceiptDlg)

        QMetaObject.connectSlotsByName(ImportShopReceiptDlg)
    # setupUi

    def retranslateUi(self, ImportShopReceiptDlg):
        ImportShopReceiptDlg.setWindowTitle(QCoreApplication.translate("ImportShopReceiptDlg", u"Import shop receipt", None))
        self.InboxGroup.setTitle(QCoreApplication.translate("ImportShopReceiptDlg", u"Get receipt from phone inbox", None))
        ___qtablewidgetitem = self.InboxList.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Captured", None))
        ___qtablewidgetitem1 = self.InboxList.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Source", None))
        ___qtablewidgetitem2 = self.InboxList.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Import as", None))
        self.InboxLoadBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"L&oad", None))
        self.InboxRefreshBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Re&fresh", None))
#if QT_CONFIG(tooltip)
        self.InboxSkipBtn.setToolTip(QCoreApplication.translate("ImportShopReceiptDlg", u"Move the selected file into the 'done' folder without importing it", None))
#endif // QT_CONFIG(tooltip)
        self.InboxSkipBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"S&kip", None))
        self.ReceiptGroup.setTitle(QCoreApplication.translate("ImportShopReceiptDlg", u"Operation data", None))
        self.SlipDateTime.setDisplayFormat(QCoreApplication.translate("ImportShopReceiptDlg", u"dd/MM/yyyy hh:mm:ss", None))
        self.DateTimeLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Date / Time:", None))
        self.CorrespondenceLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u" \u279c ", None))
        self.PeerLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"&Peer:", None))
        self.LinesLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"&Lines:", None))
        self.AccountLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Account:", None))
        self.AssignTagBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Set Tag for all lines", None))
    # retranslateUi

