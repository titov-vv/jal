# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tax_export_widget.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

class Ui_TaxWidget(object):
    def setupUi(self, TaxWidget):
        if not TaxWidget.objectName():
            TaxWidget.setObjectName(u"TaxWidget")
        TaxWidget.resize(618, 473)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(TaxWidget.sizePolicy().hasHeightForWidth())
        TaxWidget.setSizePolicy(sizePolicy)
        self.MainLayout = QGridLayout(TaxWidget)
        self.MainLayout.setSpacing(2)
        self.MainLayout.setObjectName(u"MainLayout")
        self.MainLayout.setContentsMargins(2, 2, 2, 2)
        self.XlsSelectBtn = QPushButton(TaxWidget)
        self.XlsSelectBtn.setObjectName(u"XlsSelectBtn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.XlsSelectBtn.sizePolicy().hasHeightForWidth())
        self.XlsSelectBtn.setSizePolicy(sizePolicy1)

        self.MainLayout.addWidget(self.XlsSelectBtn, 3, 2, 1, 1)

        self.Year = QSpinBox(TaxWidget)
        self.Year.setObjectName(u"Year")
        self.Year.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)
        self.Year.setMinimum(2010)
        self.Year.setMaximum(2030)
        self.Year.setValue(2025)

        self.MainLayout.addWidget(self.Year, 1, 1, 1, 2)

        self.XlsFileName = QLineEdit(TaxWidget)
        self.XlsFileName.setObjectName(u"XlsFileName")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.XlsFileName.sizePolicy().hasHeightForWidth())
        self.XlsFileName.setSizePolicy(sizePolicy2)

        self.MainLayout.addWidget(self.XlsFileName, 3, 1, 1, 1)

        self.PtBox = QGroupBox(TaxWidget)
        self.PtBox.setObjectName(u"PtBox")
        self.PtLayout = QVBoxLayout(self.PtBox)
        self.PtLayout.setSpacing(2)
        self.PtLayout.setObjectName(u"PtLayout")
        self.PtLayout.setContentsMargins(0, 0, 0, 0)
        self.Pt_OneCurrencyRate = QCheckBox(self.PtBox)
        self.Pt_OneCurrencyRate.setObjectName(u"Pt_OneCurrencyRate")
        self.Pt_OneCurrencyRate.setChecked(True)

        self.PtLayout.addWidget(self.Pt_OneCurrencyRate)

        self.Pt_RateComment = QLabel(self.PtBox)
        self.Pt_RateComment.setObjectName(u"Pt_RateComment")
        self.Pt_RateComment.setEnabled(True)

        self.PtLayout.addWidget(self.Pt_RateComment)

        self.IRS_Modelo3Group = QGroupBox(self.PtBox)
        self.IRS_Modelo3Group.setObjectName(u"IRS_Modelo3Group")
        self.IRS_Modelo3Group.setCheckable(True)
        self.IRS_Modelo3Group.setChecked(False)
        self.gridLayout = QGridLayout(self.IRS_Modelo3Group)
        self.gridLayout.setSpacing(2)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(6, 6, 6, 6)
        self.IRS_Modelo3FileLbl = QLabel(self.IRS_Modelo3Group)
        self.IRS_Modelo3FileLbl.setObjectName(u"IRS_Modelo3FileLbl")

        self.gridLayout.addWidget(self.IRS_Modelo3FileLbl, 0, 0, 1, 1)

        self.IRS_Modelo3Filename = QLineEdit(self.IRS_Modelo3Group)
        self.IRS_Modelo3Filename.setObjectName(u"IRS_Modelo3Filename")

        self.gridLayout.addWidget(self.IRS_Modelo3Filename, 0, 1, 1, 1)

        self.IRS_Modelo3SelectBtn = QPushButton(self.IRS_Modelo3Group)
        self.IRS_Modelo3SelectBtn.setObjectName(u"IRS_Modelo3SelectBtn")

        self.gridLayout.addWidget(self.IRS_Modelo3SelectBtn, 0, 2, 1, 1)


        self.PtLayout.addWidget(self.IRS_Modelo3Group)


        self.MainLayout.addWidget(self.PtBox, 8, 0, 1, 3)

        self.AccountLbl = QLabel(TaxWidget)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.MainLayout.addWidget(self.AccountLbl, 2, 0, 1, 1)

        self.XlsFileLbl = QLabel(TaxWidget)
        self.XlsFileLbl.setObjectName(u"XlsFileLbl")

        self.MainLayout.addWidget(self.XlsFileLbl, 3, 0, 1, 1)

        self.RuBox = QGroupBox(TaxWidget)
        self.RuBox.setObjectName(u"RuBox")
        self.verticalLayout = QVBoxLayout(self.RuBox)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.Ru_NoSettlement = QCheckBox(self.RuBox)
        self.Ru_NoSettlement.setObjectName(u"Ru_NoSettlement")

        self.verticalLayout.addWidget(self.Ru_NoSettlement)

        self.Ru_DividendsOnly = QCheckBox(self.RuBox)
        self.Ru_DividendsOnly.setObjectName(u"Ru_DividendsOnly")

        self.verticalLayout.addWidget(self.Ru_DividendsOnly)

        self.Ru_IncomeSourceBroker = QCheckBox(self.RuBox)
        self.Ru_IncomeSourceBroker.setObjectName(u"Ru_IncomeSourceBroker")
        self.Ru_IncomeSourceBroker.setChecked(True)

        self.verticalLayout.addWidget(self.Ru_IncomeSourceBroker)

        self.Ndfl3Group = QGroupBox(self.RuBox)
        self.Ndfl3Group.setObjectName(u"Ndfl3Group")
        self.Ndfl3Group.setEnabled(True)
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.Ndfl3Group.sizePolicy().hasHeightForWidth())
        self.Ndfl3Group.setSizePolicy(sizePolicy3)
        self.Ndfl3Group.setFlat(False)
        self.Ndfl3Group.setCheckable(True)
        self.Ndfl3Group.setChecked(False)
        self.gridLayout_2 = QGridLayout(self.Ndfl3Group)
        self.gridLayout_2.setSpacing(2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(6, 6, 6, 6)
        self.Ndfl3FileLbl = QLabel(self.Ndfl3Group)
        self.Ndfl3FileLbl.setObjectName(u"Ndfl3FileLbl")

        self.gridLayout_2.addWidget(self.Ndfl3FileLbl, 1, 0, 1, 1)

        self.Ndfl3SelectBtn = QPushButton(self.Ndfl3Group)
        self.Ndfl3SelectBtn.setObjectName(u"Ndfl3SelectBtn")

        self.gridLayout_2.addWidget(self.Ndfl3SelectBtn, 1, 2, 1, 1)

        self.Ndfl3FileName = QLineEdit(self.Ndfl3Group)
        self.Ndfl3FileName.setObjectName(u"Ndfl3FileName")

        self.gridLayout_2.addWidget(self.Ndfl3FileName, 1, 1, 1, 1)


        self.verticalLayout.addWidget(self.Ndfl3Group)


        self.MainLayout.addWidget(self.RuBox, 7, 0, 1, 3)

        self.Country = QComboBox(TaxWidget)
        self.Country.setObjectName(u"Country")

        self.MainLayout.addWidget(self.Country, 0, 1, 1, 2)

        self.CountryLbl = QLabel(TaxWidget)
        self.CountryLbl.setObjectName(u"CountryLbl")

        self.MainLayout.addWidget(self.CountryLbl, 0, 0, 1, 1)

        self.YearLbl = QLabel(TaxWidget)
        self.YearLbl.setObjectName(u"YearLbl")

        self.MainLayout.addWidget(self.YearLbl, 1, 0, 1, 1)

        self.SaveButton = QPushButton(TaxWidget)
        self.SaveButton.setObjectName(u"SaveButton")

        self.MainLayout.addWidget(self.SaveButton, 11, 2, 1, 1)

        self.Account = QComboBox(TaxWidget)
        self.Account.setObjectName(u"Account")

        self.MainLayout.addWidget(self.Account, 2, 1, 1, 2)


        self.retranslateUi(TaxWidget)

        QMetaObject.connectSlotsByName(TaxWidget)
    # setupUi

    def retranslateUi(self, TaxWidget):
        TaxWidget.setWindowTitle(QCoreApplication.translate("TaxWidget", u"Select parameters of investment tax report", None))
#if QT_CONFIG(tooltip)
        self.XlsSelectBtn.setToolTip(QCoreApplication.translate("TaxWidget", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.XlsSelectBtn.setText(QCoreApplication.translate("TaxWidget", u"...", None))
        self.Year.setSuffix("")
#if QT_CONFIG(tooltip)
        self.XlsFileName.setToolTip(QCoreApplication.translate("TaxWidget", u"File where to store tax report in Excel format", None))
#endif // QT_CONFIG(tooltip)
        self.PtBox.setTitle(QCoreApplication.translate("TaxWidget", u"Additional parameters (Portugal)", None))
        self.Pt_OneCurrencyRate.setText(QCoreApplication.translate("TaxWidget", u"Use only realization (Sell) currency rate", None))
        self.Pt_RateComment.setText(QCoreApplication.translate("TaxWidget", u"     (This selection depends CIRS a.23 interpretation)", None))
        self.IRS_Modelo3Group.setTitle(QCoreApplication.translate("TaxWidget", u"Create XML records to introduce in Modelo-3 form", None))
        self.IRS_Modelo3FileLbl.setText(QCoreApplication.translate("TaxWidget", u"Output file:", None))
#if QT_CONFIG(tooltip)
        self.IRS_Modelo3Filename.setToolTip(QCoreApplication.translate("TaxWidget", u"File where to store russian tax form", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.IRS_Modelo3SelectBtn.setToolTip(QCoreApplication.translate("TaxWidget", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.IRS_Modelo3SelectBtn.setText(QCoreApplication.translate("TaxWidget", u" ... ", None))
        self.AccountLbl.setText(QCoreApplication.translate("TaxWidget", u"Account:", None))
        self.XlsFileLbl.setText(QCoreApplication.translate("TaxWidget", u"Excel file:", None))
        self.RuBox.setTitle(QCoreApplication.translate("TaxWidget", u"Additional parameters (Russia)", None))
        self.Ru_NoSettlement.setText(QCoreApplication.translate("TaxWidget", u"Do not use settlement date for currency rates", None))
        self.Ru_DividendsOnly.setText(QCoreApplication.translate("TaxWidget", u"Update only information about dividends", None))
        self.Ru_IncomeSourceBroker.setText(QCoreApplication.translate("TaxWidget", u"Use broker name as income source", None))
        self.Ndfl3Group.setTitle(QCoreApplication.translate("TaxWidget", u"Create tax form in \"\u0414\u0435\u043a\u043b\u0430\u0440\u0430\u0446\u0438\u044f 2.0\" program format", None))
        self.Ndfl3FileLbl.setText(QCoreApplication.translate("TaxWidget", u"Output file:", None))
#if QT_CONFIG(tooltip)
        self.Ndfl3SelectBtn.setToolTip(QCoreApplication.translate("TaxWidget", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.Ndfl3SelectBtn.setText(QCoreApplication.translate("TaxWidget", u" ... ", None))
#if QT_CONFIG(tooltip)
        self.Ndfl3FileName.setToolTip(QCoreApplication.translate("TaxWidget", u"File where to store russian tax form", None))
#endif // QT_CONFIG(tooltip)
        self.CountryLbl.setText(QCoreApplication.translate("TaxWidget", u"Country:", None))
        self.YearLbl.setText(QCoreApplication.translate("TaxWidget", u"Year:", None))
        self.SaveButton.setText(QCoreApplication.translate("TaxWidget", u"Save Report", None))
    # retranslateUi

