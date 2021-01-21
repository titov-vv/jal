# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rebuild_window.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_ReBuildDialog(object):
    def setupUi(self, ReBuildDialog):
        if not ReBuildDialog.objectName():
            ReBuildDialog.setObjectName(u"ReBuildDialog")
        ReBuildDialog.setWindowModality(Qt.ApplicationModal)
        ReBuildDialog.resize(268, 150)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(ReBuildDialog.sizePolicy().hasHeightForWidth())
        ReBuildDialog.setSizePolicy(sizePolicy)
        font = QFont()
        font.setFamily(u"DejaVu Sans")
        ReBuildDialog.setFont(font)
        self.verticalLayout = QVBoxLayout(ReBuildDialog)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.TypeGroup = QGroupBox(ReBuildDialog)
        self.TypeGroup.setObjectName(u"TypeGroup")
        sizePolicy1 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.TypeGroup.sizePolicy().hasHeightForWidth())
        self.TypeGroup.setSizePolicy(sizePolicy1)
        self.formLayout = QFormLayout(self.TypeGroup)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setSizeConstraint(QLayout.SetMinimumSize)
        self.formLayout.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        self.formLayout.setHorizontalSpacing(15)
        self.formLayout.setVerticalSpacing(0)
        self.formLayout.setContentsMargins(2, 0, 2, 0)
        self.AllRadioButton = QRadioButton(self.TypeGroup)
        self.AllRadioButton.setObjectName(u"AllRadioButton")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.AllRadioButton)

        self.LastRadioButton = QRadioButton(self.TypeGroup)
        self.LastRadioButton.setObjectName(u"LastRadioButton")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.LastRadioButton)

        self.FrontierDateLabel = QLabel(self.TypeGroup)
        self.FrontierDateLabel.setObjectName(u"FrontierDateLabel")

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.FrontierDateLabel)

        self.DateRadionButton = QRadioButton(self.TypeGroup)
        self.DateRadionButton.setObjectName(u"DateRadionButton")

        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.DateRadionButton)

        self.CustomDateEdit = QDateEdit(self.TypeGroup)
        self.CustomDateEdit.setObjectName(u"CustomDateEdit")
        self.CustomDateEdit.setCalendarPopup(True)
        self.CustomDateEdit.setTimeSpec(Qt.UTC)

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.CustomDateEdit)


        self.verticalLayout.addWidget(self.TypeGroup)

        self.FastAndDirty = QCheckBox(ReBuildDialog)
        self.FastAndDirty.setObjectName(u"FastAndDirty")
        self.FastAndDirty.setChecked(True)

        self.verticalLayout.addWidget(self.FastAndDirty)

        self.DialogButtonBox = QDialogButtonBox(ReBuildDialog)
        self.DialogButtonBox.setObjectName(u"DialogButtonBox")
        sizePolicy1.setHeightForWidth(self.DialogButtonBox.sizePolicy().hasHeightForWidth())
        self.DialogButtonBox.setSizePolicy(sizePolicy1)
        self.DialogButtonBox.setOrientation(Qt.Horizontal)
        self.DialogButtonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.DialogButtonBox)


        self.retranslateUi(ReBuildDialog)
        self.DialogButtonBox.accepted.connect(ReBuildDialog.accept)
        self.DialogButtonBox.rejected.connect(ReBuildDialog.reject)

        QMetaObject.connectSlotsByName(ReBuildDialog)
    # setupUi

    def retranslateUi(self, ReBuildDialog):
        ReBuildDialog.setWindowTitle(QCoreApplication.translate("ReBuildDialog", u"Re-Build Ledger", None))
        self.TypeGroup.setTitle(QCoreApplication.translate("ReBuildDialog", u"Date Range", None))
        self.AllRadioButton.setText(QCoreApplication.translate("ReBuildDialog", u"&Full, from scratch", None))
        self.LastRadioButton.setText(QCoreApplication.translate("ReBuildDialog", u"Since &Last actual:", None))
        self.FrontierDateLabel.setText(QCoreApplication.translate("ReBuildDialog", u"FrontierDate", None))
        self.DateRadionButton.setText(QCoreApplication.translate("ReBuildDialog", u"Since &Date:", None))
        self.CustomDateEdit.setDisplayFormat(QCoreApplication.translate("ReBuildDialog", u"dd/MM/yyyy", None))
        self.FastAndDirty.setText(QCoreApplication.translate("ReBuildDialog", u"Fast, &unreliable", None))
    # retranslateUi

