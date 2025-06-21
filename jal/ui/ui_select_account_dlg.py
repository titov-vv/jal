# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'select_account_dlg.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QDialog,
    QDialogButtonBox, QLabel, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

from jal.widgets.reference_selector import AccountSelector

class Ui_SelectAccountDlg(object):
    def setupUi(self, SelectAccountDlg):
        if not SelectAccountDlg.objectName():
            SelectAccountDlg.setObjectName(u"SelectAccountDlg")
        SelectAccountDlg.resize(400, 141)
        self.verticalLayout = QVBoxLayout(SelectAccountDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.DescriptionLbl = QLabel(SelectAccountDlg)
        self.DescriptionLbl.setObjectName(u"DescriptionLbl")

        self.verticalLayout.addWidget(self.DescriptionLbl)

        self.AccountWidget = AccountSelector(SelectAccountDlg)
        self.AccountWidget.setObjectName(u"AccountWidget")

        self.verticalLayout.addWidget(self.AccountWidget)

        self.ReuseAccount = QCheckBox(SelectAccountDlg)
        self.ReuseAccount.setObjectName(u"ReuseAccount")

        self.verticalLayout.addWidget(self.ReuseAccount)

        self.buttonBox = QDialogButtonBox(SelectAccountDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)


        self.retranslateUi(SelectAccountDlg)
        self.buttonBox.accepted.connect(SelectAccountDlg.close)

        QMetaObject.connectSlotsByName(SelectAccountDlg)
    # setupUi

    def retranslateUi(self, SelectAccountDlg):
        SelectAccountDlg.setWindowTitle(QCoreApplication.translate("SelectAccountDlg", u"Please select account", None))
        self.DescriptionLbl.setText(QCoreApplication.translate("SelectAccountDlg", u"TextLabel", None))
        self.ReuseAccount.setText(QCoreApplication.translate("SelectAccountDlg", u"Use the same account for given currency", None))
    # retranslateUi

