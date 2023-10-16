# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'receipt_import_dlg.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDateTimeEdit, QDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpacerItem, QTableView, QVBoxLayout,
    QWidget)

from jal.widgets.reference_selector import (AccountSelector, PeerSelector)

class Ui_ImportShopReceiptDlg(object):
    def setupUi(self, ImportShopReceiptDlg):
        if not ImportShopReceiptDlg.objectName():
            ImportShopReceiptDlg.setObjectName(u"ImportShopReceiptDlg")
        ImportShopReceiptDlg.resize(850, 587)
        self.verticalLayout = QVBoxLayout(ImportShopReceiptDlg)
        self.verticalLayout.setSpacing(6)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.InputFrame = QFrame(ImportShopReceiptDlg)
        self.InputFrame.setObjectName(u"InputFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.InputFrame.sizePolicy().hasHeightForWidth())
        self.InputFrame.setSizePolicy(sizePolicy)
        self.InputFrame.setFrameShape(QFrame.NoFrame)
        self.InputFrame.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_2 = QHBoxLayout(self.InputFrame)
        self.horizontalLayout_2.setSpacing(2)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.QRGroup = QGroupBox(self.InputFrame)
        self.QRGroup.setObjectName(u"QRGroup")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.QRGroup.sizePolicy().hasHeightForWidth())
        self.QRGroup.setSizePolicy(sizePolicy1)
        self.QRGroup.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.horizontalLayout = QHBoxLayout(self.QRGroup)
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(2, 2, 2, 2)
        self.ScanReceiptQR = QPushButton(self.QRGroup)
        self.ScanReceiptQR.setObjectName(u"ScanReceiptQR")

        self.horizontalLayout.addWidget(self.ScanReceiptQR)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)


        self.horizontalLayout_2.addWidget(self.QRGroup)


        self.verticalLayout.addWidget(self.InputFrame)

        self.SlipDataGroup = QGroupBox(ImportShopReceiptDlg)
        self.SlipDataGroup.setObjectName(u"SlipDataGroup")
        self.SlipDataGroup.setEnabled(True)
        sizePolicy1.setHeightForWidth(self.SlipDataGroup.sizePolicy().hasHeightForWidth())
        self.SlipDataGroup.setSizePolicy(sizePolicy1)
        self.gridLayout_2 = QGridLayout(self.SlipDataGroup)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(2, 2, 2, 2)
        self.ReceiptAPICombo = QComboBox(self.SlipDataGroup)
        self.ReceiptAPICombo.setObjectName(u"ReceiptAPICombo")

        self.gridLayout_2.addWidget(self.ReceiptAPICombo, 0, 1, 1, 1)

        self.ReceiptAPILabel = QLabel(self.SlipDataGroup)
        self.ReceiptAPILabel.setObjectName(u"ReceiptAPILabel")

        self.gridLayout_2.addWidget(self.ReceiptAPILabel, 0, 0, 1, 1)

        self.DownloadReceiptBtn = QPushButton(self.SlipDataGroup)
        self.DownloadReceiptBtn.setObjectName(u"DownloadReceiptBtn")

        self.gridLayout_2.addWidget(self.DownloadReceiptBtn, 2, 0, 1, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_2.addItem(self.verticalSpacer, 1, 0, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout_2.addItem(self.horizontalSpacer_2, 0, 3, 1, 1)

        self.ReceiptParametersList = QTableView(self.SlipDataGroup)
        self.ReceiptParametersList.setObjectName(u"ReceiptParametersList")
        self.ReceiptParametersList.horizontalHeader().setVisible(False)
        self.ReceiptParametersList.horizontalHeader().setStretchLastSection(True)
        self.ReceiptParametersList.verticalHeader().setMinimumSectionSize(20)
        self.ReceiptParametersList.verticalHeader().setDefaultSectionSize(20)

        self.gridLayout_2.addWidget(self.ReceiptParametersList, 0, 2, 3, 1)


        self.verticalLayout.addWidget(self.SlipDataGroup)

        self.ReceiptGroup = QGroupBox(ImportShopReceiptDlg)
        self.ReceiptGroup.setObjectName(u"ReceiptGroup")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.ReceiptGroup.sizePolicy().hasHeightForWidth())
        self.ReceiptGroup.setSizePolicy(sizePolicy2)
        self.gridLayout = QGridLayout(self.ReceiptGroup)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.SlipDateTime = QDateTimeEdit(self.ReceiptGroup)
        self.SlipDateTime.setObjectName(u"SlipDateTime")
        self.SlipDateTime.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.SlipDateTime, 2, 1, 1, 1)

        self.DateTimeLbl = QLabel(self.ReceiptGroup)
        self.DateTimeLbl.setObjectName(u"DateTimeLbl")

        self.gridLayout.addWidget(self.DateTimeLbl, 1, 1, 1, 1)

        self.CorrespondenceLbl = QLabel(self.ReceiptGroup)
        self.CorrespondenceLbl.setObjectName(u"CorrespondenceLbl")

        self.gridLayout.addWidget(self.CorrespondenceLbl, 3, 2, 1, 1)

        self.PeerEdit = PeerSelector(self.ReceiptGroup)
        self.PeerEdit.setObjectName(u"PeerEdit")

        self.gridLayout.addWidget(self.PeerEdit, 3, 3, 1, 1)

        self.PeerLbl = QLabel(self.ReceiptGroup)
        self.PeerLbl.setObjectName(u"PeerLbl")

        self.gridLayout.addWidget(self.PeerLbl, 3, 0, 1, 1)

        self.SlipShopName = QLineEdit(self.ReceiptGroup)
        self.SlipShopName.setObjectName(u"SlipShopName")
        self.SlipShopName.setEnabled(False)

        self.gridLayout.addWidget(self.SlipShopName, 3, 1, 1, 1)

        self.LinesLbl = QLabel(self.ReceiptGroup)
        self.LinesLbl.setObjectName(u"LinesLbl")
        self.LinesLbl.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)

        self.gridLayout.addWidget(self.LinesLbl, 4, 0, 1, 1)

        self.AccountLbl = QLabel(self.ReceiptGroup)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.gridLayout.addWidget(self.AccountLbl, 1, 3, 1, 1)

        self.AccountEdit = AccountSelector(self.ReceiptGroup)
        self.AccountEdit.setObjectName(u"AccountEdit")

        self.gridLayout.addWidget(self.AccountEdit, 2, 3, 1, 1)

        self.LinesTableView = QTableView(self.ReceiptGroup)
        self.LinesTableView.setObjectName(u"LinesTableView")
        self.LinesTableView.verticalHeader().setVisible(False)
        self.LinesTableView.verticalHeader().setMinimumSectionSize(20)
        self.LinesTableView.verticalHeader().setDefaultSectionSize(20)

        self.gridLayout.addWidget(self.LinesTableView, 4, 1, 1, 4)

        self.AssignCategoryBtn = QPushButton(self.ReceiptGroup)
        self.AssignCategoryBtn.setObjectName(u"AssignCategoryBtn")

        self.gridLayout.addWidget(self.AssignCategoryBtn, 2, 4, 1, 1)

        self.AssignTagBtn = QPushButton(self.ReceiptGroup)
        self.AssignTagBtn.setObjectName(u"AssignTagBtn")

        self.gridLayout.addWidget(self.AssignTagBtn, 3, 4, 1, 1)


        self.verticalLayout.addWidget(self.ReceiptGroup)

        self.DialogButtonsFrame = QFrame(ImportShopReceiptDlg)
        self.DialogButtonsFrame.setObjectName(u"DialogButtonsFrame")
        self.DialogButtonsFrame.setFrameShape(QFrame.NoFrame)
        self.DialogButtonsFrame.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_4 = QHBoxLayout(self.DialogButtonsFrame)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(2, 2, 2, 2)
        self.ClearBtn = QPushButton(self.DialogButtonsFrame)
        self.ClearBtn.setObjectName(u"ClearBtn")
        self.ClearBtn.setEnabled(True)

        self.horizontalLayout_4.addWidget(self.ClearBtn)

        self.AddOperationBtn = QPushButton(self.DialogButtonsFrame)
        self.AddOperationBtn.setObjectName(u"AddOperationBtn")
        self.AddOperationBtn.setEnabled(True)

        self.horizontalLayout_4.addWidget(self.AddOperationBtn)

        self.CloseBtn = QPushButton(self.DialogButtonsFrame)
        self.CloseBtn.setObjectName(u"CloseBtn")

        self.horizontalLayout_4.addWidget(self.CloseBtn)


        self.verticalLayout.addWidget(self.DialogButtonsFrame)


        self.retranslateUi(ImportShopReceiptDlg)
        self.CloseBtn.clicked.connect(ImportShopReceiptDlg.close)

        QMetaObject.connectSlotsByName(ImportShopReceiptDlg)
    # setupUi

    def retranslateUi(self, ImportShopReceiptDlg):
        ImportShopReceiptDlg.setWindowTitle(QCoreApplication.translate("ImportShopReceiptDlg", u"Import shop receipt", None))
        self.QRGroup.setTitle(QCoreApplication.translate("ImportShopReceiptDlg", u"Get receipt by scanning QR-code", None))
        self.ScanReceiptQR.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Scan receipt QR", None))
        self.SlipDataGroup.setTitle(QCoreApplication.translate("ImportShopReceiptDlg", u"Get receipt by manual data entry", None))
        self.ReceiptAPILabel.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Receipt type:", None))
        self.DownloadReceiptBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Download receipt", None))
        self.ReceiptGroup.setTitle(QCoreApplication.translate("ImportShopReceiptDlg", u"Operation data", None))
        self.SlipDateTime.setDisplayFormat(QCoreApplication.translate("ImportShopReceiptDlg", u"dd/MM/yyyy hh:mm:ss", None))
        self.DateTimeLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Date / Time:", None))
        self.CorrespondenceLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u" \u279c ", None))
        self.PeerLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Peer:", None))
        self.LinesLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Lines:", None))
        self.AccountLbl.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Account:", None))
        self.AssignCategoryBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Auto-assign categories", None))
        self.AssignTagBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Set Tag for all lines", None))
        self.ClearBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Clear", None))
        self.AddOperationBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Add", None))
        self.CloseBtn.setText(QCoreApplication.translate("ImportShopReceiptDlg", u"Close", None))
    # retranslateUi

