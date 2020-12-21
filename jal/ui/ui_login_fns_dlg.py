# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login_fns_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from PySide2.QtWebEngineWidgets import QWebEngineView



class Ui_LoginFNSDialog(object):
    def setupUi(self, LoginFNSDialog):
        if not LoginFNSDialog.objectName():
            LoginFNSDialog.setObjectName(u"LoginFNSDialog")
        LoginFNSDialog.resize(400, 500)
        self.verticalLayout_3 = QVBoxLayout(LoginFNSDialog)
        self.verticalLayout_3.setSpacing(6)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(2, 2, 2, 2)
        self.LoginMethodTabs = QTabWidget(LoginFNSDialog)
        self.LoginMethodTabs.setObjectName(u"LoginMethodTabs")
        self.LoginPasswordTab = QWidget()
        self.LoginPasswordTab.setObjectName(u"LoginPasswordTab")
        self.verticalLayout = QVBoxLayout(self.LoginPasswordTab)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.LoginDataFrame = QFrame(self.LoginPasswordTab)
        self.LoginDataFrame.setObjectName(u"LoginDataFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.LoginDataFrame.sizePolicy().hasHeightForWidth())
        self.LoginDataFrame.setSizePolicy(sizePolicy)
        self.LoginDataFrame.setFrameShape(QFrame.NoFrame)
        self.LoginDataFrame.setFrameShadow(QFrame.Plain)
        self.formLayout = QFormLayout(self.LoginDataFrame)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setHorizontalSpacing(6)
        self.formLayout.setContentsMargins(6, -1, 6, 0)
        self.InnLbl = QLabel(self.LoginDataFrame)
        self.InnLbl.setObjectName(u"InnLbl")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.InnLbl)

        self.InnEdit = QLineEdit(self.LoginDataFrame)
        self.InnEdit.setObjectName(u"InnEdit")

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.InnEdit)

        self.PasswordLbl = QLabel(self.LoginDataFrame)
        self.PasswordLbl.setObjectName(u"PasswordLbl")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.PasswordLbl)

        self.PasswordEdit = QLineEdit(self.LoginDataFrame)
        self.PasswordEdit.setObjectName(u"PasswordEdit")
        self.PasswordEdit.setEchoMode(QLineEdit.Password)

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.PasswordEdit)


        self.verticalLayout.addWidget(self.LoginDataFrame)

        self.FNSButtonFrame = QFrame(self.LoginPasswordTab)
        self.FNSButtonFrame.setObjectName(u"FNSButtonFrame")
        self.FNSButtonFrame.setFrameShape(QFrame.NoFrame)
        self.FNSButtonFrame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_4 = QVBoxLayout(self.FNSButtonFrame)
        self.verticalLayout_4.setSpacing(6)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 6)
        self.frame = QFrame(self.FNSButtonFrame)
        self.frame.setObjectName(u"frame")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy1)
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_5 = QVBoxLayout(self.frame)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.FNSLoginBtn = QPushButton(self.frame)
        self.FNSLoginBtn.setObjectName(u"FNSLoginBtn")
        sizePolicy2 = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.FNSLoginBtn.sizePolicy().hasHeightForWidth())
        self.FNSLoginBtn.setSizePolicy(sizePolicy2)

        self.verticalLayout_5.addWidget(self.FNSLoginBtn, 0, Qt.AlignHCenter|Qt.AlignTop)


        self.verticalLayout_4.addWidget(self.frame)

        self.FNSSplitLine = QFrame(self.FNSButtonFrame)
        self.FNSSplitLine.setObjectName(u"FNSSplitLine")
        self.FNSSplitLine.setFrameShape(QFrame.HLine)
        self.FNSSplitLine.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_4.addWidget(self.FNSSplitLine)

        self.FNSCloseBtn = QPushButton(self.FNSButtonFrame)
        self.FNSCloseBtn.setObjectName(u"FNSCloseBtn")
        sizePolicy2.setHeightForWidth(self.FNSCloseBtn.sizePolicy().hasHeightForWidth())
        self.FNSCloseBtn.setSizePolicy(sizePolicy2)

        self.verticalLayout_4.addWidget(self.FNSCloseBtn, 0, Qt.AlignHCenter)


        self.verticalLayout.addWidget(self.FNSButtonFrame)

        self.LoginMethodTabs.addTab(self.LoginPasswordTab, "")
        self.ESIATab = QWidget()
        self.ESIATab.setObjectName(u"ESIATab")
        self.verticalLayout_2 = QVBoxLayout(self.ESIATab)
        self.verticalLayout_2.setSpacing(2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.ESIAWebView = QWebEngineView(self.ESIATab)
        self.ESIAWebView.setObjectName(u"ESIAWebView")
        sizePolicy1.setHeightForWidth(self.ESIAWebView.sizePolicy().hasHeightForWidth())
        self.ESIAWebView.setSizePolicy(sizePolicy1)
        self.ESIAWebView.setUrl(QUrl(u"about:blank"))

        self.verticalLayout_2.addWidget(self.ESIAWebView)

        self.ESIAButtonFrame = QFrame(self.ESIATab)
        self.ESIAButtonFrame.setObjectName(u"ESIAButtonFrame")
        self.ESIAButtonFrame.setFrameShape(QFrame.NoFrame)
        self.ESIAButtonFrame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_6 = QVBoxLayout(self.ESIAButtonFrame)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 6)
        self.ESIASplitLine = QFrame(self.ESIAButtonFrame)
        self.ESIASplitLine.setObjectName(u"ESIASplitLine")
        self.ESIASplitLine.setFrameShape(QFrame.HLine)
        self.ESIASplitLine.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_6.addWidget(self.ESIASplitLine)

        self.ESIACloseBtn = QPushButton(self.ESIAButtonFrame)
        self.ESIACloseBtn.setObjectName(u"ESIACloseBtn")
        sizePolicy2.setHeightForWidth(self.ESIACloseBtn.sizePolicy().hasHeightForWidth())
        self.ESIACloseBtn.setSizePolicy(sizePolicy2)

        self.verticalLayout_6.addWidget(self.ESIACloseBtn, 0, Qt.AlignHCenter)


        self.verticalLayout_2.addWidget(self.ESIAButtonFrame)

        self.LoginMethodTabs.addTab(self.ESIATab, "")

        self.verticalLayout_3.addWidget(self.LoginMethodTabs)


        self.retranslateUi(LoginFNSDialog)
        self.FNSCloseBtn.clicked.connect(LoginFNSDialog.close)
        self.ESIACloseBtn.clicked.connect(LoginFNSDialog.close)

        self.LoginMethodTabs.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(LoginFNSDialog)
    # setupUi

    def retranslateUi(self, LoginFNSDialog):
        LoginFNSDialog.setWindowTitle(QCoreApplication.translate("LoginFNSDialog", u"Authorization FNS", None))
        self.InnLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"INN:", None))
        self.PasswordLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"Password:", None))
        self.FNSLoginBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Login", None))
        self.FNSCloseBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Close", None))
        self.LoginMethodTabs.setTabText(self.LoginMethodTabs.indexOf(self.LoginPasswordTab), QCoreApplication.translate("LoginFNSDialog", u"FNS Login", None))
        self.ESIACloseBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Close", None))
        self.LoginMethodTabs.setTabText(self.LoginMethodTabs.indexOf(self.ESIATab), QCoreApplication.translate("LoginFNSDialog", u"ESIA Login", None))
    # retranslateUi

