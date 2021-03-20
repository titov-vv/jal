# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'add_asset_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_AddAssetDialog(object):
    def setupUi(self, AddAssetDialog):
        if not AddAssetDialog.objectName():
            AddAssetDialog.setObjectName(u"AddAssetDialog")
        AddAssetDialog.setWindowModality(Qt.ApplicationModal)
        AddAssetDialog.resize(400, 198)
        AddAssetDialog.setModal(False)
        self.gridLayout = QGridLayout(AddAssetDialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.isinEdit = QLineEdit(AddAssetDialog)
        self.isinEdit.setObjectName(u"isinEdit")

        self.gridLayout.addWidget(self.isinEdit, 3, 1, 1, 1)

        self.buttonBox = QDialogButtonBox(AddAssetDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Save)

        self.gridLayout.addWidget(self.buttonBox, 5, 1, 1, 1)

        self.SymbolLbl = QLabel(AddAssetDialog)
        self.SymbolLbl.setObjectName(u"SymbolLbl")

        self.gridLayout.addWidget(self.SymbolLbl, 0, 0, 1, 1)

        self.NameEdit = QLineEdit(AddAssetDialog)
        self.NameEdit.setObjectName(u"NameEdit")

        self.gridLayout.addWidget(self.NameEdit, 1, 1, 1, 1)

        self.TypeCombo = QComboBox(AddAssetDialog)
        self.TypeCombo.setObjectName(u"TypeCombo")

        self.gridLayout.addWidget(self.TypeCombo, 2, 1, 1, 1)

        self.SymbolEdit = QLineEdit(AddAssetDialog)
        self.SymbolEdit.setObjectName(u"SymbolEdit")
        self.SymbolEdit.setReadOnly(False)

        self.gridLayout.addWidget(self.SymbolEdit, 0, 1, 1, 1)

        self.NameLbl = QLabel(AddAssetDialog)
        self.NameLbl.setObjectName(u"NameLbl")

        self.gridLayout.addWidget(self.NameLbl, 1, 0, 1, 1)

        self.TypeLbl = QLabel(AddAssetDialog)
        self.TypeLbl.setObjectName(u"TypeLbl")

        self.gridLayout.addWidget(self.TypeLbl, 2, 0, 1, 1)

        self.DataSrcCombo = QComboBox(AddAssetDialog)
        self.DataSrcCombo.setObjectName(u"DataSrcCombo")

        self.gridLayout.addWidget(self.DataSrcCombo, 4, 1, 1, 1)

        self.isinLbl = QLabel(AddAssetDialog)
        self.isinLbl.setObjectName(u"isinLbl")

        self.gridLayout.addWidget(self.isinLbl, 3, 0, 1, 1)

        self.DataSrcLbl = QLabel(AddAssetDialog)
        self.DataSrcLbl.setObjectName(u"DataSrcLbl")

        self.gridLayout.addWidget(self.DataSrcLbl, 4, 0, 1, 1)

        QWidget.setTabOrder(self.NameEdit, self.TypeCombo)
        QWidget.setTabOrder(self.TypeCombo, self.isinEdit)
        QWidget.setTabOrder(self.isinEdit, self.DataSrcCombo)
        QWidget.setTabOrder(self.DataSrcCombo, self.SymbolEdit)

        self.retranslateUi(AddAssetDialog)
        self.buttonBox.accepted.connect(AddAssetDialog.accept)

        QMetaObject.connectSlotsByName(AddAssetDialog)
    # setupUi

    def retranslateUi(self, AddAssetDialog):
        AddAssetDialog.setWindowTitle(QCoreApplication.translate("AddAssetDialog", u"Add new asset", None))
        self.SymbolLbl.setText(QCoreApplication.translate("AddAssetDialog", u"Symbol:", None))
        self.NameLbl.setText(QCoreApplication.translate("AddAssetDialog", u"Name:", None))
        self.TypeLbl.setText(QCoreApplication.translate("AddAssetDialog", u"Type:", None))
        self.isinLbl.setText(QCoreApplication.translate("AddAssetDialog", u"ISIN", None))
        self.DataSrcLbl.setText(QCoreApplication.translate("AddAssetDialog", u"Quotes source:", None))
    # retranslateUi

