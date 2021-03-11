# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'reference_data_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_ReferenceDataDialog(object):
    def setupUi(self, ReferenceDataDialog):
        if not ReferenceDataDialog.objectName():
            ReferenceDataDialog.setObjectName(u"ReferenceDataDialog")
        ReferenceDataDialog.resize(869, 300)
        self.verticalLayout = QVBoxLayout(ReferenceDataDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.EditFrame = QFrame(ReferenceDataDialog)
        self.EditFrame.setObjectName(u"EditFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.EditFrame.sizePolicy().hasHeightForWidth())
        self.EditFrame.setSizePolicy(sizePolicy)
        self.EditFrame.setFrameShape(QFrame.Panel)
        self.EditFrame.setFrameShadow(QFrame.Plain)
        self.EditFrame.setLineWidth(0)
        self.edit_layout = QHBoxLayout(self.EditFrame)
        self.edit_layout.setObjectName(u"edit_layout")
        self.edit_layout.setContentsMargins(0, 0, 0, 0)
        self.GroupLbl = QLabel(self.EditFrame)
        self.GroupLbl.setObjectName(u"GroupLbl")

        self.edit_layout.addWidget(self.GroupLbl)

        self.GroupCombo = QComboBox(self.EditFrame)
        self.GroupCombo.setObjectName(u"GroupCombo")

        self.edit_layout.addWidget(self.GroupCombo)

        self.Toggle = QCheckBox(self.EditFrame)
        self.Toggle.setObjectName(u"Toggle")
        self.Toggle.setChecked(False)

        self.edit_layout.addWidget(self.Toggle)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.edit_layout.addItem(self.horizontalSpacer)

        self.AddBtn = QPushButton(self.EditFrame)
        self.AddBtn.setObjectName(u"AddBtn")

        self.edit_layout.addWidget(self.AddBtn)

        self.AddChildBtn = QPushButton(self.EditFrame)
        self.AddChildBtn.setObjectName(u"AddChildBtn")

        self.edit_layout.addWidget(self.AddChildBtn)

        self.RemoveBtn = QPushButton(self.EditFrame)
        self.RemoveBtn.setObjectName(u"RemoveBtn")

        self.edit_layout.addWidget(self.RemoveBtn)

        self.CommitBtn = QPushButton(self.EditFrame)
        self.CommitBtn.setObjectName(u"CommitBtn")
        self.CommitBtn.setEnabled(False)

        self.edit_layout.addWidget(self.CommitBtn)

        self.RevertBtn = QPushButton(self.EditFrame)
        self.RevertBtn.setObjectName(u"RevertBtn")
        self.RevertBtn.setEnabled(False)

        self.edit_layout.addWidget(self.RevertBtn)


        self.verticalLayout.addWidget(self.EditFrame)

        self.SearchFrame = QFrame(ReferenceDataDialog)
        self.SearchFrame.setObjectName(u"SearchFrame")
        self.SearchFrame.setFrameShape(QFrame.Panel)
        self.SearchFrame.setFrameShadow(QFrame.Plain)
        self.SearchFrame.setLineWidth(0)
        self.search_layout = QHBoxLayout(self.SearchFrame)
        self.search_layout.setObjectName(u"search_layout")
        self.search_layout.setContentsMargins(0, 0, 0, 0)
        self.SearchLbl = QLabel(self.SearchFrame)
        self.SearchLbl.setObjectName(u"SearchLbl")

        self.search_layout.addWidget(self.SearchLbl)

        self.SearchString = QLineEdit(self.SearchFrame)
        self.SearchString.setObjectName(u"SearchString")

        self.search_layout.addWidget(self.SearchString)


        self.verticalLayout.addWidget(self.SearchFrame)

        self.DataView = QTableView(ReferenceDataDialog)
        self.DataView.setObjectName(u"DataView")
        self.DataView.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.EditKeyPressed|QAbstractItemView.SelectedClicked)
        self.DataView.setAlternatingRowColors(True)
        self.DataView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.DataView.verticalHeader().setVisible(True)
        self.DataView.verticalHeader().setMinimumSectionSize(20)
        self.DataView.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.DataView)

        self.TreeView = QTreeView(ReferenceDataDialog)
        self.TreeView.setObjectName(u"TreeView")
        self.TreeView.setEditTriggers(QAbstractItemView.AnyKeyPressed|QAbstractItemView.EditKeyPressed|QAbstractItemView.SelectedClicked)
        self.TreeView.setTabKeyNavigation(True)
        self.TreeView.setAlternatingRowColors(True)
        self.TreeView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.TreeView.setExpandsOnDoubleClick(False)
        self.TreeView.header().setStretchLastSection(False)

        self.verticalLayout.addWidget(self.TreeView)


        self.retranslateUi(ReferenceDataDialog)

        QMetaObject.connectSlotsByName(ReferenceDataDialog)
    # setupUi

    def retranslateUi(self, ReferenceDataDialog):
        ReferenceDataDialog.setWindowTitle(QCoreApplication.translate("ReferenceDataDialog", u"Reference Data", None))
        self.GroupLbl.setText(QCoreApplication.translate("ReferenceDataDialog", u"Account Type:", None))
        self.Toggle.setText(QCoreApplication.translate("ReferenceDataDialog", u"Show inactive", None))
        self.AddBtn.setText(QCoreApplication.translate("ReferenceDataDialog", u" +\ufe0f ", None))
        self.AddChildBtn.setText(QCoreApplication.translate("ReferenceDataDialog", u"..+", None))
        self.RemoveBtn.setText(QCoreApplication.translate("ReferenceDataDialog", u" \u2014 ", None))
        self.CommitBtn.setText(QCoreApplication.translate("ReferenceDataDialog", u" \u2714 ", None))
        self.RevertBtn.setText(QCoreApplication.translate("ReferenceDataDialog", u" \u2716 ", None))
        self.SearchLbl.setText(QCoreApplication.translate("ReferenceDataDialog", u"Search:", None))
    # retranslateUi

