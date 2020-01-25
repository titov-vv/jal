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
        AccountChoiceDlg.resize(869, 300)
        self.verticalLayout = QVBoxLayout(AccountChoiceDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.frame = QFrame(AccountChoiceDlg)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
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

        self.ShowInactive = QCheckBox(self.frame)
        self.ShowInactive.setObjectName(u"ShowInactive")
        self.ShowInactive.setChecked(False)

        self.horizontalLayout.addWidget(self.ShowInactive)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.AddAccountBtn = QPushButton(self.frame)
        self.AddAccountBtn.setObjectName(u"AddAccountBtn")

        self.horizontalLayout.addWidget(self.AddAccountBtn)

        self.RemoveAccountBtn = QPushButton(self.frame)
        self.RemoveAccountBtn.setObjectName(u"RemoveAccountBtn")

        self.horizontalLayout.addWidget(self.RemoveAccountBtn)


        self.verticalLayout.addWidget(self.frame)

        self.AccountsList = QTableView(AccountChoiceDlg)
        self.AccountsList.setObjectName(u"AccountsList")
        self.AccountsList.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed)
        self.AccountsList.setAlternatingRowColors(True)
        self.AccountsList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.AccountsList.verticalHeader().setVisible(False)
        self.AccountsList.verticalHeader().setMinimumSectionSize(20)
        self.AccountsList.verticalHeader().setDefaultSectionSize(20)

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
        self.ShowInactive.setText(QCoreApplication.translate("AccountChoiceDlg", u"Show inactive", None))
        self.AddAccountBtn.setText(QCoreApplication.translate("AccountChoiceDlg", u"Add", None))
        self.RemoveAccountBtn.setText(QCoreApplication.translate("AccountChoiceDlg", u"Del", None))
    # retranslateUi

