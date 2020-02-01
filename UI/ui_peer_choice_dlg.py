# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'peer_choice_dlg.ui'
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


class Ui_PeerChoiceDlg(object):
    def setupUi(self, PeerChoiceDlg):
        if PeerChoiceDlg.objectName():
            PeerChoiceDlg.setObjectName(u"PeerChoiceDlg")
        PeerChoiceDlg.resize(598, 300)
        self.verticalLayout = QVBoxLayout(PeerChoiceDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.SearchFrame = QFrame(PeerChoiceDlg)
        self.SearchFrame.setObjectName(u"SearchFrame")
        self.SearchFrame.setFrameShape(QFrame.NoFrame)
        self.SearchFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.SearchFrame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.SearchLbl = QLabel(self.SearchFrame)
        self.SearchLbl.setObjectName(u"SearchLbl")

        self.horizontalLayout_2.addWidget(self.SearchLbl)

        self.SearchString = QLineEdit(self.SearchFrame)
        self.SearchString.setObjectName(u"SearchString")

        self.horizontalLayout_2.addWidget(self.SearchString)


        self.verticalLayout.addWidget(self.SearchFrame)

        self.EditFrame = QFrame(PeerChoiceDlg)
        self.EditFrame.setObjectName(u"EditFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.EditFrame.sizePolicy().hasHeightForWidth())
        self.EditFrame.setSizePolicy(sizePolicy)
        self.EditFrame.setFrameShape(QFrame.Panel)
        self.EditFrame.setFrameShadow(QFrame.Plain)
        self.EditFrame.setLineWidth(0)
        self.horizontalLayout = QHBoxLayout(self.EditFrame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.UpBtn = QPushButton(self.EditFrame)
        self.UpBtn.setObjectName(u"UpBtn")

        self.horizontalLayout.addWidget(self.UpBtn)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.AddPeerBtn = QPushButton(self.EditFrame)
        self.AddPeerBtn.setObjectName(u"AddPeerBtn")

        self.horizontalLayout.addWidget(self.AddPeerBtn)

        self.RemovePeerBtn = QPushButton(self.EditFrame)
        self.RemovePeerBtn.setObjectName(u"RemovePeerBtn")

        self.horizontalLayout.addWidget(self.RemovePeerBtn)

        self.CommitBtn = QPushButton(self.EditFrame)
        self.CommitBtn.setObjectName(u"CommitBtn")
        self.CommitBtn.setEnabled(False)

        self.horizontalLayout.addWidget(self.CommitBtn)

        self.RevertBtn = QPushButton(self.EditFrame)
        self.RevertBtn.setObjectName(u"RevertBtn")
        self.RevertBtn.setEnabled(False)

        self.horizontalLayout.addWidget(self.RevertBtn)


        self.verticalLayout.addWidget(self.EditFrame)

        self.PeersList = QTableView(PeerChoiceDlg)
        self.PeersList.setObjectName(u"PeersList")
        self.PeersList.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed)
        self.PeersList.setAlternatingRowColors(True)
        self.PeersList.horizontalHeader().setMinimumSectionSize(8)
        self.PeersList.verticalHeader().setVisible(True)
        self.PeersList.verticalHeader().setMinimumSectionSize(20)
        self.PeersList.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.PeersList)

        self.buttonBox = QDialogButtonBox(PeerChoiceDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(PeerChoiceDlg)
        self.buttonBox.accepted.connect(PeerChoiceDlg.accept)
        self.buttonBox.rejected.connect(PeerChoiceDlg.reject)

        QMetaObject.connectSlotsByName(PeerChoiceDlg)
    # setupUi

    def retranslateUi(self, PeerChoiceDlg):
        PeerChoiceDlg.setWindowTitle(QCoreApplication.translate("PeerChoiceDlg", u"Choose Peer", None))
        self.SearchLbl.setText(QCoreApplication.translate("PeerChoiceDlg", u"Search:", None))
        self.UpBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Up", None))
        self.AddPeerBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Add", None))
        self.RemovePeerBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Del", None))
        self.CommitBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Commit", None))
        self.RevertBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Revert", None))
    # retranslateUi

