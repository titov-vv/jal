# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login_pingo_doce_dlg.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QLabel, QLineEdit,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_LoginPingoDoceDialog(object):
    def setupUi(self, LoginPingoDoceDialog):
        if not LoginPingoDoceDialog.objectName():
            LoginPingoDoceDialog.setObjectName(u"LoginPingoDoceDialog")
        LoginPingoDoceDialog.resize(296, 130)
        self.verticalLayout_3 = QVBoxLayout(LoginPingoDoceDialog)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.PhoneNumberFrame = QFrame(LoginPingoDoceDialog)
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
        self.PhoneNumberEdit.setInputMask(u"+351-999-999-999;_")

        self.formLayout_2.setWidget(0, QFormLayout.ItemRole.FieldRole, self.PhoneNumberEdit)


        self.verticalLayout_3.addWidget(self.PhoneNumberFrame)

        self.PasswordFrame = QFrame(LoginPingoDoceDialog)
        self.PasswordFrame.setObjectName(u"PasswordFrame")
        self.PasswordFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.formLayout_3 = QFormLayout(self.PasswordFrame)
        self.formLayout_3.setObjectName(u"formLayout_3")
        self.formLayout_3.setContentsMargins(6, -1, 6, 0)
        self.PasswordLbl = QLabel(self.PasswordFrame)
        self.PasswordLbl.setObjectName(u"PasswordLbl")

        self.formLayout_3.setWidget(0, QFormLayout.ItemRole.LabelRole, self.PasswordLbl)

        self.PasswordEdit = QLineEdit(self.PasswordFrame)
        self.PasswordEdit.setObjectName(u"PasswordEdit")
        self.PasswordEdit.setEchoMode(QLineEdit.EchoMode.Password)

        self.formLayout_3.setWidget(0, QFormLayout.ItemRole.FieldRole, self.PasswordEdit)


        self.verticalLayout_3.addWidget(self.PasswordFrame)

        self.frame = QFrame(LoginPingoDoceDialog)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalLayout_9 = QVBoxLayout(self.frame)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.DialogButtonBox = QDialogButtonBox(self.frame)
        self.DialogButtonBox.setObjectName(u"DialogButtonBox")
        self.DialogButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.DialogButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel)

        self.verticalLayout_9.addWidget(self.DialogButtonBox, 0, Qt.AlignmentFlag.AlignTop)


        self.verticalLayout_3.addWidget(self.frame)

#if QT_CONFIG(shortcut)
        self.PhoneLbl.setBuddy(self.PhoneNumberEdit)
        self.PasswordLbl.setBuddy(self.PasswordEdit)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.PhoneNumberEdit, self.PasswordEdit)
        QWidget.setTabOrder(self.PasswordEdit, self.DialogButtonBox)

        self.retranslateUi(LoginPingoDoceDialog)
        self.DialogButtonBox.rejected.connect(LoginPingoDoceDialog.reject)

        QMetaObject.connectSlotsByName(LoginPingoDoceDialog)
    # setupUi

    def retranslateUi(self, LoginPingoDoceDialog):
        LoginPingoDoceDialog.setWindowTitle(QCoreApplication.translate("LoginPingoDoceDialog", u"Authorization Pingo Doce", None))
        self.PhoneLbl.setText(QCoreApplication.translate("LoginPingoDoceDialog", u"Phone number:", None))
        self.PhoneNumberEdit.setText(QCoreApplication.translate("LoginPingoDoceDialog", u"+351---", None))
        self.PasswordLbl.setText(QCoreApplication.translate("LoginPingoDoceDialog", u"Password:", None))
        self.PasswordEdit.setInputMask("")
        self.PasswordEdit.setText("")
    # retranslateUi

