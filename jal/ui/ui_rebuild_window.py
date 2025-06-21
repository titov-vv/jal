# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rebuild_window.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDateEdit, QDialog,
    QDialogButtonBox, QFormLayout, QGroupBox, QLabel,
    QLayout, QRadioButton, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_ReBuildDialog(object):
    def setupUi(self, ReBuildDialog):
        if not ReBuildDialog.objectName():
            ReBuildDialog.setObjectName(u"ReBuildDialog")
        ReBuildDialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        ReBuildDialog.resize(298, 156)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(ReBuildDialog.sizePolicy().hasHeightForWidth())
        ReBuildDialog.setSizePolicy(sizePolicy)
        font = QFont()
        font.setFamilies([u"DejaVu Sans"])
        ReBuildDialog.setFont(font)
        self.verticalLayout = QVBoxLayout(ReBuildDialog)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.TypeGroup = QGroupBox(ReBuildDialog)
        self.TypeGroup.setObjectName(u"TypeGroup")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.TypeGroup.sizePolicy().hasHeightForWidth())
        self.TypeGroup.setSizePolicy(sizePolicy1)
        self.formLayout = QFormLayout(self.TypeGroup)
        self.formLayout.setObjectName(u"formLayout")
        self.formLayout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.formLayout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.formLayout.setHorizontalSpacing(15)
        self.formLayout.setVerticalSpacing(0)
        self.formLayout.setContentsMargins(2, 0, 2, 0)
        self.AllRadioButton = QRadioButton(self.TypeGroup)
        self.AllRadioButton.setObjectName(u"AllRadioButton")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.AllRadioButton)

        self.LastRadioButton = QRadioButton(self.TypeGroup)
        self.LastRadioButton.setObjectName(u"LastRadioButton")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.LastRadioButton)

        self.FrontierDateLabel = QLabel(self.TypeGroup)
        self.FrontierDateLabel.setObjectName(u"FrontierDateLabel")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.FrontierDateLabel)

        self.DateRadionButton = QRadioButton(self.TypeGroup)
        self.DateRadionButton.setObjectName(u"DateRadionButton")

        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.DateRadionButton)

        self.CustomDateEdit = QDateEdit(self.TypeGroup)
        self.CustomDateEdit.setObjectName(u"CustomDateEdit")
        self.CustomDateEdit.setCalendarPopup(True)
        self.CustomDateEdit.setTimeSpec(Qt.TimeSpec.UTC)

        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.CustomDateEdit)


        self.verticalLayout.addWidget(self.TypeGroup)

        self.DialogButtonBox = QDialogButtonBox(ReBuildDialog)
        self.DialogButtonBox.setObjectName(u"DialogButtonBox")
        sizePolicy1.setHeightForWidth(self.DialogButtonBox.sizePolicy().hasHeightForWidth())
        self.DialogButtonBox.setSizePolicy(sizePolicy1)
        self.DialogButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.DialogButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

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
    # retranslateUi

