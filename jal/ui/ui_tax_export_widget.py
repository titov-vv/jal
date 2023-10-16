# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tax_export_widget.ui'
##
## Created by: Qt User Interface Compiler version 6.6.0
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGridLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpacerItem, QSpinBox,
    QVBoxLayout, QWidget)

from jal.widgets.reference_selector import AccountSelector

class Ui_TaxWidget(object):
    def setupUi(self, TaxWidget):
        if not TaxWidget.objectName():
            TaxWidget.setObjectName(u"TaxWidget")
        TaxWidget.resize(618, 321)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(TaxWidget.sizePolicy().hasHeightForWidth())
        TaxWidget.setSizePolicy(sizePolicy)
        self.gridLayout = QGridLayout(TaxWidget)
        self.gridLayout.setSpacing(2)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, -1, -1, -1)
        self.XlsFileName = QLineEdit(TaxWidget)
        self.XlsFileName.setObjectName(u"XlsFileName")
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.XlsFileName.sizePolicy().hasHeightForWidth())
        self.XlsFileName.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.XlsFileName, 3, 1, 1, 1)

        self.CountryLbl = QLabel(TaxWidget)
        self.CountryLbl.setObjectName(u"CountryLbl")

        self.gridLayout.addWidget(self.CountryLbl, 0, 0, 1, 1)

        self.AccountWidget = AccountSelector(TaxWidget)
        self.AccountWidget.setObjectName(u"AccountWidget")

        self.gridLayout.addWidget(self.AccountWidget, 2, 1, 1, 2)

        self.Country = QComboBox(TaxWidget)
        self.Country.setObjectName(u"Country")

        self.gridLayout.addWidget(self.Country, 0, 1, 1, 2)

        self.XlsFileLbl = QLabel(TaxWidget)
        self.XlsFileLbl.setObjectName(u"XlsFileLbl")

        self.gridLayout.addWidget(self.XlsFileLbl, 3, 0, 1, 1)

        self.Year = QSpinBox(TaxWidget)
        self.Year.setObjectName(u"Year")
        self.Year.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.Year.setMinimum(2010)
        self.Year.setMaximum(2030)
        self.Year.setValue(2020)

        self.gridLayout.addWidget(self.Year, 1, 1, 1, 2)

        self.XlsSelectBtn = QPushButton(TaxWidget)
        self.XlsSelectBtn.setObjectName(u"XlsSelectBtn")
        sizePolicy2 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.XlsSelectBtn.sizePolicy().hasHeightForWidth())
        self.XlsSelectBtn.setSizePolicy(sizePolicy2)

        self.gridLayout.addWidget(self.XlsSelectBtn, 3, 2, 1, 1)

        self.SaveButton = QPushButton(TaxWidget)
        self.SaveButton.setObjectName(u"SaveButton")

        self.gridLayout.addWidget(self.SaveButton, 11, 2, 1, 1)

        self.YearLbl = QLabel(TaxWidget)
        self.YearLbl.setObjectName(u"YearLbl")

        self.gridLayout.addWidget(self.YearLbl, 1, 0, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 12, 2, 1, 1)

        self.RussianSpecificFrame = QFrame(TaxWidget)
        self.RussianSpecificFrame.setObjectName(u"RussianSpecificFrame")
        self.RussianSpecificFrame.setFrameShape(QFrame.NoFrame)
        self.RussianSpecificFrame.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.RussianSpecificFrame)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.DlsgGroup = QGroupBox(self.RussianSpecificFrame)
        self.DlsgGroup.setObjectName(u"DlsgGroup")
        sizePolicy.setHeightForWidth(self.DlsgGroup.sizePolicy().hasHeightForWidth())
        self.DlsgGroup.setSizePolicy(sizePolicy)
        self.DlsgGroup.setFlat(False)
        self.DlsgGroup.setCheckable(True)
        self.DlsgGroup.setChecked(False)
        self.gridLayout_2 = QGridLayout(self.DlsgGroup)
        self.gridLayout_2.setSpacing(2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(6, 6, 6, 6)
        self.DlsgFileLbl = QLabel(self.DlsgGroup)
        self.DlsgFileLbl.setObjectName(u"DlsgFileLbl")

        self.gridLayout_2.addWidget(self.DlsgFileLbl, 0, 0, 1, 1)

        self.IncomeSourceBroker = QCheckBox(self.DlsgGroup)
        self.IncomeSourceBroker.setObjectName(u"IncomeSourceBroker")
        self.IncomeSourceBroker.setChecked(True)

        self.gridLayout_2.addWidget(self.IncomeSourceBroker, 1, 0, 1, 3)

        self.DividendsOnly = QCheckBox(self.DlsgGroup)
        self.DividendsOnly.setObjectName(u"DividendsOnly")

        self.gridLayout_2.addWidget(self.DividendsOnly, 2, 0, 1, 3)

        self.DlsgSelectBtn = QPushButton(self.DlsgGroup)
        self.DlsgSelectBtn.setObjectName(u"DlsgSelectBtn")

        self.gridLayout_2.addWidget(self.DlsgSelectBtn, 0, 2, 1, 1)

        self.DlsgFileName = QLineEdit(self.DlsgGroup)
        self.DlsgFileName.setObjectName(u"DlsgFileName")

        self.gridLayout_2.addWidget(self.DlsgFileName, 0, 1, 1, 1)


        self.verticalLayout.addWidget(self.DlsgGroup)


        self.gridLayout.addWidget(self.RussianSpecificFrame, 7, 0, 1, 3)

        self.AccountLbl = QLabel(TaxWidget)
        self.AccountLbl.setObjectName(u"AccountLbl")

        self.gridLayout.addWidget(self.AccountLbl, 2, 0, 1, 1)

        self.WarningLbl = QLabel(TaxWidget)
        self.WarningLbl.setObjectName(u"WarningLbl")
        font = QFont()
        font.setItalic(True)
        self.WarningLbl.setFont(font)

        self.gridLayout.addWidget(self.WarningLbl, 5, 0, 1, 1)

        self.line = QFrame(TaxWidget)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.gridLayout.addWidget(self.line, 4, 0, 1, 3)

        self.NoSettlement = QCheckBox(TaxWidget)
        self.NoSettlement.setObjectName(u"NoSettlement")

        self.gridLayout.addWidget(self.NoSettlement, 6, 0, 1, 1)


        self.retranslateUi(TaxWidget)

        QMetaObject.connectSlotsByName(TaxWidget)
    # setupUi

    def retranslateUi(self, TaxWidget):
        TaxWidget.setWindowTitle(QCoreApplication.translate("TaxWidget", u"Taxes", None))
#if QT_CONFIG(tooltip)
        self.XlsFileName.setToolTip(QCoreApplication.translate("TaxWidget", u"File where to store tax report in Excel format", None))
#endif // QT_CONFIG(tooltip)
        self.CountryLbl.setText(QCoreApplication.translate("TaxWidget", u"Country:", None))
#if QT_CONFIG(tooltip)
        self.AccountWidget.setToolTip(QCoreApplication.translate("TaxWidget", u"Foreign account to prepare tax report for", None))
#endif // QT_CONFIG(tooltip)
        self.XlsFileLbl.setText(QCoreApplication.translate("TaxWidget", u"Excel file:", None))
        self.Year.setSuffix("")
#if QT_CONFIG(tooltip)
        self.XlsSelectBtn.setToolTip(QCoreApplication.translate("TaxWidget", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.XlsSelectBtn.setText(QCoreApplication.translate("TaxWidget", u"...", None))
        self.SaveButton.setText(QCoreApplication.translate("TaxWidget", u"Save Report", None))
        self.YearLbl.setText(QCoreApplication.translate("TaxWidget", u"Year:", None))
        self.DlsgGroup.setTitle(QCoreApplication.translate("TaxWidget", u"Create tax form in \"\u0414\u0435\u043a\u043b\u0430\u0440\u0430\u0446\u0438\u044f\" program format (*.dcX)", None))
        self.DlsgFileLbl.setText(QCoreApplication.translate("TaxWidget", u"Output file:", None))
        self.IncomeSourceBroker.setText(QCoreApplication.translate("TaxWidget", u"Use broker name as income source", None))
        self.DividendsOnly.setText(QCoreApplication.translate("TaxWidget", u"Update only information about dividends", None))
#if QT_CONFIG(tooltip)
        self.DlsgSelectBtn.setToolTip(QCoreApplication.translate("TaxWidget", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.DlsgSelectBtn.setText(QCoreApplication.translate("TaxWidget", u" ... ", None))
#if QT_CONFIG(tooltip)
        self.DlsgFileName.setToolTip(QCoreApplication.translate("TaxWidget", u"File where to store russian tax form", None))
#endif // QT_CONFIG(tooltip)
        self.AccountLbl.setText(QCoreApplication.translate("TaxWidget", u"Account:", None))
        self.WarningLbl.setText(QCoreApplication.translate("TaxWidget", u"Below functions are experimental - use it with care", None))
        self.NoSettlement.setText(QCoreApplication.translate("TaxWidget", u"Do not use settlement date for currency rates", None))
    # retranslateUi

