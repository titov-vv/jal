# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'slip_import_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from jal.widgets.reference_selector import AccountSelector
from jal.widgets.reference_selector import PeerSelector
from PySide2.QtMultimediaWidgets import QVideoWidget


class Ui_ImportSlipDlg(object):
    def setupUi(self, ImportSlipDlg):
        if not ImportSlipDlg.objectName():
            ImportSlipDlg.setObjectName(u"ImportSlipDlg")
        ImportSlipDlg.resize(850, 587)
        self.verticalLayout = QVBoxLayout(ImportSlipDlg)
        self.verticalLayout.setSpacing(6)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.InputFrame = QFrame(ImportSlipDlg)
        self.InputFrame.setObjectName(u"InputFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.InputFrame.sizePolicy().hasHeightForWidth())
        self.InputFrame.setSizePolicy(sizePolicy)
        self.InputFrame.setFrameShape(QFrame.NoFrame)
        self.InputFrame.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_3 = QHBoxLayout(self.InputFrame)
        self.horizontalLayout_3.setSpacing(2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.QRGroup = QGroupBox(self.InputFrame)
        self.QRGroup.setObjectName(u"QRGroup")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.QRGroup.sizePolicy().hasHeightForWidth())
        self.QRGroup.setSizePolicy(sizePolicy1)
        self.QRGroup.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.verticalLayout_3 = QVBoxLayout(self.QRGroup)
        self.verticalLayout_3.setSpacing(6)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(2, 2, 2, 2)
        self.GetQRfromCameraBtn = QPushButton(self.QRGroup)
        self.GetQRfromCameraBtn.setObjectName(u"GetQRfromCameraBtn")

        self.verticalLayout_3.addWidget(self.GetQRfromCameraBtn)

        self.LoadQRfromFileBtn = QPushButton(self.QRGroup)
        self.LoadQRfromFileBtn.setObjectName(u"LoadQRfromFileBtn")

        self.verticalLayout_3.addWidget(self.LoadQRfromFileBtn)

        self.GetQRfromClipboardBtn = QPushButton(self.QRGroup)
        self.GetQRfromClipboardBtn.setObjectName(u"GetQRfromClipboardBtn")

        self.verticalLayout_3.addWidget(self.GetQRfromClipboardBtn)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer)


        self.horizontalLayout_3.addWidget(self.QRGroup)

        self.SlipDataGroup = QGroupBox(self.InputFrame)
        self.SlipDataGroup.setObjectName(u"SlipDataGroup")
        sizePolicy1.setHeightForWidth(self.SlipDataGroup.sizePolicy().hasHeightForWidth())
        self.SlipDataGroup.setSizePolicy(sizePolicy1)
        self.gridLayout_2 = QGridLayout(self.SlipDataGroup)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(2, 2, 2, 2)
        self.GetSlipBtn = QPushButton(self.SlipDataGroup)
        self.GetSlipBtn.setObjectName(u"GetSlipBtn")

        self.gridLayout_2.addWidget(self.GetSlipBtn, 7, 1, 1, 1)

        self.AmountLbl = QLabel(self.SlipDataGroup)
        self.AmountLbl.setObjectName(u"AmountLbl")

        self.gridLayout_2.addWidget(self.AmountLbl, 0, 2, 1, 1)

        self.SlipTimstamp = QDateTimeEdit(self.SlipDataGroup)
        self.SlipTimstamp.setObjectName(u"SlipTimstamp")
        self.SlipTimstamp.setTimeSpec(Qt.UTC)

        self.gridLayout_2.addWidget(self.SlipTimstamp, 0, 1, 1, 1)

        self.TimestampLbl = QLabel(self.SlipDataGroup)
        self.TimestampLbl.setObjectName(u"TimestampLbl")

        self.gridLayout_2.addWidget(self.TimestampLbl, 0, 0, 1, 1)

        self.FDlbl = QLabel(self.SlipDataGroup)
        self.FDlbl.setObjectName(u"FDlbl")

        self.gridLayout_2.addWidget(self.FDlbl, 2, 0, 1, 1)

        self.SlipAmount = QLineEdit(self.SlipDataGroup)
        self.SlipAmount.setObjectName(u"SlipAmount")

        self.gridLayout_2.addWidget(self.SlipAmount, 0, 3, 1, 1)

        self.FP = QLineEdit(self.SlipDataGroup)
        self.FP.setObjectName(u"FP")

        self.gridLayout_2.addWidget(self.FP, 2, 3, 1, 1)

        self.FD = QLineEdit(self.SlipDataGroup)
        self.FD.setObjectName(u"FD")

        self.gridLayout_2.addWidget(self.FD, 2, 1, 1, 1)

        self.FNlbl = QLabel(self.SlipDataGroup)
        self.FNlbl.setObjectName(u"FNlbl")

        self.gridLayout_2.addWidget(self.FNlbl, 4, 0, 1, 1)

        self.DummyLbl = QLabel(self.SlipDataGroup)
        self.DummyLbl.setObjectName(u"DummyLbl")

        self.gridLayout_2.addWidget(self.DummyLbl, 7, 0, 1, 1)

        self.SlipTypeLbl = QLabel(self.SlipDataGroup)
        self.SlipTypeLbl.setObjectName(u"SlipTypeLbl")

        self.gridLayout_2.addWidget(self.SlipTypeLbl, 4, 2, 1, 1)

        self.FN = QLineEdit(self.SlipDataGroup)
        self.FN.setObjectName(u"FN")

        self.gridLayout_2.addWidget(self.FN, 4, 1, 1, 1)

        self.LoadJSONfromFileBtn = QPushButton(self.SlipDataGroup)
        self.LoadJSONfromFileBtn.setObjectName(u"LoadJSONfromFileBtn")

        self.gridLayout_2.addWidget(self.LoadJSONfromFileBtn, 7, 3, 1, 1)

        self.FPlbl = QLabel(self.SlipDataGroup)
        self.FPlbl.setObjectName(u"FPlbl")

        self.gridLayout_2.addWidget(self.FPlbl, 2, 2, 1, 1)

        self.line = QFrame(self.SlipDataGroup)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.gridLayout_2.addWidget(self.line, 5, 0, 1, 4)

        self.SlipType = QComboBox(self.SlipDataGroup)
        self.SlipType.addItem("")
        self.SlipType.addItem("")
        self.SlipType.setObjectName(u"SlipType")

        self.gridLayout_2.addWidget(self.SlipType, 4, 3, 1, 1)


        self.horizontalLayout_3.addWidget(self.SlipDataGroup)

        self.CameraGroup = QGroupBox(self.InputFrame)
        self.CameraGroup.setObjectName(u"CameraGroup")
        self.verticalLayout_2 = QVBoxLayout(self.CameraGroup)
        self.verticalLayout_2.setSpacing(2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(2, 2, 2, 2)
        self.Viewfinder = QVideoWidget(self.CameraGroup)
        self.Viewfinder.setObjectName(u"Viewfinder")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.Viewfinder.sizePolicy().hasHeightForWidth())
        self.Viewfinder.setSizePolicy(sizePolicy2)

        self.verticalLayout_2.addWidget(self.Viewfinder)

        self.CameraBtnFrame = QFrame(self.CameraGroup)
        self.CameraBtnFrame.setObjectName(u"CameraBtnFrame")
        sizePolicy3 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.CameraBtnFrame.sizePolicy().hasHeightForWidth())
        self.CameraBtnFrame.setSizePolicy(sizePolicy3)
        self.CameraBtnFrame.setFrameShape(QFrame.NoFrame)
        self.CameraBtnFrame.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_5 = QHBoxLayout(self.CameraBtnFrame)
        self.horizontalLayout_5.setSpacing(2)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.StopCameraBtn = QPushButton(self.CameraBtnFrame)
        self.StopCameraBtn.setObjectName(u"StopCameraBtn")

        self.horizontalLayout_5.addWidget(self.StopCameraBtn)


        self.verticalLayout_2.addWidget(self.CameraBtnFrame)


        self.horizontalLayout_3.addWidget(self.CameraGroup)


        self.verticalLayout.addWidget(self.InputFrame)

        self.SlipGroup = QGroupBox(ImportSlipDlg)
        self.SlipGroup.setObjectName(u"SlipGroup")
        sizePolicy2.setHeightForWidth(self.SlipGroup.sizePolicy().hasHeightForWidth())
        self.SlipGroup.setSizePolicy(sizePolicy2)
        self.gridLayout = QGridLayout(self.SlipGroup)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.SlipDateTime = QDateTimeEdit(self.SlipGroup)
        self.SlipDateTime.setObjectName(u"SlipDateTime")
        self.SlipDateTime.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.SlipDateTime, 2, 1, 1, 1)

        self.DateTimeLbl = QLabel(self.SlipGroup)
        self.DateTimeLbl.setObjectName(u"DateTimeLbl")

        self.gridLayout.addWidget(self.DateTimeLbl, 1, 1, 1, 1)

        self.CorrespondenceLbl = QLabel(self.SlipGroup)
        self.CorrespondenceLbl.setObjectName(u"CorrespondenceLbl")

        self.gridLayout.addWidget(self.CorrespondenceLbl, 3, 2, 1, 1)

        self.PeerEdit = PeerSelector(self.SlipGroup)
        self.PeerEdit.setObjectName(u"PeerEdit")

        self.gridLayout.addWidget(self.PeerEdit, 3, 3, 1, 1)

        self.PeerLbl = QLabel(self.SlipGroup)
        self.PeerLbl.setObjectName(u"PeerLbl")

        self.gridLayout.addWidget(self.PeerLbl, 3, 0, 1, 1)

        self.SlipShopName = QLineEdit(self.SlipGroup)
        self.SlipShopName.setObjectName(u"SlipShopName")
        self.SlipShopName.setEnabled(False)

        self.gridLayout.addWidget(self.SlipShopName, 3, 1, 1, 1)

        self.LinesLbl = QLabel(self.SlipGroup)
        self.LinesLbl.setObjectName(u"LinesLbl")
        self.LinesLbl.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)

        self.gridLayout.addWidget(self.LinesLbl, 4, 0, 1, 1)

        self.AccountLbl = QLabel(self.SlipGroup)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.gridLayout.addWidget(self.AccountLbl, 1, 3, 1, 1)

        self.AccountEdit = AccountSelector(self.SlipGroup)
        self.AccountEdit.setObjectName(u"AccountEdit")

        self.gridLayout.addWidget(self.AccountEdit, 2, 3, 1, 1)

        self.LinesTableView = QTableView(self.SlipGroup)
        self.LinesTableView.setObjectName(u"LinesTableView")
        self.LinesTableView.verticalHeader().setVisible(False)
        self.LinesTableView.verticalHeader().setMinimumSectionSize(20)
        self.LinesTableView.verticalHeader().setDefaultSectionSize(20)

        self.gridLayout.addWidget(self.LinesTableView, 4, 1, 1, 4)

        self.AssignCategoryBtn = QPushButton(self.SlipGroup)
        self.AssignCategoryBtn.setObjectName(u"AssignCategoryBtn")

        self.gridLayout.addWidget(self.AssignCategoryBtn, 2, 4, 1, 1)

        self.AssignTagBtn = QPushButton(self.SlipGroup)
        self.AssignTagBtn.setObjectName(u"AssignTagBtn")

        self.gridLayout.addWidget(self.AssignTagBtn, 3, 4, 1, 1)


        self.verticalLayout.addWidget(self.SlipGroup)

        self.DialogButtonsFrame = QFrame(ImportSlipDlg)
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


        self.retranslateUi(ImportSlipDlg)
        self.CloseBtn.clicked.connect(ImportSlipDlg.close)

        QMetaObject.connectSlotsByName(ImportSlipDlg)
    # setupUi

    def retranslateUi(self, ImportSlipDlg):
        ImportSlipDlg.setWindowTitle(QCoreApplication.translate("ImportSlipDlg", u"Import Slip", None))
        self.QRGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"QR-code", None))
        self.GetQRfromCameraBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Get from camera", None))
        self.LoadQRfromFileBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Load from file", None))
        self.GetQRfromClipboardBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Get from clipboard", None))
        self.SlipDataGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"Slip data", None))
        self.GetSlipBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Get slip from internet", None))
        self.AmountLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Amount:", None))
        self.SlipTimstamp.setDisplayFormat(QCoreApplication.translate("ImportSlipDlg", u"dd/MM/yyyy hh:mm:ss", None))
        self.TimestampLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Date/Time:", None))
        self.FDlbl.setText(QCoreApplication.translate("ImportSlipDlg", u"FD:", None))
        self.FNlbl.setText(QCoreApplication.translate("ImportSlipDlg", u"FN:", None))
        self.DummyLbl.setText("")
        self.SlipTypeLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Type:", None))
        self.LoadJSONfromFileBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Load slip from JSON file", None))
        self.FPlbl.setText(QCoreApplication.translate("ImportSlipDlg", u"FP:", None))
        self.SlipType.setItemText(0, QCoreApplication.translate("ImportSlipDlg", u"Purchase", None))
        self.SlipType.setItemText(1, QCoreApplication.translate("ImportSlipDlg", u"Return", None))

        self.CameraGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"Camera", None))
        self.StopCameraBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Stop camera", None))
        self.SlipGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"Slip", None))
        self.SlipDateTime.setDisplayFormat(QCoreApplication.translate("ImportSlipDlg", u"dd/MM/yyyy hh:mm:ss", None))
        self.DateTimeLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Date / Time:", None))
        self.CorrespondenceLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"-->", None))
        self.PeerLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Peer:", None))
        self.LinesLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Lines:", None))
        self.AccountLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Account:", None))
        self.AssignCategoryBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Auto-assign categories", None))
        self.AssignTagBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Set Tag for all lines", None))
        self.ClearBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Clear", None))
        self.AddOperationBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Add", None))
        self.CloseBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Close", None))
    # retranslateUi

