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
        TaxExportDlg.resize(601, 197)
        self.gridLayout = QGridLayout(TaxExportDlg)
        self.gridLayout.setObjectName(u"gridLayout")
        self.XlsFileName = QLineEdit(TaxExportDlg)
        self.XlsFileName.setObjectName(u"XlsFileName")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.XlsFileName.sizePolicy().hasHeightForWidth())
        self.XlsFileName.setSizePolicy(sizePolicy)

        self.gridLayout.addWidget(self.XlsFileName, 2, 1, 1, 1)

        self.XlsFileLbl = QLabel(TaxExportDlg)
        self.XlsFileLbl.setObjectName(u"XlsFileLbl")

        self.gridLayout.addWidget(self.XlsFileLbl, 2, 0, 1, 1)

        self.buttonBox = QDialogButtonBox(TaxExportDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Vertical)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 0, 3, 3, 1)

        self.YearLbl = QLabel(TaxExportDlg)
        self.YearLbl.setObjectName(u"YearLbl")

        self.gridLayout.addWidget(self.YearLbl, 0, 0, 1, 1)

        self.Year = QSpinBox(TaxExportDlg)
        self.Year.setObjectName(u"Year")
        self.Year.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.Year.setMinimum(2015)
        self.Year.setMaximum(2020)
        self.Year.setValue(2019)

        self.gridLayout.addWidget(self.Year, 0, 1, 1, 2)

        self.AccountWidget = AccountSelector(TaxExportDlg)
        self.AccountWidget.setObjectName(u"AccountWidget")

        self.gridLayout.addWidget(self.AccountWidget, 1, 1, 1, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 4, 0, 1, 1)

        self.XlsSelectBtn = QPushButton(TaxExportDlg)
        self.XlsSelectBtn.setObjectName(u"XlsSelectBtn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.XlsSelectBtn.sizePolicy().hasHeightForWidth())
        self.XlsSelectBtn.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.XlsSelectBtn, 2, 2, 1, 1)

        self.AccountLbl = QLabel(TaxExportDlg)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.gridLayout.addWidget(self.AccountLbl, 1, 0, 1, 1)

        self.groupBox = QGroupBox(TaxExportDlg)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy2)
        self.groupBox.setFlat(False)
        self.groupBox.setCheckable(True)
        self.groupBox.setChecked(False)
        self.gridLayout_2 = QGridLayout(self.groupBox)
        self.gridLayout_2.setSpacing(6)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.InitialSelectBtn = QPushButton(self.groupBox)
        self.InitialSelectBtn.setObjectName(u"InitialSelectBtn")

        self.gridLayout_2.addWidget(self.InitialSelectBtn, 0, 2, 1, 1)

        self.InitialFileName = QLineEdit(self.groupBox)
        self.InitialFileName.setObjectName(u"InitialFileName")

        self.gridLayout_2.addWidget(self.InitialFileName, 0, 1, 1, 1)

        self.InitialFileLbl = QLabel(self.groupBox)
        self.InitialFileLbl.setObjectName(u"InitialFileLbl")

        self.gridLayout_2.addWidget(self.InitialFileLbl, 0, 0, 1, 1)

        self.OutputFileLbl = QLabel(self.groupBox)
        self.OutputFileLbl.setObjectName(u"OutputFileLbl")

        self.gridLayout_2.addWidget(self.OutputFileLbl, 1, 0, 1, 1)

        self.OutputFileName = QLineEdit(self.groupBox)
        self.OutputFileName.setObjectName(u"OutputFileName")

        self.gridLayout_2.addWidget(self.OutputFileName, 1, 1, 1, 1)

        self.OutputSelectBtn = QPushButton(self.groupBox)
        self.OutputSelectBtn.setObjectName(u"OutputSelectBtn")

        self.gridLayout_2.addWidget(self.OutputSelectBtn, 1, 2, 1, 1)


        self.gridLayout.addWidget(self.groupBox, 3, 0, 1, 3)


        self.retranslateUi(TaxExportDlg)
        self.buttonBox.accepted.connect(TaxExportDlg.accept)
        self.buttonBox.rejected.connect(TaxExportDlg.reject)

        QMetaObject.connectSlotsByName(TaxExportDlg)
    # setupUi

    def retranslateUi(self, TaxExportDlg):
        TaxExportDlg.setWindowTitle(QCoreApplication.translate("TaxExportDlg", u"Select parameters and filename for tax report", None))
        self.XlsFileLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Excel file:", None))
        self.YearLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Year:", None))
        self.Year.setSuffix("")
        self.XlsSelectBtn.setText(QCoreApplication.translate("TaxExportDlg", u"...", None))
        self.AccountLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Account:", None))
        self.groupBox.setTitle(QCoreApplication.translate("TaxExportDlg", u"Update file \"\u0414\u0435\u043a\u043b\u0430\u0440\u0430\u0446\u0438\u044f\"", None))
        self.InitialSelectBtn.setText(QCoreApplication.translate("TaxExportDlg", u" ... ", None))
        self.InitialFileLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Initial file:", None))
        self.OutputFileLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Output file:", None))
        self.OutputSelectBtn.setText(QCoreApplication.translate("TaxExportDlg", u" ... ", None))
    # retranslateUi

