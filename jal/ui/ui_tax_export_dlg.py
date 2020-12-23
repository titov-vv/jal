# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tax_export_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from jal.ui_custom.reference_selector import AccountSelector


class Ui_TaxExportDlg(object):
    def setupUi(self, TaxExportDlg):
        if not TaxExportDlg.objectName():
            TaxExportDlg.setObjectName(u"TaxExportDlg")
        TaxExportDlg.resize(570, 117)
        self.gridLayout = QGridLayout(TaxExportDlg)
        self.gridLayout.setObjectName(u"gridLayout")
        self.FileLbl = QLabel(TaxExportDlg)
        self.FileLbl.setObjectName(u"FileLbl")

        self.gridLayout.addWidget(self.FileLbl, 2, 0, 1, 1)

        self.AccountWidget = AccountSelector(TaxExportDlg)
        self.AccountWidget.setObjectName(u"AccountWidget")

        self.gridLayout.addWidget(self.AccountWidget, 1, 1, 1, 2)

        self.Filename = QLineEdit(TaxExportDlg)
        self.Filename.setObjectName(u"Filename")

        self.gridLayout.addWidget(self.Filename, 2, 1, 1, 1)

        self.Year = QSpinBox(TaxExportDlg)
        self.Year.setObjectName(u"Year")
        self.Year.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.Year.setMinimum(2015)
        self.Year.setMaximum(2020)
        self.Year.setValue(2019)

        self.gridLayout.addWidget(self.Year, 0, 1, 1, 2)

        self.YearLbl = QLabel(TaxExportDlg)
        self.YearLbl.setObjectName(u"YearLbl")

        self.gridLayout.addWidget(self.YearLbl, 0, 0, 1, 1)

        self.AccountLbl = QLabel(TaxExportDlg)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.gridLayout.addWidget(self.AccountLbl, 1, 0, 1, 1)

        self.buttonBox = QDialogButtonBox(TaxExportDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Vertical)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 0, 3, 3, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 3, 0, 1, 1)

        self.FileSelectBtn = QPushButton(TaxExportDlg)
        self.FileSelectBtn.setObjectName(u"FileSelectBtn")

        self.gridLayout.addWidget(self.FileSelectBtn, 2, 2, 1, 1)


        self.retranslateUi(TaxExportDlg)
        self.buttonBox.accepted.connect(TaxExportDlg.accept)
        self.buttonBox.rejected.connect(TaxExportDlg.reject)

        QMetaObject.connectSlotsByName(TaxExportDlg)
    # setupUi

    def retranslateUi(self, TaxExportDlg):
        TaxExportDlg.setWindowTitle(QCoreApplication.translate("TaxExportDlg", u"Select parameters and filename for tax report", None))
        self.FileLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Filename", None))
        self.Year.setSuffix("")
        self.YearLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Year:", None))
        self.AccountLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Account:", None))
        self.FileSelectBtn.setText(QCoreApplication.translate("TaxExportDlg", u"...", None))
    # retranslateUi

