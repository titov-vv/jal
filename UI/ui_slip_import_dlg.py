# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'slip_import_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.15.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QDate, QDateTime, QMetaObject,
    QObject, QPoint, QRect, QSize, QTime, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter,
    QPixmap, QRadialGradient)
from PySide2.QtWidgets import *

from PySide2.QtMultimediaWidgets import QVideoWidget
from CustomUI.reference_selector import AccountSelector


class Ui_ImportSlipDlg(object):
    def setupUi(self, ImportSlipDlg):
        if not ImportSlipDlg.objectName():
            ImportSlipDlg.setObjectName(u"ImportSlipDlg")
        ImportSlipDlg.resize(600, 700)
        self.verticalLayout = QVBoxLayout(ImportSlipDlg)
        self.verticalLayout.setSpacing(6)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.QRGroup = QGroupBox(ImportSlipDlg)
        self.QRGroup.setObjectName(u"QRGroup")
        self.horizontalLayout = QHBoxLayout(self.QRGroup)
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(2, 2, 2, 2)
        self.GetQRfromClipboardBtn = QPushButton(self.QRGroup)
        self.GetQRfromClipboardBtn.setObjectName(u"GetQRfromClipboardBtn")

        self.horizontalLayout.addWidget(self.GetQRfromClipboardBtn)

        self.LoadQRfromFileBtn = QPushButton(self.QRGroup)
        self.LoadQRfromFileBtn.setObjectName(u"LoadQRfromFileBtn")

        self.horizontalLayout.addWidget(self.LoadQRfromFileBtn)

        self.GetQRfromCameraBtn = QPushButton(self.QRGroup)
        self.GetQRfromCameraBtn.setObjectName(u"GetQRfromCameraBtn")

        self.horizontalLayout.addWidget(self.GetQRfromCameraBtn)


        self.verticalLayout.addWidget(self.QRGroup)

        self.frame_2 = QFrame(ImportSlipDlg)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_3.setSpacing(2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.SlipDataGroup = QGroupBox(self.frame_2)
        self.SlipDataGroup.setObjectName(u"SlipDataGroup")
        self.formLayout = QFormLayout(self.SlipDataGroup)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setContentsMargins(2, 2, 2, 2)
        self.FD = QLineEdit(self.SlipDataGroup)
        self.FD.setObjectName(u"FD")

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.FD)

        self.FN = QLineEdit(self.SlipDataGroup)
        self.FN.setObjectName(u"FN")

        self.formLayout.setWidget(4, QFormLayout.FieldRole, self.FN)

        self.FP = QLineEdit(self.SlipDataGroup)
        self.FP.setObjectName(u"FP")

        self.formLayout.setWidget(3, QFormLayout.FieldRole, self.FP)

        self.FNlbl = QLabel(self.SlipDataGroup)
        self.FNlbl.setObjectName(u"FNlbl")

        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.FNlbl)

        self.FPlbl = QLabel(self.SlipDataGroup)
        self.FPlbl.setObjectName(u"FPlbl")

        self.formLayout.setWidget(3, QFormLayout.LabelRole, self.FPlbl)

        self.GetSlipBtn = QPushButton(self.SlipDataGroup)
        self.GetSlipBtn.setObjectName(u"GetSlipBtn")

        self.formLayout.setWidget(6, QFormLayout.FieldRole, self.GetSlipBtn)

        self.FDlbl = QLabel(self.SlipDataGroup)
        self.FDlbl.setObjectName(u"FDlbl")

        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.FDlbl)

        self.DummyLbl = QLabel(self.SlipDataGroup)
        self.DummyLbl.setObjectName(u"DummyLbl")

        self.formLayout.setWidget(6, QFormLayout.LabelRole, self.DummyLbl)

        self.TimestampLbl = QLabel(self.SlipDataGroup)
        self.TimestampLbl.setObjectName(u"TimestampLbl")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.TimestampLbl)

        self.AmountLbl = QLabel(self.SlipDataGroup)
        self.AmountLbl.setObjectName(u"AmountLbl")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.AmountLbl)

        self.SlipTimstamp = QDateTimeEdit(self.SlipDataGroup)
        self.SlipTimstamp.setObjectName(u"SlipTimstamp")

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.SlipTimstamp)

        self.SlipAmount = QLineEdit(self.SlipDataGroup)
        self.SlipAmount.setObjectName(u"SlipAmount")

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.SlipAmount)

        self.SlipTypeLbl = QLabel(self.SlipDataGroup)
        self.SlipTypeLbl.setObjectName(u"SlipTypeLbl")

        self.formLayout.setWidget(5, QFormLayout.LabelRole, self.SlipTypeLbl)

        self.SlipType = QLineEdit(self.SlipDataGroup)
        self.SlipType.setObjectName(u"SlipType")

        self.formLayout.setWidget(5, QFormLayout.FieldRole, self.SlipType)


        self.horizontalLayout_3.addWidget(self.SlipDataGroup)

        self.CameraGroup = QGroupBox(self.frame_2)
        self.CameraGroup.setObjectName(u"CameraGroup")
        self.verticalLayout_2 = QVBoxLayout(self.CameraGroup)
        self.verticalLayout_2.setSpacing(2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(2, 2, 2, 2)
        self.Viewfinder = QVideoWidget(self.CameraGroup)
        self.Viewfinder.setObjectName(u"Viewfinder")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.Viewfinder.sizePolicy().hasHeightForWidth())
        self.Viewfinder.setSizePolicy(sizePolicy)

        self.verticalLayout_2.addWidget(self.Viewfinder)

        self.frame_3 = QFrame(self.CameraGroup)
        self.frame_3.setObjectName(u"frame_3")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.frame_3.sizePolicy().hasHeightForWidth())
        self.frame_3.setSizePolicy(sizePolicy1)
        self.frame_3.setFrameShape(QFrame.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Plain)
        self.horizontalLayout_5 = QHBoxLayout(self.frame_3)
        self.horizontalLayout_5.setSpacing(2)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.StopCameraBtn = QPushButton(self.frame_3)
        self.StopCameraBtn.setObjectName(u"StopCameraBtn")

        self.horizontalLayout_5.addWidget(self.StopCameraBtn)


        self.verticalLayout_2.addWidget(self.frame_3)


        self.horizontalLayout_3.addWidget(self.CameraGroup)


        self.verticalLayout.addWidget(self.frame_2)

        self.JSONGroup = QGroupBox(ImportSlipDlg)
        self.JSONGroup.setObjectName(u"JSONGroup")
        self.horizontalLayout_2 = QHBoxLayout(self.JSONGroup)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(2, 2, 2, 2)
        self.LoadJSONfromFileBtn = QPushButton(self.JSONGroup)
        self.LoadJSONfromFileBtn.setObjectName(u"LoadJSONfromFileBtn")

        self.horizontalLayout_2.addWidget(self.LoadJSONfromFileBtn)


        self.verticalLayout.addWidget(self.JSONGroup)

        self.SlipGroup = QGroupBox(ImportSlipDlg)
        self.SlipGroup.setObjectName(u"SlipGroup")
        self.gridLayout = QGridLayout(self.SlipGroup)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.SlipShopName = QLineEdit(self.SlipGroup)
        self.SlipShopName.setObjectName(u"SlipShopName")

        self.gridLayout.addWidget(self.SlipShopName, 1, 1, 1, 1)

        self.PeerLbl = QLabel(self.SlipGroup)
        self.PeerLbl.setObjectName(u"PeerLbl")

        self.gridLayout.addWidget(self.PeerLbl, 1, 0, 1, 1)

        self.tableView = QTableView(self.SlipGroup)
        self.tableView.setObjectName(u"tableView")

        self.gridLayout.addWidget(self.tableView, 2, 1, 1, 2)

        self.LinesLbl = QLabel(self.SlipGroup)
        self.LinesLbl.setObjectName(u"LinesLbl")
        self.LinesLbl.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)

        self.gridLayout.addWidget(self.LinesLbl, 2, 0, 1, 1)

        self.LoadedLbl = QLabel(self.SlipGroup)
        self.LoadedLbl.setObjectName(u"LoadedLbl")

        self.gridLayout.addWidget(self.LoadedLbl, 0, 1, 1, 1)

        self.StoredLbl = QLabel(self.SlipGroup)
        self.StoredLbl.setObjectName(u"StoredLbl")

        self.gridLayout.addWidget(self.StoredLbl, 0, 2, 1, 1)

        self.AccountEdit = AccountSelector(self.SlipGroup)
        self.AccountEdit.setObjectName(u"AccountEdit")

        self.gridLayout.addWidget(self.AccountEdit, 1, 2, 1, 1)


        self.verticalLayout.addWidget(self.SlipGroup)

        self.frame = QFrame(ImportSlipDlg)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(2, 2, 2, 2)
        self.ClearBtn = QPushButton(self.frame)
        self.ClearBtn.setObjectName(u"ClearBtn")

        self.horizontalLayout_4.addWidget(self.ClearBtn)

        self.AddOperationBtn = QPushButton(self.frame)
        self.AddOperationBtn.setObjectName(u"AddOperationBtn")

        self.horizontalLayout_4.addWidget(self.AddOperationBtn)

        self.CloseBtn = QPushButton(self.frame)
        self.CloseBtn.setObjectName(u"CloseBtn")

        self.horizontalLayout_4.addWidget(self.CloseBtn)


        self.verticalLayout.addWidget(self.frame)


        self.retranslateUi(ImportSlipDlg)

        QMetaObject.connectSlotsByName(ImportSlipDlg)
    # setupUi

    def retranslateUi(self, ImportSlipDlg):
        ImportSlipDlg.setWindowTitle(QCoreApplication.translate("ImportSlipDlg", u"Import Slip", None))
        self.QRGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"QR-code", None))
        self.GetQRfromClipboardBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Get from clipboard", None))
        self.LoadQRfromFileBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Load from file", None))
        self.GetQRfromCameraBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Get from camera", None))
        self.SlipDataGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"Slip data", None))
        self.FNlbl.setText(QCoreApplication.translate("ImportSlipDlg", u"FN:", None))
        self.FPlbl.setText(QCoreApplication.translate("ImportSlipDlg", u"FP:", None))
        self.GetSlipBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Get Slip", None))
        self.FDlbl.setText(QCoreApplication.translate("ImportSlipDlg", u"FD:", None))
        self.DummyLbl.setText("")
        self.TimestampLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Date/Time:", None))
        self.AmountLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Amount:", None))
        self.SlipTimstamp.setDisplayFormat(QCoreApplication.translate("ImportSlipDlg", u"dd/MM/yyyy hh:mm:ss", None))
        self.SlipTypeLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Type:", None))
        self.CameraGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"Camera", None))
        self.StopCameraBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Stop Camera", None))
        self.JSONGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"From JSON-file", None))
        self.LoadJSONfromFileBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Load from file", None))
        self.SlipGroup.setTitle(QCoreApplication.translate("ImportSlipDlg", u"Slip", None))
        self.PeerLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Peer:", None))
        self.LinesLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Lines:", None))
        self.LoadedLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"Imported:", None))
        self.StoredLbl.setText(QCoreApplication.translate("ImportSlipDlg", u"To be added:", None))
        self.ClearBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Clear", None))
        self.AddOperationBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Add", None))
        self.CloseBtn.setText(QCoreApplication.translate("ImportSlipDlg", u"Close", None))
    # retranslateUi

