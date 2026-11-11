# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tax_export_widget.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDateEdit, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
    QSpacerItem, QSpinBox, QVBoxLayout, QWidget)

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
        self.MainLayout.setObjectName(u"MainLayout")
        self.XlsSelectBtn = QPushButton(TaxWidget)
        self.XlsSelectBtn.setObjectName(u"XlsSelectBtn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.XlsSelectBtn.sizePolicy().hasHeightForWidth())
        self.XlsSelectBtn.setSizePolicy(sizePolicy1)

        self.MainLayout.addWidget(self.XlsSelectBtn, 5, 2, 1, 1)

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

        self.MainLayout.addWidget(self.XlsFileName, 5, 1, 1, 1)

        self.AccountLbl = QLabel(TaxWidget)
        self.AccountLbl.setObjectName(u"AccountLbl")
        self.AccountLbl.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)

        self.MainLayout.addWidget(self.AccountLbl, 4, 0, 1, 1)

        self.XlsFileLbl = QLabel(TaxWidget)
        self.XlsFileLbl.setObjectName(u"XlsFileLbl")

        self.MainLayout.addWidget(self.XlsFileLbl, 5, 0, 1, 1)

        self.OptionsBox = QGroupBox(TaxWidget)
        self.OptionsBox.setObjectName(u"OptionsBox")
        self.OptionsLayout = QVBoxLayout(self.OptionsBox)
        self.OptionsLayout.setObjectName(u"OptionsLayout")
        self.ReportOptionsLayout = QGridLayout()
        self.ReportOptionsLayout.setObjectName(u"ReportOptionsLayout")

        self.OptionsLayout.addLayout(self.ReportOptionsLayout)

        self.FormGroup = QGroupBox(self.OptionsBox)
        self.FormGroup.setObjectName(u"FormGroup")
        self.FormGroup.setCheckable(True)
        self.FormGroup.setChecked(False)
        self.FormLayout = QGridLayout(self.FormGroup)
        self.FormLayout.setObjectName(u"FormLayout")
        self.FormFileLbl = QLabel(self.FormGroup)
        self.FormFileLbl.setObjectName(u"FormFileLbl")

        self.FormLayout.addWidget(self.FormFileLbl, 0, 0, 1, 1)

        self.FormFileName = QLineEdit(self.FormGroup)
        self.FormFileName.setObjectName(u"FormFileName")

        self.FormLayout.addWidget(self.FormFileName, 0, 1, 1, 1)

        self.FormSelectBtn = QPushButton(self.FormGroup)
        self.FormSelectBtn.setObjectName(u"FormSelectBtn")

        self.FormLayout.addWidget(self.FormSelectBtn, 0, 2, 1, 1)


        self.OptionsLayout.addWidget(self.FormGroup)


        self.MainLayout.addWidget(self.OptionsBox, 7, 0, 1, 3)

        self.Country = QComboBox(TaxWidget)
        self.Country.setObjectName(u"Country")

        self.MainLayout.addWidget(self.Country, 0, 1, 1, 2)

        self.CountryLbl = QLabel(TaxWidget)
        self.CountryLbl.setObjectName(u"CountryLbl")

        self.MainLayout.addWidget(self.CountryLbl, 0, 0, 1, 1)

        self.YearLbl = QLabel(TaxWidget)
        self.YearLbl.setObjectName(u"YearLbl")

        self.MainLayout.addWidget(self.YearLbl, 1, 0, 1, 1)

        self.PeriodLbl = QLabel(TaxWidget)
        self.PeriodLbl.setObjectName(u"PeriodLbl")

        self.MainLayout.addWidget(self.PeriodLbl, 2, 0, 1, 1)

        self.PeriodLayout = QHBoxLayout()
        self.PeriodLayout.setObjectName(u"PeriodLayout")
        self.PeriodFrom = QDateEdit(TaxWidget)
        self.PeriodFrom.setObjectName(u"PeriodFrom")
        self.PeriodFrom.setCalendarPopup(True)

        self.PeriodLayout.addWidget(self.PeriodFrom)

        self.PeriodDash = QLabel(TaxWidget)
        self.PeriodDash.setObjectName(u"PeriodDash")
        self.PeriodDash.setText(u"-")

        self.PeriodLayout.addWidget(self.PeriodDash)

        self.PeriodTo = QDateEdit(TaxWidget)
        self.PeriodTo.setObjectName(u"PeriodTo")
        self.PeriodTo.setCalendarPopup(True)

        self.PeriodLayout.addWidget(self.PeriodTo)

        self.PeriodSpacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.PeriodLayout.addItem(self.PeriodSpacer)


        self.MainLayout.addLayout(self.PeriodLayout, 2, 1, 1, 2)

        self.ResidenceLbl = QLabel(TaxWidget)
        self.ResidenceLbl.setObjectName(u"ResidenceLbl")
        self.ResidenceLbl.setWordWrap(True)

        self.MainLayout.addWidget(self.ResidenceLbl, 3, 1, 1, 2)

        self.SaveButton = QPushButton(TaxWidget)
        self.SaveButton.setObjectName(u"SaveButton")

        self.MainLayout.addWidget(self.SaveButton, 11, 2, 1, 1)

        self.Accounts = QListWidget(TaxWidget)
        self.Accounts.setObjectName(u"Accounts")
        self.Accounts.setMaximumSize(QSize(16777215, 100))

        self.MainLayout.addWidget(self.Accounts, 4, 1, 1, 2)

#if QT_CONFIG(shortcut)
        self.AccountLbl.setBuddy(self.Accounts)
        self.XlsFileLbl.setBuddy(self.XlsFileName)
        self.FormFileLbl.setBuddy(self.FormFileName)
        self.CountryLbl.setBuddy(self.Country)
        self.YearLbl.setBuddy(self.Year)
        self.PeriodLbl.setBuddy(self.PeriodFrom)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.Country, self.Year)
        QWidget.setTabOrder(self.Year, self.PeriodFrom)
        QWidget.setTabOrder(self.PeriodFrom, self.PeriodTo)
        QWidget.setTabOrder(self.PeriodTo, self.Accounts)
        QWidget.setTabOrder(self.Accounts, self.XlsFileName)
        QWidget.setTabOrder(self.XlsFileName, self.XlsSelectBtn)
        QWidget.setTabOrder(self.XlsSelectBtn, self.FormGroup)
        QWidget.setTabOrder(self.FormGroup, self.FormFileName)
        QWidget.setTabOrder(self.FormFileName, self.FormSelectBtn)
        QWidget.setTabOrder(self.FormSelectBtn, self.SaveButton)

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
        self.AccountLbl.setText(QCoreApplication.translate("TaxWidget", u"&Accounts:", None))
        self.XlsFileLbl.setText(QCoreApplication.translate("TaxWidget", u"&Excel file:", None))
        self.OptionsBox.setTitle(QCoreApplication.translate("TaxWidget", u"Additional parameters", None))
        self.FormFileLbl.setText(QCoreApplication.translate("TaxWidget", u"Output &file:", None))
#if QT_CONFIG(tooltip)
        self.FormFileName.setToolTip(QCoreApplication.translate("TaxWidget", u"File where to store tax form", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.FormSelectBtn.setToolTip(QCoreApplication.translate("TaxWidget", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.FormSelectBtn.setText(QCoreApplication.translate("TaxWidget", u" ... ", None))
        self.CountryLbl.setText(QCoreApplication.translate("TaxWidget", u"&Country:", None))
        self.YearLbl.setText(QCoreApplication.translate("TaxWidget", u"&Year:", None))
        self.PeriodLbl.setText(QCoreApplication.translate("TaxWidget", u"&Period:", None))
        self.PeriodFrom.setDisplayFormat(QCoreApplication.translate("TaxWidget", u"dd/MM/yyyy", None))
        self.PeriodTo.setDisplayFormat(QCoreApplication.translate("TaxWidget", u"dd/MM/yyyy", None))
        self.SaveButton.setText(QCoreApplication.translate("TaxWidget", u"Save Report", None))
    # retranslateUi

