# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login_fns_dlg.ui'
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
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpacerItem, QTabWidget,
    QVBoxLayout, QWidget)

class Ui_LoginFNSDialog(object):
    def setupUi(self, LoginFNSDialog):
        if not LoginFNSDialog.objectName():
            LoginFNSDialog.setObjectName(u"LoginFNSDialog")
        LoginFNSDialog.resize(400, 500)
        self.verticalLayout_3 = QVBoxLayout(LoginFNSDialog)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.LoginMethodTabs = QTabWidget(LoginFNSDialog)
        self.LoginMethodTabs.setObjectName(u"LoginMethodTabs")
        self.LoginSMSTab = QWidget()
        self.LoginSMSTab.setObjectName(u"LoginSMSTab")
        self.verticalLayout_7 = QVBoxLayout(self.LoginSMSTab)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.PhoneNumberFrame = QFrame(self.LoginSMSTab)
        self.PhoneNumberFrame.setObjectName(u"PhoneNumberFrame")
        self.PhoneNumberFrame.setFrameShape(QFrame.Shape.NoFrame)
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
        self.CodeButtonFrame.setFrameShape(QFrame.Shape.NoFrame)
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

        self.verticalLayout_8.addWidget(self.GetCodeBtn, 0, Qt.AlignmentFlag.AlignHCenter)


        self.verticalLayout_7.addWidget(self.CodeButtonFrame)

        self.CodeFrame = QFrame(self.LoginSMSTab)
        self.CodeFrame.setObjectName(u"CodeFrame")
        self.CodeFrame.setFrameShape(QFrame.Shape.NoFrame)
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
        self.SMSButtonFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalLayout_10 = QVBoxLayout(self.SMSButtonFrame)
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.verticalLayout_10.setContentsMargins(0, 0, 0, 6)
        self.SMSButtonSpacer = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_10.addItem(self.SMSButtonSpacer)

        self.line = QFrame(self.SMSButtonFrame)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_10.addWidget(self.line)

        self.SMSButtonBox = QDialogButtonBox(self.SMSButtonFrame)
        self.SMSButtonBox.setObjectName(u"SMSButtonBox")
        self.SMSButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.SMSButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.verticalLayout_10.addWidget(self.SMSButtonBox)


        self.verticalLayout_7.addWidget(self.SMSButtonFrame)

        self.LoginMethodTabs.addTab(self.LoginSMSTab, "")
        self.LoginPasswordTab = QWidget()
        self.LoginPasswordTab.setObjectName(u"LoginPasswordTab")
        self.verticalLayout = QVBoxLayout(self.LoginPasswordTab)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.LoginDataFrame = QFrame(self.LoginPasswordTab)
        self.LoginDataFrame.setObjectName(u"LoginDataFrame")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.LoginDataFrame.sizePolicy().hasHeightForWidth())
        self.LoginDataFrame.setSizePolicy(sizePolicy2)
        self.LoginDataFrame.setFrameShape(QFrame.Shape.NoFrame)
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
        self.PasswordEdit.setEchoMode(QLineEdit.EchoMode.Password)

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.PasswordEdit)


        self.verticalLayout.addWidget(self.LoginDataFrame)

        self.FNSButtonFrame = QFrame(self.LoginPasswordTab)
        self.FNSButtonFrame.setObjectName(u"FNSButtonFrame")
        self.FNSButtonFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalLayout_4 = QVBoxLayout(self.FNSButtonFrame)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 6)
        self.FNSButtonSpacer = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_4.addItem(self.FNSButtonSpacer)

        self.FNSSplitLine = QFrame(self.FNSButtonFrame)
        self.FNSSplitLine.setObjectName(u"FNSSplitLine")
        self.FNSSplitLine.setFrameShape(QFrame.Shape.HLine)
        self.FNSSplitLine.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_4.addWidget(self.FNSSplitLine)

        self.FNSButtonBox = QDialogButtonBox(self.FNSButtonFrame)
        self.FNSButtonBox.setObjectName(u"FNSButtonBox")
        self.FNSButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.FNSButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.verticalLayout_4.addWidget(self.FNSButtonBox)


        self.verticalLayout.addWidget(self.FNSButtonFrame)

        self.LoginMethodTabs.addTab(self.LoginPasswordTab, "")
        self.ESIATab = QWidget()
        self.ESIATab.setObjectName(u"ESIATab")
        self.verticalLayout_2 = QVBoxLayout(self.ESIATab)
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
        self.ESIAButtonFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalLayout_6 = QVBoxLayout(self.ESIAButtonFrame)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 6)
        self.ESIASplitLine = QFrame(self.ESIAButtonFrame)
        self.ESIASplitLine.setObjectName(u"ESIASplitLine")
        self.ESIASplitLine.setFrameShape(QFrame.Shape.HLine)
        self.ESIASplitLine.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_6.addWidget(self.ESIASplitLine)

        self.ESIAButtonBox = QDialogButtonBox(self.ESIAButtonFrame)
        self.ESIAButtonBox.setObjectName(u"ESIAButtonBox")
        self.ESIAButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.ESIAButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.verticalLayout_6.addWidget(self.ESIAButtonBox)


        self.verticalLayout_2.addWidget(self.ESIAButtonFrame)

        self.LoginMethodTabs.addTab(self.ESIATab, "")

        self.verticalLayout_3.addWidget(self.LoginMethodTabs)

#if QT_CONFIG(shortcut)
        self.PhoneLbl.setBuddy(self.PhoneNumberEdit)
        self.CodeLbl.setBuddy(self.CodeEdit)
        self.InnLbl.setBuddy(self.InnEdit)
        self.PasswordLbl.setBuddy(self.PasswordEdit)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.LoginMethodTabs, self.PhoneNumberEdit)
        QWidget.setTabOrder(self.PhoneNumberEdit, self.GetCodeBtn)
        QWidget.setTabOrder(self.GetCodeBtn, self.CodeEdit)
        QWidget.setTabOrder(self.CodeEdit, self.SMSButtonBox)
        QWidget.setTabOrder(self.SMSButtonBox, self.InnEdit)
        QWidget.setTabOrder(self.InnEdit, self.PasswordEdit)
        QWidget.setTabOrder(self.PasswordEdit, self.FNSButtonBox)
        QWidget.setTabOrder(self.FNSButtonBox, self.ESIAWebView)
        QWidget.setTabOrder(self.ESIAWebView, self.ESIAButtonBox)

        self.retranslateUi(LoginFNSDialog)
        self.FNSButtonBox.rejected.connect(LoginFNSDialog.reject)
        self.SMSButtonBox.rejected.connect(LoginFNSDialog.reject)
        self.ESIAButtonBox.rejected.connect(LoginFNSDialog.reject)

        self.LoginMethodTabs.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(LoginFNSDialog)
    # setupUi

    def retranslateUi(self, LoginFNSDialog):
        LoginFNSDialog.setWindowTitle(QCoreApplication.translate("LoginFNSDialog", u"Authorization FNS", None))
        self.PhoneLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"&Phone number:", None))
        self.GetCodeBtn.setText(QCoreApplication.translate("LoginFNSDialog", u"Send SMS with code", None))
        self.CodeLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"&Code from SMS:", None))
        self.LoginMethodTabs.setTabText(self.LoginMethodTabs.indexOf(self.LoginSMSTab), QCoreApplication.translate("LoginFNSDialog", u"SMS Login", None))
        self.InnLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"&INN:", None))
        self.PasswordLbl.setText(QCoreApplication.translate("LoginFNSDialog", u"P&assword:", None))
        self.LoginMethodTabs.setTabText(self.LoginMethodTabs.indexOf(self.LoginPasswordTab), QCoreApplication.translate("LoginFNSDialog", u"FNS Login", None))
        self.LoginMethodTabs.setTabText(self.LoginMethodTabs.indexOf(self.ESIATab), QCoreApplication.translate("LoginFNSDialog", u"ESIA Login", None))
    # retranslateUi

