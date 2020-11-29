# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'abort_window.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_AbortWindow(object):
    def setupUi(self, AbortWindow):
        if not AbortWindow.objectName():
            AbortWindow.setObjectName(u"AbortWindow")
        AbortWindow.resize(335, 66)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(AbortWindow.sizePolicy().hasHeightForWidth())
        AbortWindow.setSizePolicy(sizePolicy)
        self.centralwidget = QWidget(AbortWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralwidget.setLayoutDirection(Qt.LeftToRight)
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.MessageLbl = QLabel(self.centralwidget)
        self.MessageLbl.setObjectName(u"MessageLbl")
        sizePolicy.setHeightForWidth(self.MessageLbl.sizePolicy().hasHeightForWidth())
        self.MessageLbl.setSizePolicy(sizePolicy)

        self.verticalLayout.addWidget(self.MessageLbl)

        self.CloseBtn = QPushButton(self.centralwidget)
        self.CloseBtn.setObjectName(u"CloseBtn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.CloseBtn.sizePolicy().hasHeightForWidth())
        self.CloseBtn.setSizePolicy(sizePolicy1)
        self.CloseBtn.setLayoutDirection(Qt.LeftToRight)

        self.verticalLayout.addWidget(self.CloseBtn, 0, Qt.AlignHCenter)

        AbortWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(AbortWindow)
        self.CloseBtn.clicked.connect(AbortWindow.close)

        QMetaObject.connectSlotsByName(AbortWindow)
    # setupUi

    def retranslateUi(self, AbortWindow):
        AbortWindow.setWindowTitle(QCoreApplication.translate("AbortWindow", u"Ledger: Start-up aborted", None))
        self.MessageLbl.setText(QCoreApplication.translate("AbortWindow", u"TextLabel", None))
        self.CloseBtn.setText(QCoreApplication.translate("AbortWindow", u"Close", None))
    # retranslateUi

