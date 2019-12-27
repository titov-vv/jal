# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'account_choice_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.14.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QMetaObject, QObject, QPoint,
    QRect, QSize, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QFont,
    QFontDatabase, QIcon, QLinearGradient, QPalette, QPainter, QPixmap,
    QRadialGradient)
from PySide2.QtWidgets import *

class Ui_AccountChoiceDlg(object):
    def setupUi(self, AccountChoiceDlg):
        if AccountChoiceDlg.objectName():
            AccountChoiceDlg.setObjectName(u"AccountChoiceDlg")
        AccountChoiceDlg.resize(400, 300)
        self.verticalLayout = QVBoxLayout(AccountChoiceDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(AccountChoiceDlg)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Panel)
        self.frame.setFrameShadow(QFrame.Plain)
        self.frame.setLineWidth(0)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.AccountTypeLbl = QLabel(self.frame)
        self.AccountTypeLbl.setObjectName(u"AccountTypeLbl")

        self.horizontalLayout.addWidget(self.AccountTypeLbl)

        self.AccountTypeCombo = QComboBox(self.frame)
        self.AccountTypeCombo.setObjectName(u"AccountTypeCombo")

        self.horizontalLayout.addWidget(self.AccountTypeCombo)


        self.verticalLayout.addWidget(self.frame)

        self.AccountsList = QTableView(AccountChoiceDlg)
        self.AccountsList.setObjectName(u"AccountsList")

        self.verticalLayout.addWidget(self.AccountsList)

        self.buttonBox = QDialogButtonBox(AccountChoiceDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(AccountChoiceDlg)
        self.buttonBox.accepted.connect(AccountChoiceDlg.accept)
        self.buttonBox.rejected.connect(AccountChoiceDlg.reject)

        QMetaObject.connectSlotsByName(AccountChoiceDlg)
    # setupUi

    def retranslateUi(self, AccountChoiceDlg):
        AccountChoiceDlg.setWindowTitle(QCoreApplication.translate("AccountChoiceDlg", u"Choose Account", None))
        self.AccountTypeLbl.setText(QCoreApplication.translate("AccountChoiceDlg", u"Account Type:", None))
    # retranslateUi

