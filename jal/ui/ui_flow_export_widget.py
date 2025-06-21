# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'flow_export_widget.ui'
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
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpinBox, QWidget)

class Ui_MoneyFlowWidget(object):
    def setupUi(self, MoneyFlowWidget):
        if not MoneyFlowWidget.objectName():
            MoneyFlowWidget.setObjectName(u"MoneyFlowWidget")
        MoneyFlowWidget.resize(458, 158)
        self.gridLayout = QGridLayout(MoneyFlowWidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.XlsSelectBtn = QPushButton(MoneyFlowWidget)
        self.XlsSelectBtn.setObjectName(u"XlsSelectBtn")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.XlsSelectBtn.sizePolicy().hasHeightForWidth())
        self.XlsSelectBtn.setSizePolicy(sizePolicy)

        self.gridLayout.addWidget(self.XlsSelectBtn, 1, 2, 1, 1)

        self.SaveButton = QPushButton(MoneyFlowWidget)
        self.SaveButton.setObjectName(u"SaveButton")

        self.gridLayout.addWidget(self.SaveButton, 2, 2, 1, 1)

        self.XlsFileLbl = QLabel(MoneyFlowWidget)
        self.XlsFileLbl.setObjectName(u"XlsFileLbl")

        self.gridLayout.addWidget(self.XlsFileLbl, 1, 0, 1, 1)

        self.YearLbl = QLabel(MoneyFlowWidget)
        self.YearLbl.setObjectName(u"YearLbl")

        self.gridLayout.addWidget(self.YearLbl, 0, 0, 1, 1)

        self.Year = QSpinBox(MoneyFlowWidget)
        self.Year.setObjectName(u"Year")
        self.Year.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.Year.setMinimum(2010)
        self.Year.setMaximum(2030)
        self.Year.setValue(2020)

        self.gridLayout.addWidget(self.Year, 0, 1, 1, 2)

        self.XlsFileName = QLineEdit(MoneyFlowWidget)
        self.XlsFileName.setObjectName(u"XlsFileName")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.XlsFileName.sizePolicy().hasHeightForWidth())
        self.XlsFileName.setSizePolicy(sizePolicy1)

        self.gridLayout.addWidget(self.XlsFileName, 1, 1, 1, 1)


        self.retranslateUi(MoneyFlowWidget)

        QMetaObject.connectSlotsByName(MoneyFlowWidget)
    # setupUi

    def retranslateUi(self, MoneyFlowWidget):
        MoneyFlowWidget.setWindowTitle(QCoreApplication.translate("MoneyFlowWidget", u"Money Flow", None))
#if QT_CONFIG(tooltip)
        self.XlsSelectBtn.setToolTip(QCoreApplication.translate("MoneyFlowWidget", u"Select file", None))
#endif // QT_CONFIG(tooltip)
        self.XlsSelectBtn.setText(QCoreApplication.translate("MoneyFlowWidget", u"...", None))
        self.SaveButton.setText(QCoreApplication.translate("MoneyFlowWidget", u"Save Report", None))
        self.XlsFileLbl.setText(QCoreApplication.translate("MoneyFlowWidget", u"Excel file:", None))
        self.YearLbl.setText(QCoreApplication.translate("MoneyFlowWidget", u"Year:", None))
        self.Year.setSuffix("")
#if QT_CONFIG(tooltip)
        self.XlsFileName.setToolTip(QCoreApplication.translate("MoneyFlowWidget", u"File where to store tax report in Excel format", None))
#endif // QT_CONFIG(tooltip)
    # retranslateUi

