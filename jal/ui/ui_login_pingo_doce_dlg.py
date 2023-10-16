# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login_pingo_doce_dlg.ui'
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
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QFrame,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_LoginPingoDoceDialog(object):
    def setupUi(self, LoginPingoDoceDialog):
        if not LoginPingoDoceDialog.objectName():
            LoginPingoDoceDialog.setObjectName(u"LoginPingoDoceDialog")
        LoginPingoDoceDialog.resize(296, 130)
        self.verticalLayout_3 = QVBoxLayout(LoginPingoDoceDialog)
        self.verticalLayout_3.setSpacing(6)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(2, 2, 2, 2)
        self.PhoneNumberFrame = QFrame(LoginPingoDoceDialog)
        self.PhoneNumberFrame.setObjectName(u"PhoneNumberFrame")
        self.PhoneNumberFrame.setFrameShape(QFrame.NoFrame)
        self.PhoneNumberFrame.setFrameShadow(QFrame.Plain)
        self.formLayout_2 = QFormLayout(self.PhoneNumberFrame)
        self.formLayout_2.setObjectName(u"formLayout_2")
        self.formLayout_2.setContentsMargins(6, -1, 6, 0)
        self.PhoneLbl = QLabel(self.PhoneNumberFrame)
        self.PhoneLbl.setObjectName(u"PhoneLbl")

        self.formLayout_2.setWidget(0, QFormLayout.LabelRole, self.PhoneLbl)

        self.PhoneNumberEdit = QLineEdit(self.PhoneNumberFrame)
        self.PhoneNumberEdit.setObjectName(u"PhoneNumberEdit")
        self.PhoneNumberEdit.setInputMask(u"+351-999-999-999;_")

        self.formLayout_2.setWidget(0, QFormLayout.FieldRole, self.PhoneNumberEdit)


        self.verticalLayout_3.addWidget(self.PhoneNumberFrame)

        self.PasswordFrame = QFrame(LoginPingoDoceDialog)
        self.PasswordFrame.setObjectName(u"PasswordFrame")
        self.PasswordFrame.setFrameShape(QFrame.NoFrame)
        self.PasswordFrame.setFrameShadow(QFrame.Plain)
        self.formLayout_3 = QFormLayout(self.PasswordFrame)
        self.formLayout_3.setObjectName(u"formLayout_3")
        self.formLayout_3.setContentsMargins(6, -1, 6, 0)
        self.PasswordLbl = QLabel(self.PasswordFrame)
        self.PasswordLbl.setObjectName(u"PasswordLbl")

        self.formLayout_3.setWidget(0, QFormLayout.LabelRole, self.PasswordLbl)

        self.PasswordEdit = QLineEdit(self.PasswordFrame)
        self.PasswordEdit.setObjectName(u"PasswordEdit")
        self.PasswordEdit.setEchoMode(QLineEdit.Password)

        self.formLayout_3.setWidget(0, QFormLayout.FieldRole, self.PasswordEdit)


        self.verticalLayout_3.addWidget(self.PasswordFrame)

        self.frame = QFrame(LoginPingoDoceDialog)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_9 = QVBoxLayout(self.frame)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.LoginBtn = QPushButton(self.frame)
        self.LoginBtn.setObjectName(u"LoginBtn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.LoginBtn.sizePolicy().hasHeightForWidth())
        self.LoginBtn.setSizePolicy(sizePolicy1)

        self.verticalLayout_9.addWidget(self.LoginBtn, 0, Qt.AlignHCenter|Qt.AlignTop)


        self.verticalLayout_3.addWidget(self.frame)


        self.retranslateUi(LoginPingoDoceDialog)

        QMetaObject.connectSlotsByName(LoginPingoDoceDialog)
    # setupUi

    def retranslateUi(self, LoginPingoDoceDialog):
        LoginPingoDoceDialog.setWindowTitle(QCoreApplication.translate("LoginPingoDoceDialog", u"Authorization Pingo Doce", None))
        self.PhoneLbl.setText(QCoreApplication.translate("LoginPingoDoceDialog", u"Phone number:", None))
        self.PhoneNumberEdit.setText(QCoreApplication.translate("LoginPingoDoceDialog", u"+351---", None))
        self.PasswordLbl.setText(QCoreApplication.translate("LoginPingoDoceDialog", u"Password:", None))
        self.PasswordEdit.setInputMask("")
        self.PasswordEdit.setText("")
        self.LoginBtn.setText(QCoreApplication.translate("LoginPingoDoceDialog", u"Login", None))
    # retranslateUi

