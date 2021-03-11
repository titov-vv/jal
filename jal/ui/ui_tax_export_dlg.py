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

from jal.widgets.reference_selector import AccountSelector


class Ui_TaxExportDlg(object):
    def setupUi(self, TaxExportDlg):
        if not TaxExportDlg.objectName():
            TaxExportDlg.setObjectName(u"TaxExportDlg")
        TaxExportDlg.resize(602, 290)
        self.gridLayout = QGridLayout(TaxExportDlg)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setHorizontalSpacing(6)
        self.gridLayout.setContentsMargins(9, 9, 9, 9)
        self.line = QFrame(TaxExportDlg)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.gridLayout.addWidget(self.line, 4, 0, 1, 4)

        self.XlsSelectBtn = QPushButton(TaxExportDlg)
        self.XlsSelectBtn.setObjectName(u"XlsSelectBtn")
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.XlsSelectBtn.sizePolicy().hasHeightForWidth())
        self.XlsSelectBtn.setSizePolicy(sizePolicy)

        self.gridLayout.addWidget(self.XlsSelectBtn, 3, 2, 1, 1)

        self.WarningLbl = QLabel(TaxExportDlg)
        self.WarningLbl.setObjectName(u"WarningLbl")
        font = QFont()
        font.setItalic(True)
        self.WarningLbl.setFont(font)

        self.gridLayout.addWidget(self.WarningLbl, 5, 0, 1, 4)

        self.DlsgGroup = QGroupBox(TaxExportDlg)
        self.DlsgGroup.setObjectName(u"DlsgGroup")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.DlsgGroup.sizePolicy().hasHeightForWidth())
        self.DlsgGroup.setSizePolicy(sizePolicy1)
        self.DlsgGroup.setFlat(False)
        self.DlsgGroup.setCheckable(True)
        self.DlsgGroup.setChecked(False)
        self.gridLayout_2 = QGridLayout(self.DlsgGroup)
        self.gridLayout_2.setSpacing(2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(6, 6, 6, 6)
        self.DlsgInFileName = QLineEdit(self.DlsgGroup)
        self.DlsgInFileName.setObjectName(u"DlsgInFileName")

        self.gridLayout_2.addWidget(self.DlsgInFileName, 0, 1, 1, 1)

        self.OutputSelectBtn = QPushButton(self.DlsgGroup)
        self.OutputSelectBtn.setObjectName(u"OutputSelectBtn")

        self.gridLayout_2.addWidget(self.OutputSelectBtn, 1, 2, 1, 1)

        self.DlsgOutFileName = QLineEdit(self.DlsgGroup)
        self.DlsgOutFileName.setObjectName(u"DlsgOutFileName")

        self.gridLayout_2.addWidget(self.DlsgOutFileName, 1, 1, 1, 1)

        self.InitialFileLbl = QLabel(self.DlsgGroup)
        self.InitialFileLbl.setObjectName(u"InitialFileLbl")

        self.gridLayout_2.addWidget(self.InitialFileLbl, 0, 0, 1, 1)

        self.OutputFileLbl = QLabel(self.DlsgGroup)
        self.OutputFileLbl.setObjectName(u"OutputFileLbl")

        self.gridLayout_2.addWidget(self.OutputFileLbl, 1, 0, 1, 1)

        self.InitialSelectBtn = QPushButton(self.DlsgGroup)
        self.InitialSelectBtn.setObjectName(u"InitialSelectBtn")

        self.gridLayout_2.addWidget(self.InitialSelectBtn, 0, 2, 1, 1)

        self.DividendsOnly = QCheckBox(self.DlsgGroup)
        self.DividendsOnly.setObjectName(u"DividendsOnly")

        self.gridLayout_2.addWidget(self.DividendsOnly, 2, 0, 1, 3)


        self.gridLayout.addWidget(self.DlsgGroup, 7, 0, 1, 4)

        self.Year = QSpinBox(TaxExportDlg)
        self.Year.setObjectName(u"Year")
        self.Year.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.Year.setMinimum(2010)
        self.Year.setMaximum(2030)
        self.Year.setValue(2020)

        self.gridLayout.addWidget(self.Year, 1, 1, 1, 2)

        self.XlsFileName = QLineEdit(TaxExportDlg)
        self.XlsFileName.setObjectName(u"XlsFileName")
        sizePolicy2 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.XlsFileName.sizePolicy().hasHeightForWidth())
        self.XlsFileName.setSizePolicy(sizePolicy2)

        self.gridLayout.addWidget(self.XlsFileName, 3, 1, 1, 1)

        self.AccountWidget = AccountSelector(TaxExportDlg)
        self.AccountWidget.setObjectName(u"AccountWidget")

        self.gridLayout.addWidget(self.AccountWidget, 2, 1, 1, 2)

        self.YearLbl = QLabel(TaxExportDlg)
        self.YearLbl.setObjectName(u"YearLbl")

        self.gridLayout.addWidget(self.YearLbl, 1, 0, 1, 1)

        self.buttonBox = QDialogButtonBox(TaxExportDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Vertical)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 1, 3, 3, 1)

        self.AccountLbl = QLabel(TaxExportDlg)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.gridLayout.addWidget(self.AccountLbl, 2, 0, 1, 1)

        self.XlsFileLbl = QLabel(TaxExportDlg)
        self.XlsFileLbl.setObjectName(u"XlsFileLbl")

        self.gridLayout.addWidget(self.XlsFileLbl, 3, 0, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 9, 0, 1, 1)

        self.NoSettlement = QCheckBox(TaxExportDlg)
        self.NoSettlement.setObjectName(u"NoSettlement")

        self.gridLayout.addWidget(self.NoSettlement, 8, 0, 1, 4)

        QWidget.setTabOrder(self.Year, self.XlsFileName)
        QWidget.setTabOrder(self.XlsFileName, self.XlsSelectBtn)
        QWidget.setTabOrder(self.XlsSelectBtn, self.DlsgGroup)
        QWidget.setTabOrder(self.DlsgGroup, self.DlsgInFileName)
        QWidget.setTabOrder(self.DlsgInFileName, self.InitialSelectBtn)
        QWidget.setTabOrder(self.InitialSelectBtn, self.DlsgOutFileName)
        QWidget.setTabOrder(self.DlsgOutFileName, self.OutputSelectBtn)

        self.retranslateUi(TaxExportDlg)
        self.buttonBox.accepted.connect(TaxExportDlg.accept)
        self.buttonBox.rejected.connect(TaxExportDlg.reject)

        QMetaObject.connectSlotsByName(TaxExportDlg)
    # setupUi

    def retranslateUi(self, TaxExportDlg):
        TaxExportDlg.setWindowTitle(QCoreApplication.translate("TaxExportDlg", u"Select parameters and files for tax report", None))
#if QT_CONFIG(tooltip)
        self.XlsSelectBtn.setToolTip(QCoreApplication.translate("TaxExportDlg", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.XlsSelectBtn.setText(QCoreApplication.translate("TaxExportDlg", u"...", None))
        self.WarningLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Below functions are experimental - use it with care", None))
        self.DlsgGroup.setTitle(QCoreApplication.translate("TaxExportDlg", u"Update file \"\u0414\u0435\u043a\u043b\u0430\u0440\u0430\u0446\u0438\u044f\" (*.dc0)", None))
#if QT_CONFIG(tooltip)
        self.DlsgInFileName.setToolTip(QCoreApplication.translate("TaxExportDlg", u"File to use as a template for russian tax form", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.OutputSelectBtn.setToolTip(QCoreApplication.translate("TaxExportDlg", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.OutputSelectBtn.setText(QCoreApplication.translate("TaxExportDlg", u" ... ", None))
#if QT_CONFIG(tooltip)
        self.DlsgOutFileName.setToolTip(QCoreApplication.translate("TaxExportDlg", u"File where to store russian tax form", None))
#endif // QT_CONFIG(tooltip)
        self.InitialFileLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Initial file:", None))
        self.OutputFileLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Output file:", None))
#if QT_CONFIG(tooltip)
        self.InitialSelectBtn.setToolTip(QCoreApplication.translate("TaxExportDlg", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.InitialSelectBtn.setText(QCoreApplication.translate("TaxExportDlg", u" ... ", None))
        self.DividendsOnly.setText(QCoreApplication.translate("TaxExportDlg", u"Update only information about dividends", None))
        self.Year.setSuffix("")
#if QT_CONFIG(tooltip)
        self.XlsFileName.setToolTip(QCoreApplication.translate("TaxExportDlg", u"File where to store tax report in Excel format", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.AccountWidget.setToolTip(QCoreApplication.translate("TaxExportDlg", u"Foreign account to prepare tax report for", None))
#endif // QT_CONFIG(tooltip)
        self.YearLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Year:", None))
        self.AccountLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Account:", None))
        self.XlsFileLbl.setText(QCoreApplication.translate("TaxExportDlg", u"Excel file:", None))
        self.NoSettlement.setText(QCoreApplication.translate("TaxExportDlg", u"Do not use settlement date for currency rates", None))
    # retranslateUi

