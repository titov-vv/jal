# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'account_type_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.14.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QMetaObject, QObject, QPoint,
    QRect, QSize, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QLinearGradient, QPalette, QPainter, QPixmap,
    QRadialGradient)
from PySide2.QtWidgets import *


class Ui_AccountTypesDlg(object):
    def setupUi(self, AccountTypesDlg):
        if AccountTypesDlg.objectName():
            AccountTypesDlg.setObjectName(u"AccountTypesDlg")
        AccountTypesDlg.resize(348, 300)
        self.verticalLayout = QVBoxLayout(AccountTypesDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.frame = QFrame(AccountTypesDlg)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Panel)
        self.frame.setFrameShadow(QFrame.Plain)
        self.frame.setLineWidth(0)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.AddAccTypeBtn = QPushButton(self.frame)
        self.AddAccTypeBtn.setObjectName(u"AddAccTypeBtn")

        self.horizontalLayout.addWidget(self.AddAccTypeBtn)

        self.RemoveAccTypeBtn = QPushButton(self.frame)
        self.RemoveAccTypeBtn.setObjectName(u"RemoveAccTypeBtn")

        self.horizontalLayout.addWidget(self.RemoveAccTypeBtn)

        self.CommitBtn = QPushButton(self.frame)
        self.CommitBtn.setObjectName(u"CommitBtn")

        self.horizontalLayout.addWidget(self.CommitBtn)

        self.RevertBtn = QPushButton(self.frame)
        self.RevertBtn.setObjectName(u"RevertBtn")

        self.horizontalLayout.addWidget(self.RevertBtn)


        self.verticalLayout.addWidget(self.frame)

        self.AccountTypeList = QTableView(AccountTypesDlg)
        self.AccountTypeList.setObjectName(u"AccountTypeList")
        self.AccountTypeList.verticalHeader().setMinimumSectionSize(20)
        self.AccountTypeList.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.AccountTypeList)

        self.buttonBox = QDialogButtonBox(AccountTypesDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(AccountTypesDlg)
        self.buttonBox.accepted.connect(AccountTypesDlg.accept)
        self.buttonBox.rejected.connect(AccountTypesDlg.reject)

        QMetaObject.connectSlotsByName(AccountTypesDlg)
    # setupUi

    def retranslateUi(self, AccountTypesDlg):
        AccountTypesDlg.setWindowTitle(QCoreApplication.translate("AccountTypesDlg", u"Dialog", None))
        self.AddAccTypeBtn.setText(QCoreApplication.translate("AccountTypesDlg", u"Add", None))
        self.RemoveAccTypeBtn.setText(QCoreApplication.translate("AccountTypesDlg", u"Del", None))
        self.CommitBtn.setText(QCoreApplication.translate("AccountTypesDlg", u"Commit", None))
        self.RevertBtn.setText(QCoreApplication.translate("AccountTypesDlg", u"Revert", None))
    # retranslateUi

