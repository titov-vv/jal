# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'active_choice_dlg.ui'
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

class Ui_ActiveChoiceDlg(object):
    def setupUi(self, ActiveChoiceDlg):
        if ActiveChoiceDlg.objectName():
            ActiveChoiceDlg.setObjectName(u"ActiveChoiceDlg")
        ActiveChoiceDlg.resize(870, 300)
        self.verticalLayout = QVBoxLayout(ActiveChoiceDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.frame = QFrame(ActiveChoiceDlg)
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
        self.ActiveTypeLbl = QLabel(self.frame)
        self.ActiveTypeLbl.setObjectName(u"ActiveTypeLbl")

        self.horizontalLayout.addWidget(self.ActiveTypeLbl)

        self.ActiveTypeCombo = QComboBox(self.frame)
        self.ActiveTypeCombo.setObjectName(u"ActiveTypeCombo")

        self.horizontalLayout.addWidget(self.ActiveTypeCombo)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.AddActiveBtn = QPushButton(self.frame)
        self.AddActiveBtn.setObjectName(u"AddActiveBtn")

        self.horizontalLayout.addWidget(self.AddActiveBtn)

        self.RemoveActiveBtn = QPushButton(self.frame)
        self.RemoveActiveBtn.setObjectName(u"RemoveActiveBtn")

        self.horizontalLayout.addWidget(self.RemoveActiveBtn)


        self.verticalLayout.addWidget(self.frame)

        self.ActivesList = QTableView(ActiveChoiceDlg)
        self.ActivesList.setObjectName(u"ActivesList")
        self.ActivesList.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed)
        self.ActivesList.setAlternatingRowColors(True)
        self.ActivesList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ActivesList.verticalHeader().setVisible(False)
        self.ActivesList.verticalHeader().setMinimumSectionSize(20)
        self.ActivesList.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.ActivesList)

        self.buttonBox = QDialogButtonBox(ActiveChoiceDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(ActiveChoiceDlg)
        self.buttonBox.accepted.connect(ActiveChoiceDlg.accept)
        self.buttonBox.rejected.connect(ActiveChoiceDlg.reject)

        QMetaObject.connectSlotsByName(ActiveChoiceDlg)
    # setupUi

    def retranslateUi(self, ActiveChoiceDlg):
        ActiveChoiceDlg.setWindowTitle(QCoreApplication.translate("ActiveChoiceDlg", u"Choose Active", None))
        self.ActiveTypeLbl.setText(QCoreApplication.translate("ActiveChoiceDlg", u"Active Type:", None))
        self.AddActiveBtn.setText(QCoreApplication.translate("ActiveChoiceDlg", u"Add", None))
        self.RemoveActiveBtn.setText(QCoreApplication.translate("ActiveChoiceDlg", u"Del", None))
    # retranslateUi

