# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rebuild_window.ui'
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


class Ui_ReBuildDialog(object):
    def setupUi(self, ReBuildDialog):
        if ReBuildDialog.objectName():
            ReBuildDialog.setObjectName(u"ReBuildDialog")
        ReBuildDialog.resize(260, 119)
        font = QFont()
        font.setFamily(u"DejaVu Sans")
        ReBuildDialog.setFont(font)
        self.DialogButtonBox = QDialogButtonBox(ReBuildDialog)
        self.DialogButtonBox.setObjectName(u"DialogButtonBox")
        self.DialogButtonBox.setGeometry(QRect(88, 90, 171, 32))
        self.DialogButtonBox.setOrientation(Qt.Horizontal)
        self.DialogButtonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.TypeGroup = QGroupBox(ReBuildDialog)
        self.TypeGroup.setObjectName(u"TypeGroup")
        self.TypeGroup.setGeometry(QRect(0, 0, 259, 91))
        self.AllRadioButton = QRadioButton(self.TypeGroup)
        self.AllRadioButton.setObjectName(u"AllRadioButton")
        self.AllRadioButton.setGeometry(QRect(10, 22, 100, 21))
        self.LastRadioButton = QRadioButton(self.TypeGroup)
        self.LastRadioButton.setObjectName(u"LastRadioButton")
        self.LastRadioButton.setGeometry(QRect(10, 44, 131, 21))
        self.DateRadionButton = QRadioButton(self.TypeGroup)
        self.DateRadionButton.setObjectName(u"DateRadionButton")
        self.DateRadionButton.setGeometry(QRect(10, 66, 131, 21))
        self.CustomDateEdit = QDateEdit(self.TypeGroup)
        self.CustomDateEdit.setObjectName(u"CustomDateEdit")
        self.CustomDateEdit.setGeometry(QRect(140, 64, 110, 24))
        self.CustomDateEdit.setCalendarPopup(True)
        self.FrontierDateLabel = QLabel(self.TypeGroup)
        self.FrontierDateLabel.setObjectName(u"FrontierDateLabel")
        self.FrontierDateLabel.setGeometry(QRect(140, 46, 111, 16))

        self.retranslateUi(ReBuildDialog)
        self.DialogButtonBox.accepted.connect(ReBuildDialog.accept)
        self.DialogButtonBox.rejected.connect(ReBuildDialog.reject)

        QMetaObject.connectSlotsByName(ReBuildDialog)
    # setupUi

    def retranslateUi(self, ReBuildDialog):
        ReBuildDialog.setWindowTitle(QCoreApplication.translate("ReBuildDialog", u"Re-Build Ledger", None))
        self.TypeGroup.setTitle(QCoreApplication.translate("ReBuildDialog", u"Date Range", None))
        self.AllRadioButton.setText(QCoreApplication.translate("ReBuildDialog", u"&All", None))
        self.LastRadioButton.setText(QCoreApplication.translate("ReBuildDialog", u"Since &Last actual:", None))
        self.DateRadionButton.setText(QCoreApplication.translate("ReBuildDialog", u"Since &Date:", None))
        self.CustomDateEdit.setDisplayFormat(QCoreApplication.translate("ReBuildDialog", u"dd/MM/yyyy", None))
        self.FrontierDateLabel.setText(QCoreApplication.translate("ReBuildDialog", u"FrontierDate", None))
    # retranslateUi

