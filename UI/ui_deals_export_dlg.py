# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'deals_export_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.15.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QDate, QDateTime, QMetaObject,
    QObject, QPoint, QRect, QSize, QTime, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter,
    QPixmap, QRadialGradient)
from PySide2.QtWidgets import *

from CustomUI.account_select import AccountSelector


class Ui_DealsExportDlg(object):
    def setupUi(self, DealsExportDlg):
        if not DealsExportDlg.objectName():
            DealsExportDlg.setObjectName(u"DealsExportDlg")
        DealsExportDlg.resize(603, 118)
        self.gridLayout = QGridLayout(DealsExportDlg)
        self.gridLayout.setObjectName(u"gridLayout")
        self.AccountLbl = QLabel(DealsExportDlg)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.gridLayout.addWidget(self.AccountLbl, 1, 0, 1, 1)

        self.AccountWidget = AccountSelector(DealsExportDlg)
        self.AccountWidget.setObjectName(u"AccountWidget")

        self.gridLayout.addWidget(self.AccountWidget, 1, 1, 1, 5)

        self.FileLbl = QLabel(DealsExportDlg)
        self.FileLbl.setObjectName(u"FileLbl")

        self.gridLayout.addWidget(self.FileLbl, 2, 0, 1, 1)

        self.FromDate = QDateEdit(DealsExportDlg)
        self.FromDate.setObjectName(u"FromDate")
        self.FromDate.setCalendarPopup(True)

        self.gridLayout.addWidget(self.FromDate, 0, 1, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 3, 0, 1, 1)

        self.EndLbl = QLabel(DealsExportDlg)
        self.EndLbl.setObjectName(u"EndLbl")

        self.gridLayout.addWidget(self.EndLbl, 0, 2, 1, 1)

        self.StartLbl = QLabel(DealsExportDlg)
        self.StartLbl.setObjectName(u"StartLbl")

        self.gridLayout.addWidget(self.StartLbl, 0, 0, 1, 1)

        self.ToDate = QDateEdit(DealsExportDlg)
        self.ToDate.setObjectName(u"ToDate")
        self.ToDate.setCalendarPopup(True)

        self.gridLayout.addWidget(self.ToDate, 0, 3, 1, 1)

        self.buttonBox = QDialogButtonBox(DealsExportDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Vertical)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 0, 6, 2, 1)

        self.FileSelectBtn = QPushButton(DealsExportDlg)
        self.FileSelectBtn.setObjectName(u"FileSelectBtn")

        self.gridLayout.addWidget(self.FileSelectBtn, 2, 5, 1, 1)

        self.DateGroupCheckBox = QCheckBox(DealsExportDlg)
        self.DateGroupCheckBox.setObjectName(u"DateGroupCheckBox")
        self.DateGroupCheckBox.setChecked(True)

        self.gridLayout.addWidget(self.DateGroupCheckBox, 0, 4, 1, 1)

        self.Filename = QLineEdit(DealsExportDlg)
        self.Filename.setObjectName(u"Filename")

        self.gridLayout.addWidget(self.Filename, 2, 1, 1, 4)


        self.retranslateUi(DealsExportDlg)
        self.buttonBox.accepted.connect(DealsExportDlg.accept)
        self.buttonBox.rejected.connect(DealsExportDlg.reject)

        QMetaObject.connectSlotsByName(DealsExportDlg)
    # setupUi

    def retranslateUi(self, DealsExportDlg):
        DealsExportDlg.setWindowTitle(QCoreApplication.translate("DealsExportDlg", u"Deals export", None))
        self.AccountLbl.setText(QCoreApplication.translate("DealsExportDlg", u"Account:", None))
        self.FileLbl.setText(QCoreApplication.translate("DealsExportDlg", u"Filename:", None))
        self.FromDate.setDisplayFormat(QCoreApplication.translate("DealsExportDlg", u"dd/MM/yyyy", None))
        self.EndLbl.setText(QCoreApplication.translate("DealsExportDlg", u"To:", None))
        self.StartLbl.setText(QCoreApplication.translate("DealsExportDlg", u"From:", None))
        self.ToDate.setDisplayFormat(QCoreApplication.translate("DealsExportDlg", u"dd/MM/yyyy", None))
        self.FileSelectBtn.setText(QCoreApplication.translate("DealsExportDlg", u"...", None))
        self.DateGroupCheckBox.setText(QCoreApplication.translate("DealsExportDlg", u"Group dates", None))
    # retranslateUi

