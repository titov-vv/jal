# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'symbol_edit_dlg.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
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
from jal.widgets.reference_selector import ReferenceSelectorWidget

class Ui_SymbolDialog(object):
    def setupUi(self, SymbolDialog):
        if not SymbolDialog.objectName():
            SymbolDialog.setObjectName(u"SymbolDialog")
        SymbolDialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        SymbolDialog.resize(1001, 441)
        SymbolDialog.setModal(False)
        self.gridLayout = QGridLayout(SymbolDialog)
        self.gridLayout.setSpacing(2)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)
        self.ButtonsFrame = QFrame(SymbolDialog)
        self.ButtonsFrame.setObjectName(u"ButtonsFrame")
        self.ButtonsFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.ButtonsFrame.setFrameShadow(QFrame.Shadow.Raised)
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


        self.gridLayout.addWidget(self.ButtonsFrame, 1, 0, 1, 5)

        self.MainFrame = QFrame(SymbolDialog)
        self.MainFrame.setObjectName(u"MainFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.MainFrame.sizePolicy().hasHeightForWidth())
        self.MainFrame.setSizePolicy(sizePolicy)
        self.MainFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.MainFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.MainFrame)
        self.horizontalLayout_3.setSpacing(2)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.VSplitter = QSplitter(self.MainFrame)
        self.VSplitter.setObjectName(u"VSplitter")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.VSplitter.sizePolicy().hasHeightForWidth())
        self.VSplitter.setSizePolicy(sizePolicy1)
        self.VSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.VSplitter.setChildrenCollapsible(False)
        self.AssetFrame = QFrame(self.VSplitter)
        self.AssetFrame.setObjectName(u"AssetFrame")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(2)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.AssetFrame.sizePolicy().hasHeightForWidth())
        self.AssetFrame.setSizePolicy(sizePolicy2)
        self.AssetFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.AssetFrame.setFrameShadow(QFrame.Shadow.Sunken)
        self.gridLayout_5 = QGridLayout(self.AssetFrame)
        self.gridLayout_5.setSpacing(2)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.gridLayout_5.setContentsMargins(0, 0, 0, 0)
        self.AddDataButton = QPushButton(self.AssetFrame)
        self.AddDataButton.setObjectName(u"AddDataButton")

        self.gridLayout_5.addWidget(self.AddDataButton, 3, 2, 1, 1)

        self.CountryLbl = QLabel(self.AssetFrame)
        self.CountryLbl.setObjectName(u"CountryLbl")

        self.gridLayout_5.addWidget(self.CountryLbl, 2, 0, 1, 1)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_5.addItem(self.horizontalSpacer_3, 3, 1, 1, 1)

        self.NameLbl = QLabel(self.AssetFrame)
        self.NameLbl.setObjectName(u"NameLbl")

        self.gridLayout_5.addWidget(self.NameLbl, 0, 0, 1, 1)

        self.CountryCombo = DbLookupComboBox(self.AssetFrame)
        self.CountryCombo.setObjectName(u"CountryCombo")
        self.CountryCombo.setProperty(u"db_table", u"countries_ext")
        self.CountryCombo.setProperty(u"key_field", u"id")
        self.CountryCombo.setProperty(u"db_field", u"name")

        self.gridLayout_5.addWidget(self.CountryCombo, 2, 1, 1, 3)

        self.DataLbl = QLabel(self.AssetFrame)
        self.DataLbl.setObjectName(u"DataLbl")

        self.gridLayout_5.addWidget(self.DataLbl, 3, 0, 1, 1)

        self.TypeLbl = QLabel(self.AssetFrame)
        self.TypeLbl.setObjectName(u"TypeLbl")

        self.gridLayout_5.addWidget(self.TypeLbl, 1, 0, 1, 1)

        self.RemoveDataButton = QPushButton(self.AssetFrame)
        self.RemoveDataButton.setObjectName(u"RemoveDataButton")

        self.gridLayout_5.addWidget(self.RemoveDataButton, 3, 3, 1, 1)

        self.DataTable = QTableView(self.AssetFrame)
        self.DataTable.setObjectName(u"DataTable")
        self.DataTable.setFrameShadow(QFrame.Shadow.Plain)
        self.DataTable.setEditTriggers(QAbstractItemView.EditTrigger.AnyKeyPressed|QAbstractItemView.EditTrigger.EditKeyPressed|QAbstractItemView.EditTrigger.SelectedClicked)
        self.DataTable.setAlternatingRowColors(True)
        self.DataTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.DataTable.verticalHeader().setVisible(False)
        self.DataTable.verticalHeader().setMinimumSectionSize(20)
        self.DataTable.verticalHeader().setDefaultSectionSize(20)

        self.gridLayout_5.addWidget(self.DataTable, 4, 0, 1, 4)

        self.TypeCombo = AssetTypeComboBox(self.AssetFrame)
        self.TypeCombo.setObjectName(u"TypeCombo")

        self.gridLayout_5.addWidget(self.TypeCombo, 1, 1, 1, 3)

        self.NameEdit = QLineEdit(self.AssetFrame)
        self.NameEdit.setObjectName(u"NameEdit")

        self.gridLayout_5.addWidget(self.NameEdit, 0, 1, 1, 3)

        self.VSplitter.addWidget(self.AssetFrame)
        self.SymbolFrame = QFrame(self.VSplitter)
        self.SymbolFrame.setObjectName(u"SymbolFrame")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(4)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.SymbolFrame.sizePolicy().hasHeightForWidth())
        self.SymbolFrame.setSizePolicy(sizePolicy3)
        self.SymbolFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.SymbolFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.SymbolFrame)
        self.verticalLayout_2.setSpacing(2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.HSplitter = QSplitter(self.SymbolFrame)
        self.HSplitter.setObjectName(u"HSplitter")
        self.HSplitter.setOrientation(Qt.Orientation.Vertical)
        self.HSplitter.setChildrenCollapsible(False)
        self.SymbolsListFrame = QFrame(self.HSplitter)
        self.SymbolsListFrame.setObjectName(u"SymbolsListFrame")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(2)
        sizePolicy4.setHeightForWidth(self.SymbolsListFrame.sizePolicy().hasHeightForWidth())
        self.SymbolsListFrame.setSizePolicy(sizePolicy4)
        self.SymbolsListFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.SymbolsListFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_3 = QGridLayout(self.SymbolsListFrame)
        self.gridLayout_3.setSpacing(2)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.SymbolsLabel = QLabel(self.SymbolsListFrame)
        self.SymbolsLabel.setObjectName(u"SymbolsLabel")

        self.gridLayout_3.addWidget(self.SymbolsLabel, 0, 0, 1, 1)

        self.RemoveSymbolButton = QPushButton(self.SymbolsListFrame)
        self.RemoveSymbolButton.setObjectName(u"RemoveSymbolButton")

        self.gridLayout_3.addWidget(self.RemoveSymbolButton, 0, 3, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_3.addItem(self.horizontalSpacer_2, 0, 1, 1, 1)

        self.AddSymbolButton = QPushButton(self.SymbolsListFrame)
        self.AddSymbolButton.setObjectName(u"AddSymbolButton")

        self.gridLayout_3.addWidget(self.AddSymbolButton, 0, 2, 1, 1)

        self.SymbolsTable = QTableView(self.SymbolsListFrame)
        self.SymbolsTable.setObjectName(u"SymbolsTable")
        self.SymbolsTable.setFrameShadow(QFrame.Shadow.Plain)
        self.SymbolsTable.setEditTriggers(QAbstractItemView.EditTrigger.AnyKeyPressed|QAbstractItemView.EditTrigger.EditKeyPressed|QAbstractItemView.EditTrigger.SelectedClicked)
        self.SymbolsTable.setAlternatingRowColors(True)
        self.SymbolsTable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.SymbolsTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.SymbolsTable.verticalHeader().setVisible(False)
        self.SymbolsTable.verticalHeader().setMinimumSectionSize(20)
        self.SymbolsTable.verticalHeader().setDefaultSectionSize(20)

        self.gridLayout_3.addWidget(self.SymbolsTable, 1, 0, 1, 4)

        self.HSplitter.addWidget(self.SymbolsListFrame)
        self.IDsListFrame = QFrame(self.HSplitter)
        self.IDsListFrame.setObjectName(u"IDsListFrame")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(4)
        sizePolicy5.setHeightForWidth(self.IDsListFrame.sizePolicy().hasHeightForWidth())
        self.IDsListFrame.setSizePolicy(sizePolicy5)
        self.IDsListFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.IDsListFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_2 = QGridLayout(self.IDsListFrame)
        self.gridLayout_2.setSpacing(2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.RemoveIdButton = QPushButton(self.IDsListFrame)
        self.RemoveIdButton.setObjectName(u"RemoveIdButton")

        self.gridLayout_2.addWidget(self.RemoveIdButton, 0, 3, 1, 1)

        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_2.addItem(self.horizontalSpacer_5, 0, 1, 1, 1)

        self.IdentifiersLabel = QLabel(self.IDsListFrame)
        self.IdentifiersLabel.setObjectName(u"IdentifiersLabel")

        self.gridLayout_2.addWidget(self.IdentifiersLabel, 0, 0, 1, 1)

        self.AddIdButton = QPushButton(self.IDsListFrame)
        self.AddIdButton.setObjectName(u"AddIdButton")

        self.gridLayout_2.addWidget(self.AddIdButton, 0, 2, 1, 1)

        self.IdentifiersTable = QTableView(self.IDsListFrame)
        self.IdentifiersTable.setObjectName(u"IdentifiersTable")
        self.IdentifiersTable.setFrameShadow(QFrame.Shadow.Plain)
        self.IdentifiersTable.setEditTriggers(QAbstractItemView.EditTrigger.AnyKeyPressed|QAbstractItemView.EditTrigger.EditKeyPressed|QAbstractItemView.EditTrigger.SelectedClicked)
        self.IdentifiersTable.setAlternatingRowColors(True)
        self.IdentifiersTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.IdentifiersTable.verticalHeader().setVisible(False)
        self.IdentifiersTable.verticalHeader().setMinimumSectionSize(20)
        self.IdentifiersTable.verticalHeader().setDefaultSectionSize(20)

        self.gridLayout_2.addWidget(self.IdentifiersTable, 1, 0, 1, 4)

        self.HSplitter.addWidget(self.IDsListFrame)

        self.verticalLayout_2.addWidget(self.HSplitter)

        self.VSplitter.addWidget(self.SymbolFrame)

        self.horizontalLayout_3.addWidget(self.VSplitter)


        self.gridLayout.addWidget(self.MainFrame, 0, 0, 1, 5)


        self.retranslateUi(SymbolDialog)
        self.OkButton.clicked.connect(SymbolDialog.accept)
        self.CancelButton.clicked.connect(SymbolDialog.reject)

        QMetaObject.connectSlotsByName(SymbolDialog)
    # setupUi

    def retranslateUi(self, SymbolDialog):
        SymbolDialog.setWindowTitle(QCoreApplication.translate("SymbolDialog", u"Asset", None))
        self.CancelButton.setText(QCoreApplication.translate("SymbolDialog", u"Cancel", None))
        self.OkButton.setText(QCoreApplication.translate("SymbolDialog", u"OK", None))
#if QT_CONFIG(tooltip)
        self.AddDataButton.setToolTip(QCoreApplication.translate("SymbolDialog", u"Add new attribute", None))
#endif // QT_CONFIG(tooltip)
        self.AddDataButton.setText("")
        self.CountryLbl.setText(QCoreApplication.translate("SymbolDialog", u"Country: ", None))
        self.NameLbl.setText(QCoreApplication.translate("SymbolDialog", u"Asset name:", None))
        self.DataLbl.setText(QCoreApplication.translate("SymbolDialog", u"Asset attributes", None))
        self.TypeLbl.setText(QCoreApplication.translate("SymbolDialog", u"Type: ", None))
#if QT_CONFIG(tooltip)
        self.RemoveDataButton.setToolTip(QCoreApplication.translate("SymbolDialog", u"Remove selected attribute", None))
#endif // QT_CONFIG(tooltip)
        self.RemoveDataButton.setText("")
        self.SymbolsLabel.setText(QCoreApplication.translate("SymbolDialog", u"Symbols", None))
#if QT_CONFIG(tooltip)
        self.RemoveSymbolButton.setToolTip(QCoreApplication.translate("SymbolDialog", u"Remove selected symbol", None))
#endif // QT_CONFIG(tooltip)
        self.RemoveSymbolButton.setText("")
#if QT_CONFIG(tooltip)
        self.AddSymbolButton.setToolTip(QCoreApplication.translate("SymbolDialog", u"Add new symbol", None))
#endif // QT_CONFIG(tooltip)
        self.AddSymbolButton.setText("")
#if QT_CONFIG(tooltip)
        self.RemoveIdButton.setToolTip(QCoreApplication.translate("SymbolDialog", u"Remove selected identifier", None))
#endif // QT_CONFIG(tooltip)
        self.RemoveIdButton.setText("")
        self.IdentifiersLabel.setText(QCoreApplication.translate("SymbolDialog", u"Identifiers", None))
#if QT_CONFIG(tooltip)
        self.AddIdButton.setToolTip(QCoreApplication.translate("SymbolDialog", u"Add new identifier", None))
#endif // QT_CONFIG(tooltip)
        self.AddIdButton.setText("")
    # retranslateUi

