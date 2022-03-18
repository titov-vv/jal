# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'asset_dlg.ui'
##
## Created by: Qt User Interface Compiler version 6.2.3
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QTableView, QVBoxLayout, QWidget)

from jal.widgets.db_lookup_combobox import AssetTypeCombo

class Ui_AssetDialog(object):
    def setupUi(self, AssetDialog):
        if not AssetDialog.objectName():
            AssetDialog.setObjectName(u"AssetDialog")
        AssetDialog.setWindowModality(Qt.ApplicationModal)
        AssetDialog.resize(789, 375)
        AssetDialog.setModal(False)
        self.gridLayout = QGridLayout(AssetDialog)
        self.gridLayout.setSpacing(2)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.TypeLbl = QLabel(AssetDialog)
        self.TypeLbl.setObjectName(u"TypeLbl")

        self.gridLayout.addWidget(self.TypeLbl, 1, 2, 1, 1)

        self.TypeCombo = AssetTypeCombo(AssetDialog)
        self.TypeCombo.setObjectName(u"TypeCombo")

        self.gridLayout.addWidget(self.TypeCombo, 1, 3, 1, 1)

        self.NameLbl = QLabel(AssetDialog)
        self.NameLbl.setObjectName(u"NameLbl")

        self.gridLayout.addWidget(self.NameLbl, 0, 0, 1, 1)

        self.isinEdit = QLineEdit(AssetDialog)
        self.isinEdit.setObjectName(u"isinEdit")

        self.gridLayout.addWidget(self.isinEdit, 1, 1, 1, 1)

        self.NameEdit = QLineEdit(AssetDialog)
        self.NameEdit.setObjectName(u"NameEdit")

        self.gridLayout.addWidget(self.NameEdit, 0, 1, 1, 3)

        self.isinLbl = QLabel(AssetDialog)
        self.isinLbl.setObjectName(u"isinLbl")

        self.gridLayout.addWidget(self.isinLbl, 1, 0, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 9, 2, 1, 1)

        self.SymbolsBox = QGroupBox(AssetDialog)
        self.SymbolsBox.setObjectName(u"SymbolsBox")
        self.verticalLayout = QVBoxLayout(self.SymbolsBox)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.SymbolsEditWidget = QWidget(self.SymbolsBox)
        self.SymbolsEditWidget.setObjectName(u"SymbolsEditWidget")
        self.horizontalLayout_2 = QHBoxLayout(self.SymbolsEditWidget)
        self.horizontalLayout_2.setSpacing(2)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)

        self.AddSymbolButton = QPushButton(self.SymbolsEditWidget)
        self.AddSymbolButton.setObjectName(u"AddSymbolButton")

        self.horizontalLayout_2.addWidget(self.AddSymbolButton)

        self.RemoveSymbolButton = QPushButton(self.SymbolsEditWidget)
        self.RemoveSymbolButton.setObjectName(u"RemoveSymbolButton")

        self.horizontalLayout_2.addWidget(self.RemoveSymbolButton)


        self.verticalLayout.addWidget(self.SymbolsEditWidget)

        self.SymbolsTable = QTableView(self.SymbolsBox)
        self.SymbolsTable.setObjectName(u"SymbolsTable")
        self.SymbolsTable.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.EditKeyPressed|QAbstractItemView.SelectedClicked)
        self.SymbolsTable.setAlternatingRowColors(True)
        self.SymbolsTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.SymbolsTable.verticalHeader().setVisible(False)
        self.SymbolsTable.verticalHeader().setMinimumSectionSize(20)
        self.SymbolsTable.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.SymbolsTable)


        self.gridLayout.addWidget(self.SymbolsBox, 2, 0, 1, 2)

        self.BaseLbl = QLabel(AssetDialog)
        self.BaseLbl.setObjectName(u"BaseLbl")

        self.gridLayout.addWidget(self.BaseLbl, 3, 0, 1, 1)

        self.DataBox = QGroupBox(AssetDialog)
        self.DataBox.setObjectName(u"DataBox")
        self.verticalLayout_2 = QVBoxLayout(self.DataBox)
        self.verticalLayout_2.setSpacing(2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.DataEditWidget = QWidget(self.DataBox)
        self.DataEditWidget.setObjectName(u"DataEditWidget")
        self.horizontalLayout_3 = QHBoxLayout(self.DataEditWidget)
        self.horizontalLayout_3.setSpacing(2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_3)

        self.AddDataButton = QPushButton(self.DataEditWidget)
        self.AddDataButton.setObjectName(u"AddDataButton")

        self.horizontalLayout_3.addWidget(self.AddDataButton)

        self.RemoveDataButton = QPushButton(self.DataEditWidget)
        self.RemoveDataButton.setObjectName(u"RemoveDataButton")

        self.horizontalLayout_3.addWidget(self.RemoveDataButton)


        self.verticalLayout_2.addWidget(self.DataEditWidget)

        self.DataTable = QTableView(self.DataBox)
        self.DataTable.setObjectName(u"DataTable")

        self.verticalLayout_2.addWidget(self.DataTable)


        self.gridLayout.addWidget(self.DataBox, 2, 2, 1, 2)

        self.ButtonsFrame = QFrame(AssetDialog)
        self.ButtonsFrame.setObjectName(u"ButtonsFrame")
        self.ButtonsFrame.setFrameShape(QFrame.NoFrame)
        self.ButtonsFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.ButtonsFrame)
        self.horizontalLayout.setSpacing(2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.CancelButton = QPushButton(self.ButtonsFrame)
        self.CancelButton.setObjectName(u"CancelButton")

        self.horizontalLayout.addWidget(self.CancelButton)

        self.OkButton = QPushButton(self.ButtonsFrame)
        self.OkButton.setObjectName(u"OkButton")

        self.horizontalLayout.addWidget(self.OkButton)


        self.gridLayout.addWidget(self.ButtonsFrame, 8, 0, 1, 4)

        self.BaseAssetEdit = QLineEdit(AssetDialog)
        self.BaseAssetEdit.setObjectName(u"BaseAssetEdit")

        self.gridLayout.addWidget(self.BaseAssetEdit, 3, 1, 1, 3)


        self.retranslateUi(AssetDialog)

        QMetaObject.connectSlotsByName(AssetDialog)
    # setupUi

    def retranslateUi(self, AssetDialog):
        AssetDialog.setWindowTitle(QCoreApplication.translate("AssetDialog", u"Asset", None))
        self.TypeLbl.setText(QCoreApplication.translate("AssetDialog", u"Type:", None))
        self.NameLbl.setText(QCoreApplication.translate("AssetDialog", u"Name:", None))
        self.isinLbl.setText(QCoreApplication.translate("AssetDialog", u"ISIN:", None))
        self.SymbolsBox.setTitle(QCoreApplication.translate("AssetDialog", u"Symbols", None))
        self.AddSymbolButton.setText("")
        self.RemoveSymbolButton.setText("")
        self.BaseLbl.setText(QCoreApplication.translate("AssetDialog", u"Base asset:", None))
        self.DataBox.setTitle(QCoreApplication.translate("AssetDialog", u"Extra data", None))
        self.AddDataButton.setText("")
        self.RemoveDataButton.setText("")
        self.CancelButton.setText("")
        self.OkButton.setText("")
    # retranslateUi

