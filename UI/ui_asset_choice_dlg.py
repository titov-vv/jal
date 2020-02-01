# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'asset_choice_dlg.ui'
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


class Ui_AssetChoiceDlg(object):
    def setupUi(self, AssetChoiceDlg):
        if AssetChoiceDlg.objectName():
            AssetChoiceDlg.setObjectName(u"AssetChoiceDlg")
        AssetChoiceDlg.resize(870, 300)
        self.verticalLayout = QVBoxLayout(AssetChoiceDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.frame = QFrame(AssetChoiceDlg)
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
        self.AssetTypeLbl = QLabel(self.frame)
        self.AssetTypeLbl.setObjectName(u"AssetTypeLbl")

        self.horizontalLayout.addWidget(self.AssetTypeLbl)

        self.AssetTypeCombo = QComboBox(self.frame)
        self.AssetTypeCombo.setObjectName(u"AssetTypeCombo")

        self.horizontalLayout.addWidget(self.AssetTypeCombo)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.AddAssetBtn = QPushButton(self.frame)
        self.AddAssetBtn.setObjectName(u"AddAssetBtn")

        self.horizontalLayout.addWidget(self.AddAssetBtn)

        self.RemoveAssetBtn = QPushButton(self.frame)
        self.RemoveAssetBtn.setObjectName(u"RemoveAssetBtn")

        self.horizontalLayout.addWidget(self.RemoveAssetBtn)

        self.CommitBtn = QPushButton(self.frame)
        self.CommitBtn.setObjectName(u"CommitBtn")
        self.CommitBtn.setEnabled(False)

        self.horizontalLayout.addWidget(self.CommitBtn)

        self.RevertBtn = QPushButton(self.frame)
        self.RevertBtn.setObjectName(u"RevertBtn")
        self.RevertBtn.setEnabled(False)

        self.horizontalLayout.addWidget(self.RevertBtn)


        self.verticalLayout.addWidget(self.frame)

        self.AssetsList = QTableView(AssetChoiceDlg)
        self.AssetsList.setObjectName(u"AssetsList")
        self.AssetsList.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed)
        self.AssetsList.setAlternatingRowColors(True)
        self.AssetsList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.AssetsList.verticalHeader().setVisible(True)
        self.AssetsList.verticalHeader().setMinimumSectionSize(20)
        self.AssetsList.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.AssetsList)

        self.buttonBox = QDialogButtonBox(AssetChoiceDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(AssetChoiceDlg)
        self.buttonBox.accepted.connect(AssetChoiceDlg.accept)
        self.buttonBox.rejected.connect(AssetChoiceDlg.reject)

        QMetaObject.connectSlotsByName(AssetChoiceDlg)
    # setupUi

    def retranslateUi(self, AssetChoiceDlg):
        AssetChoiceDlg.setWindowTitle(QCoreApplication.translate("AssetChoiceDlg", u"Choose Asset", None))
        self.AssetTypeLbl.setText(QCoreApplication.translate("AssetChoiceDlg", u"Asset Type:", None))
        self.AddAssetBtn.setText(QCoreApplication.translate("AssetChoiceDlg", u"Add", None))
        self.RemoveAssetBtn.setText(QCoreApplication.translate("AssetChoiceDlg", u"Del", None))
        self.CommitBtn.setText(QCoreApplication.translate("AssetChoiceDlg", u"Commit", None))
        self.RevertBtn.setText(QCoreApplication.translate("AssetChoiceDlg", u"Revert", None))
    # retranslateUi

