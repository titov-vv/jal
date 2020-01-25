# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'peer_choice_dlg.ui'
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

class Ui_PeerChoiceDlg(object):
    def setupUi(self, PeerChoiceDlg):
        if PeerChoiceDlg.objectName():
            PeerChoiceDlg.setObjectName(u"PeerChoiceDlg")
        PeerChoiceDlg.resize(598, 300)
        self.verticalLayout = QVBoxLayout(PeerChoiceDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.frame_2 = QFrame(PeerChoiceDlg)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.SearchString = QLineEdit(self.frame_2)
        self.SearchString.setObjectName(u"SearchString")

        self.horizontalLayout_2.addWidget(self.SearchString)

        self.BackBtn = QPushButton(self.frame_2)
        self.BackBtn.setObjectName(u"BackBtn")

        self.horizontalLayout_2.addWidget(self.BackBtn)


        self.verticalLayout.addWidget(self.frame_2)

        self.frame = QFrame(PeerChoiceDlg)
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
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.AddPeerBtn = QPushButton(self.frame)
        self.AddPeerBtn.setObjectName(u"AddPeerBtn")

        self.horizontalLayout.addWidget(self.AddPeerBtn)

        self.RemovePeerBtn = QPushButton(self.frame)
        self.RemovePeerBtn.setObjectName(u"RemovePeerBtn")

        self.horizontalLayout.addWidget(self.RemovePeerBtn)

        self.CommitBtn = QPushButton(self.frame)
        self.CommitBtn.setObjectName(u"CommitBtn")
        self.CommitBtn.setEnabled(False)

        self.horizontalLayout.addWidget(self.CommitBtn)

        self.RevertBtn = QPushButton(self.frame)
        self.RevertBtn.setObjectName(u"RevertBtn")
        self.RevertBtn.setEnabled(False)

        self.horizontalLayout.addWidget(self.RevertBtn)


        self.verticalLayout.addWidget(self.frame)

        self.PeersList = QTableView(PeerChoiceDlg)
        self.PeersList.setObjectName(u"PeersList")
        self.PeersList.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed)
        self.PeersList.setAlternatingRowColors(True)
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
        self.BackBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Back", None))
        self.AddPeerBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Add", None))
        self.RemovePeerBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Del", None))
        self.CommitBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Commit", None))
        self.RevertBtn.setText(QCoreApplication.translate("PeerChoiceDlg", u"Revert", None))
    # retranslateUi

