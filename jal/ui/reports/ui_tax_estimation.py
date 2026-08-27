# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tax_estimation.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QSizePolicy, QSpacerItem,
    QTableView, QVBoxLayout, QWidget)

class Ui_TaxEstimationDialog(object):
    def setupUi(self, TaxEstimationDialog):
        if not TaxEstimationDialog.objectName():
            TaxEstimationDialog.setObjectName(u"TaxEstimationDialog")
        TaxEstimationDialog.resize(754, 191)
        self.verticalLayout = QVBoxLayout(TaxEstimationDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.RateFrame = QFrame(TaxEstimationDialog)
        self.RateFrame.setObjectName(u"RateFrame")
        self.RateFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.RateFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.RateFrame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.LastQuoteLbl = QLabel(self.RateFrame)
        self.LastQuoteLbl.setObjectName(u"LastQuoteLbl")
        font = QFont()
        font.setBold(True)
        self.LastQuoteLbl.setFont(font)

        self.horizontalLayout_2.addWidget(self.LastQuoteLbl)

        self.QuoteLbl = QLabel(self.RateFrame)
        self.QuoteLbl.setObjectName(u"QuoteLbl")

        self.horizontalLayout_2.addWidget(self.QuoteLbl)

        self.RateSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.RateSpacer)


        self.horizontalLayout.addWidget(self.RateFrame)

        self.QuoteFrame = QFrame(TaxEstimationDialog)
        self.QuoteFrame.setObjectName(u"QuoteFrame")
        self.QuoteFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.QuoteFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.QuoteFrame)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.CurrentRateLbl = QLabel(self.QuoteFrame)
        self.CurrentRateLbl.setObjectName(u"CurrentRateLbl")
        self.CurrentRateLbl.setFont(font)

        self.horizontalLayout_3.addWidget(self.CurrentRateLbl)

        self.RateLbl = QLabel(self.QuoteFrame)
        self.RateLbl.setObjectName(u"RateLbl")

        self.horizontalLayout_3.addWidget(self.RateLbl)

        self.QuoteSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.QuoteSpacer)


        self.horizontalLayout.addWidget(self.QuoteFrame)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.DealsView = QTableView(TaxEstimationDialog)
        self.DealsView.setObjectName(u"DealsView")
        self.DealsView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.DealsView.verticalHeader().setVisible(False)
        self.DealsView.verticalHeader().setMinimumSectionSize(20)

        self.verticalLayout.addWidget(self.DealsView)


        self.retranslateUi(TaxEstimationDialog)

        QMetaObject.connectSlotsByName(TaxEstimationDialog)
    # setupUi

    def retranslateUi(self, TaxEstimationDialog):
        TaxEstimationDialog.setWindowTitle(QCoreApplication.translate("TaxEstimationDialog", u"Tax estimation", None))
        self.LastQuoteLbl.setText(QCoreApplication.translate("TaxEstimationDialog", u"Last quote:", None))
        self.QuoteLbl.setText(QCoreApplication.translate("TaxEstimationDialog", u"X.XX", None))
        self.CurrentRateLbl.setText(QCoreApplication.translate("TaxEstimationDialog", u"Current rate:", None))
        self.RateLbl.setText(QCoreApplication.translate("TaxEstimationDialog", u"X.XX", None))
    # retranslateUi

