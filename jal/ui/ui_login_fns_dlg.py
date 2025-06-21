# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login_fns_dlg.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
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
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QFrame,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QTabWidget, QVBoxLayout, QWidget)

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
        self.LoginSMSTab = QWidget()
        self.LoginSMSTab.setObjectName(u"LoginSMSTab")
        self.verticalLayout_7 = QVBoxLayout(self.LoginSMSTab)
        self.verticalLayout_7.setSpacing(2)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.PhoneNumberFrame = QFrame(self.LoginSMSTab)
        self.PhoneNumberFrame.setObjectName(u"PhoneNumberFrame")
        self.PhoneNumberFrame.setFrameShape(QFrame.NoFrame)
        self.PhoneNumberFrame.setFrameShadow(QFrame.Plain)
        self.formLayout_2 = QFormLayout(self.PhoneNumberFrame)
        self.formLayout_2.setObjectName(u"formLayout_2")
        self.formLayout_2.setContentsMargins(6, -1, 6, 0)
        self.PhoneLbl = QLabel(self.PhoneNumberFrame)
        self.PhoneLbl.setObjectName(u"PhoneLbl")

        self.formLayout_2.setWidget(0, QFormLayout.ItemRole.LabelRole, self.PhoneLbl)

        self.PhoneNumberEdit = QLineEdit(self.PhoneNumberFrame)
        self.PhoneNumberEdit.setObjectName(u"PhoneNumberEdit")
        self.PhoneNumberEdit.setInputMask(u"+7-999-999-99-99;_")

        self.formLayout_2.setWidget(0, QFormLayout.ItemRole.FieldRole, self.PhoneNumberEdit)


        self.verticalLayout_7.addWidget(self.PhoneNumberFrame)

        self.CodeButtonFrame = QFrame(self.LoginSMSTab)
        self.CodeButtonFrame.setObjectName(u"CodeButtonFrame")
        self.CodeButtonFrame.setFrameShape(QFrame.NoFrame)
        self.CodeButtonFrame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_8 = QVBoxLayout(self.CodeButtonFrame)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.verticalLayout_8.setContentsMargins(0, 6, 0, 0)
        self.GetCodeBtn = QPushButton(self.CodeButtonFrame)
        self.GetCodeBtn.setObjectName(u"GetCodeBtn")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.GetCodeBtn.sizePolicy().hasHeightForWidth())
        self.GetCodeBtn.setSizePolicy(sizePolicy)

        self.verticalLayout_8.addWidget(self.GetCodeBtn, 0, Qt.AlignHCenter)


        self.verticalLayout_7.addWidget(self.CodeButtonFrame)

        self.CodeFrame = QFrame(self.LoginSMSTab)
        self.CodeFrame.setObjectName(u"CodeFrame")
        self.CodeFrame.setFrameShape(QFrame.NoFrame)
        self.CodeFrame.setFrameShadow(QFrame.Plain)
        self.formLayout_3 = QFormLayout(self.CodeFrame)
        self.formLayout_3.setObjectName(u"formLayout_3")
        self.formLayout_3.setContentsMargins(6, -1, 6, 0)
        self.CodeLbl = QLabel(self.CodeFrame)
        self.CodeLbl.setObjectName(u"CodeLbl")

        self.formLayout_3.setWidget(0, QFormLayout.ItemRole.LabelRole, self.CodeLbl)

        self.CodeEdit = QLineEdit(self.CodeFrame)
        self.CodeEdit.setObjectName(u"CodeEdit")

        self.formLayout_3.setWidget(0, QFormLayout.ItemRole.FieldRole, self.CodeEdit)


        self.verticalLayout_7.addWidget(self.CodeFrame)

        self.SMSButtonFrame = QFrame(self.LoginSMSTab)
        self.SMSButtonFrame.setObjectName(u"SMSButtonFrame")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.SMSButtonFrame.sizePolicy().hasHeightForWidth())
        self.SMSButtonFrame.setSizePolicy(sizePolicy1)
        self.SMSButtonFrame.setFrameShape(QFrame.NoFrame)
        self.SMSButtonFrame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_10 = QVBoxLayout(self.SMSButtonFrame)
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.verticalLayout_10.setContentsMargins(0, 0, 0, 6)
        self.frame = QFrame(self.SMSButtonFrame)
        self.frame.setObjectName(u"frame")
        sizePolicy1.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy1)
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_9 = QVBoxLayout(self.frame)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.SMSLoginBtn = QPushButton(self.frame)
        self.SMSLoginBtn.setObjectName(u"SMSLoginBtn")
        sizePolicy.setHeightForWidth(self.SMSLoginBtn.sizePolicy().hasHeightForWidth())
        self.SMSLoginBtn.setSizePolicy(sizePolicy)

        self.verticalLayout_9.addWidget(self.SMSLoginBtn, 0, Qt.AlignHCenter|Qt.AlignTop)


        self.verticalLayout_10.addWidget(self.frame)

        self.line = QFrame(self.SMSButtonFrame)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_10.addWidget(self.line)

        self.SMSCloseBtn = QPushButton(self.SMSButtonFrame)
        self.SMSCloseBtn.setObjectName(u"SMSCloseBtn")
        sizePolicy.setHeightForWidth(self.SMSCloseBtn.sizePolicy().hasHeightForWidth())
        self.SMSCloseBtn.setSizePolicy(sizePolicy)

        self.verticalLayout_10.addWidget(self.SMSCloseBtn, 0, Qt.AlignHCenter)


        self.verticalLayout_7.addWidget(self.SMSButtonFrame)

        self.LoginMethodTabs.addTab(self.LoginSMSTab, "")
        self.LoginPasswordTab = QWidget()
        self.LoginPasswordTab.setObjectName(u"LoginPasswordTab")
        self.verticalLayout = QVBoxLayout(self.LoginPasswordTab)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.LoginDataFrame = QFrame(self.LoginPasswordTab)
        self.LoginDataFrame.setObjectName(u"LoginDataFrame")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.LoginDataFrame.sizePolicy().hasHeightForWidth())
        self.LoginDataFrame.setSizePolicy(sizePolicy2)
        self.LoginDataFrame.setFrameShape(QFrame.NoFrame)
        self.LoginDataFrame.setFrameShadow(QFrame.Plain)
        self.formLayout = QFormLayout(self.LoginDataFrame)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setHorizontalSpacing(6)
        self.formLayout.setContentsMargins(6, -1, 6, 0)
        self.InnLbl = QLabel(self.LoginDataFrame)
        self.InnLbl.setObjectName(u"InnLbl")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.InnLbl)

        self.InnEdit = QLineEdit(self.LoginDataFrame)
        self.InnEdit.setObjectName(u"InnEdit")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.InnEdit)

        self.PasswordLbl = QLabel(self.LoginDataFrame)
        self.PasswordLbl.setObjectName(u"PasswordLbl")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.PasswordLbl)

        self.PasswordEdit = QLineEdit(self.LoginDataFrame)
        self.PasswordEdit.setObjectName(u"PasswordEdit")
        self.PasswordEdit.setEchoMode(QLineEdit.Password)

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.PasswordEdit)


        self.verticalLayout.addWidget(self.LoginDataFrame)

        self.FNSButtonFrame = QFrame(self.LoginPasswordTab)
        self.FNSButtonFrame.setObjectName(u"FNSButtonFrame")
        self.FNSButtonFrame.setFrameShape(QFrame.NoFrame)
        self.FNSButtonFrame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_4 = QVBoxLayout(self.FNSButtonFrame)
        self.verticalLayout_4.setSpacing(6)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 6)
        self.FNSLoginFrame = QFrame(self.FNSButtonFrame)
        self.FNSLoginFrame.setObjectName(u"FNSLoginFrame")
        sizePolicy1.setHeightForWidth(self.FNSLoginFrame.sizePolicy().hasHeightForWidth())
        self.FNSLoginFrame.setSizePolicy(sizePolicy1)
        self.FNSLoginFrame.setFrameShape(QFrame.NoFrame)
        self.FNSLoginFrame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_5 = QVBoxLayout(self.FNSLoginFrame)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.FNSLoginBtn = QPushButton(self.FNSLoginFrame)
        self.FNSLoginBtn.setObjectName(u"FNSLoginBtn")
        sizePolicy.setHeightForWidth(self.FNSLoginBtn.sizePolicy().hasHeightForWidth())
        self.FNSLoginBtn.setSizePolicy(sizePolicy)

        self.verticalLayout_5.addWidget(self.FNSLoginBtn, 0, Qt.AlignHCenter|Qt.AlignTop)


        self.verticalLayout_4.addWidget(self.FNSLoginFrame)

        self.FNSSplitLine = QFrame(self.FNSButtonFrame)
        self.FNSSplitLine.setObjectName(u"FNSSplitLine")
        self.FNSSplitLine.setFrameShape(QFrame.Shape.HLine)
        self.FNSSplitLine.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_4.addWidget(self.FNSSplitLine)

        self.FNSCloseBtn = QPushButton(self.FNSButtonFrame)
        self.FNSCloseBtn.setObjectName(u"FNSCloseBtn")
        sizePolicy.setHeightForWidth(self.FNSCloseBtn.sizePolicy().hasHeightForWidth())
        self.FNSCloseBtn.setSizePolicy(sizePolicy)

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
        self.ESIASplitLine.setFrameShape(QFrame.Shape.HLine)
        self.ESIASplitLine.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_6.addWidget(self.ESIASplitLine)

        self.ESIACloseBtn = QPushButton(self.ESIAButtonFrame)
        self.ESIACloseBtn.setObjectName(u"ESIACloseBtn")
        sizePolicy.setHeightForWidth(self.ESIACloseBtn.sizePolicy().hasHeightForWidth())
        self.ESIACloseBtn.setSizePolicy(sizePolicy)

        self.verticalLayout_6.addWidget(self.ESIACloseBtn, 0, Qt.AlignHCenter)


        self.verticalLayout_2.addWidget(self.ESIAButtonFrame)

        self.LoginMethodTabs.addTab(self.ESIATab, "")

        self.verticalLayout_3.addWidget(self.LoginMethodTabs)


        self.retranslateUi(LoginFNSDialog)
        self.FNSCloseBtn.clicked.connect(LoginFNSDialog.close)
        self.ESIACloseBtn.clicked.connect(LoginFNSDialog.close)
        self.SMSCloseBtn.clicked.connect(LoginFNSDialog.close)

        self.LoginMethodTabs.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(LoginFNSDialog)
    # setupUi

    def retranslateUi(self, LoginFNSDialog):
        LoginFNSDialog.setWindowTitle(QCoreApplication.translate("LoginFNSDialog", u"Authorization FNS", None))
        self.PhoneLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"Phone number:", None))
        self.GetCodeBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Send SMS with code", None))
        self.CodeLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"Code from SMS:", None))
        self.SMSLoginBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Login", None))
        self.SMSCloseBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Close", None))
        self.LoginMethodTabs.setTabText(self.LoginMethodTabs.indexOf(self.LoginSMSTab), QCoreApplication.translate("LoginFNSDialog", u"SMS Login", None))
        self.InnLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"INN:", None))
        self.PasswordLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"Password:", None))
        self.FNSLoginBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Login", None))
        self.FNSCloseBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Close", None))
        self.LoginMethodTabs.setTabText(self.LoginMethodTabs.indexOf(self.LoginPasswordTab), QCoreApplication.translate("LoginFNSDialog", u"FNS Login", None))
        self.ESIACloseBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Close", None))
        self.LoginMethodTabs.setTabText(self.LoginMethodTabs.indexOf(self.ESIATab), QCoreApplication.translate("LoginFNSDialog", u"ESIA Login", None))
    # retranslateUi

