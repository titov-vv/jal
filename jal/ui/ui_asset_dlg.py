# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'asset_dlg.ui'
##
## Created by: Qt User Interface Compiler version 6.9.1
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
    QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QSplitter, QTableView, QVBoxLayout, QWidget)

from jal.constants import AssetTypeComboBox
from jal.widgets.custom.db_lookup_combobox import DbLookupComboBox
from jal.widgets.reference_selector import AssetSelector

class Ui_AssetDialog(object):
    def setupUi(self, AssetDialog):
        if not AssetDialog.objectName():
            AssetDialog.setObjectName(u"AssetDialog")
        AssetDialog.setWindowModality(Qt.ApplicationModal)
        AssetDialog.resize(927, 323)
        AssetDialog.setModal(False)
        self.gridLayout = QGridLayout(AssetDialog)
        self.gridLayout.setSpacing(2)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_4, 1, 2, 1, 1)

        self.frame = QFrame(AssetDialog)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame)
        self.horizontalLayout_3.setSpacing(2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.frame)
        self.splitter.setObjectName(u"splitter")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.splitter.sizePolicy().hasHeightForWidth())
        self.splitter.setSizePolicy(sizePolicy1)
        self.splitter.setOrientation(Qt.Horizontal)
        self.SymbolsFrame = QFrame(self.splitter)
        self.SymbolsFrame.setObjectName(u"SymbolsFrame")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(5)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.SymbolsFrame.sizePolicy().hasHeightForWidth())
        self.SymbolsFrame.setSizePolicy(sizePolicy2)
        self.SymbolsFrame.setFrameShape(QFrame.NoFrame)
        self.SymbolsFrame.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.SymbolsFrame)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.SymbolsCaptionFrame = QFrame(self.SymbolsFrame)
        self.SymbolsCaptionFrame.setObjectName(u"SymbolsCaptionFrame")
        self.SymbolsCaptionFrame.setFrameShape(QFrame.NoFrame)
        self.SymbolsCaptionFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.SymbolsCaptionFrame)
        self.horizontalLayout_5.setSpacing(2)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.SymbolsLabel = QLabel(self.SymbolsCaptionFrame)
        self.SymbolsLabel.setObjectName(u"SymbolsLabel")

        self.horizontalLayout_5.addWidget(self.SymbolsLabel)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_2)

        self.AddSymbolButton = QPushButton(self.SymbolsCaptionFrame)
        self.AddSymbolButton.setObjectName(u"AddSymbolButton")

        self.horizontalLayout_5.addWidget(self.AddSymbolButton)

        self.RemoveSymbolButton = QPushButton(self.SymbolsCaptionFrame)
        self.RemoveSymbolButton.setObjectName(u"RemoveSymbolButton")

        self.horizontalLayout_5.addWidget(self.RemoveSymbolButton)


        self.verticalLayout.addWidget(self.SymbolsCaptionFrame)

        self.SymbolsTable = QTableView(self.SymbolsFrame)
        self.SymbolsTable.setObjectName(u"SymbolsTable")
        self.SymbolsTable.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.EditKeyPressed|QAbstractItemView.SelectedClicked)
        self.SymbolsTable.setAlternatingRowColors(True)
        self.SymbolsTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.SymbolsTable.verticalHeader().setVisible(False)
        self.SymbolsTable.verticalHeader().setMinimumSectionSize(20)
        self.SymbolsTable.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.SymbolsTable)

        self.splitter.addWidget(self.SymbolsFrame)
        self.DataFrame = QFrame(self.splitter)
        self.DataFrame.setObjectName(u"DataFrame")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(2)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.DataFrame.sizePolicy().hasHeightForWidth())
        self.DataFrame.setSizePolicy(sizePolicy3)
        self.DataFrame.setFrameShape(QFrame.NoFrame)
        self.DataFrame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.DataFrame)
        self.verticalLayout_2.setSpacing(2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.DataCaptionFrame = QFrame(self.DataFrame)
        self.DataCaptionFrame.setObjectName(u"DataCaptionFrame")
        self.DataCaptionFrame.setFrameShape(QFrame.NoFrame)
        self.DataCaptionFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.DataCaptionFrame)
        self.horizontalLayout_2.setSpacing(2)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.DataLbl = QLabel(self.DataCaptionFrame)
        self.DataLbl.setObjectName(u"DataLbl")

        self.horizontalLayout_2.addWidget(self.DataLbl)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_3)

        self.AddDataButton = QPushButton(self.DataCaptionFrame)
        self.AddDataButton.setObjectName(u"AddDataButton")

        self.horizontalLayout_2.addWidget(self.AddDataButton)

        self.RemoveDataButton = QPushButton(self.DataCaptionFrame)
        self.RemoveDataButton.setObjectName(u"RemoveDataButton")

        self.horizontalLayout_2.addWidget(self.RemoveDataButton)


        self.verticalLayout_2.addWidget(self.DataCaptionFrame)

        self.DataTable = QTableView(self.DataFrame)
        self.DataTable.setObjectName(u"DataTable")
        self.DataTable.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.EditKeyPressed|QAbstractItemView.SelectedClicked)
        self.DataTable.setAlternatingRowColors(True)
        self.DataTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.DataTable.verticalHeader().setVisible(False)
        self.DataTable.verticalHeader().setMinimumSectionSize(20)
        self.DataTable.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout_2.addWidget(self.DataTable)

        self.splitter.addWidget(self.DataFrame)

        self.horizontalLayout_3.addWidget(self.splitter)


        self.gridLayout.addWidget(self.frame, 3, 0, 1, 5)

        self.NameLbl = QLabel(AssetDialog)
        self.NameLbl.setObjectName(u"NameLbl")

        self.gridLayout.addWidget(self.NameLbl, 0, 0, 1, 1)

        self.isinLbl = QLabel(AssetDialog)
        self.isinLbl.setObjectName(u"isinLbl")

        self.gridLayout.addWidget(self.isinLbl, 1, 0, 1, 1)

        self.BaseAssetSelector = AssetSelector(AssetDialog)
        self.BaseAssetSelector.setObjectName(u"BaseAssetSelector")

        self.gridLayout.addWidget(self.BaseAssetSelector, 2, 1, 1, 1)

        self.ButtonsFrame = QFrame(AssetDialog)
        self.ButtonsFrame.setObjectName(u"ButtonsFrame")
        self.ButtonsFrame.setFrameShape(QFrame.NoFrame)
        self.ButtonsFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.ButtonsFrame)
        self.horizontalLayout.setSpacing(2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.CancelButton = QPushButton(self.ButtonsFrame)
        self.CancelButton.setObjectName(u"CancelButton")

        self.horizontalLayout.addWidget(self.CancelButton)

        self.OkButton = QPushButton(self.ButtonsFrame)
        self.OkButton.setObjectName(u"OkButton")

        self.horizontalLayout.addWidget(self.OkButton)


        self.gridLayout.addWidget(self.ButtonsFrame, 10, 0, 1, 5)

        self.BaseLbl = QLabel(AssetDialog)
        self.BaseLbl.setObjectName(u"BaseLbl")

        self.gridLayout.addWidget(self.BaseLbl, 2, 0, 1, 1)

        self.TypeLbl = QLabel(AssetDialog)
        self.TypeLbl.setObjectName(u"TypeLbl")

        self.gridLayout.addWidget(self.TypeLbl, 1, 3, 1, 1)

        self.isinEdit = QLineEdit(AssetDialog)
        self.isinEdit.setObjectName(u"isinEdit")

        self.gridLayout.addWidget(self.isinEdit, 1, 1, 1, 1)

        self.CountryLbl = QLabel(AssetDialog)
        self.CountryLbl.setObjectName(u"CountryLbl")

        self.gridLayout.addWidget(self.CountryLbl, 2, 3, 1, 1)

        self.TypeCombo = AssetTypeComboBox(AssetDialog)
        self.TypeCombo.setObjectName(u"TypeCombo")

        self.gridLayout.addWidget(self.TypeCombo, 1, 4, 1, 1)

        self.NameEdit = QLineEdit(AssetDialog)
        self.NameEdit.setObjectName(u"NameEdit")

        self.gridLayout.addWidget(self.NameEdit, 0, 1, 1, 4)

        self.CountryCombo = DbLookupComboBox(AssetDialog)
        self.CountryCombo.setObjectName(u"CountryCombo")
        self.CountryCombo.setProperty(u"db_table", u"countries_ext")
        self.CountryCombo.setProperty(u"key_field", u"id")
        self.CountryCombo.setProperty(u"db_field", u"name")

        self.gridLayout.addWidget(self.CountryCombo, 2, 4, 1, 1)


        self.retranslateUi(AssetDialog)
        self.OkButton.clicked.connect(AssetDialog.accept)
        self.CancelButton.clicked.connect(AssetDialog.reject)

        QMetaObject.connectSlotsByName(AssetDialog)
    # setupUi

    def retranslateUi(self, AssetDialog):
        AssetDialog.setWindowTitle(QCoreApplication.translate("AssetDialog", u"Asset", None))
        self.SymbolsLabel.setText(QCoreApplication.translate("AssetDialog", u"Symbols", None))
        self.AddSymbolButton.setText("")
        self.RemoveSymbolButton.setText("")
        self.DataLbl.setText(QCoreApplication.translate("AssetDialog", u"Extra data", None))
        self.AddDataButton.setText("")
        self.RemoveDataButton.setText("")
        self.NameLbl.setText(QCoreApplication.translate("AssetDialog", u"Name:", None))
        self.isinLbl.setText(QCoreApplication.translate("AssetDialog", u"ISIN:", None))
        self.CancelButton.setText(QCoreApplication.translate("AssetDialog", u"Cancel", None))
        self.OkButton.setText(QCoreApplication.translate("AssetDialog", u"OK", None))
        self.BaseLbl.setText(QCoreApplication.translate("AssetDialog", u"Base asset:", None))
        self.TypeLbl.setText(QCoreApplication.translate("AssetDialog", u"Type: ", None))
        self.CountryLbl.setText(QCoreApplication.translate("AssetDialog", u"Country: ", None))
    # retranslateUi

