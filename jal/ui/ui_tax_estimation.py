# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tax_estimation.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_TaxEstimationDialog(object):
    def setupUi(self, TaxEstimationDialog):
        if not TaxEstimationDialog.objectName():
            TaxEstimationDialog.setObjectName(u"TaxEstimationDialog")
        TaxEstimationDialog.resize(754, 191)
        self.verticalLayout = QVBoxLayout(TaxEstimationDialog)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.RateFrame = QFrame(TaxEstimationDialog)
        self.RateFrame.setObjectName(u"RateFrame")
        self.RateFrame.setFrameShape(QFrame.StyledPanel)
        self.RateFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.RateFrame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.LastQuoteLbl = QLabel(self.RateFrame)
        self.LastQuoteLbl.setObjectName(u"LastQuoteLbl")
        font = QFont()
        font.setBold(True)
        font.setWeight(75)
        self.LastQuoteLbl.setFont(font)

        self.horizontalLayout_2.addWidget(self.LastQuoteLbl)

        self.QuoteLbl = QLabel(self.RateFrame)
        self.QuoteLbl.setObjectName(u"QuoteLbl")

        self.horizontalLayout_2.addWidget(self.QuoteLbl)

        self.RateSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.RateSpacer)


        self.horizontalLayout.addWidget(self.RateFrame)

        self.QuoteFrame = QFrame(TaxEstimationDialog)
        self.QuoteFrame.setObjectName(u"QuoteFrame")
        self.QuoteFrame.setFrameShape(QFrame.StyledPanel)
        self.QuoteFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.QuoteFrame)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.CurrentRateLbl = QLabel(self.QuoteFrame)
        self.CurrentRateLbl.setObjectName(u"CurrentRateLbl")
        self.CurrentRateLbl.setFont(font)

        self.horizontalLayout_3.addWidget(self.CurrentRateLbl)

        self.RateLbl = QLabel(self.QuoteFrame)
        self.RateLbl.setObjectName(u"RateLbl")

        self.horizontalLayout_3.addWidget(self.RateLbl)

        self.QuoteSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.QuoteSpacer)


        self.horizontalLayout.addWidget(self.QuoteFrame)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.DealsView = QTableView(TaxEstimationDialog)
        self.DealsView.setObjectName(u"DealsView")
        self.DealsView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.DealsView.verticalHeader().setVisible(False)
        self.DealsView.verticalHeader().setMinimumSectionSize(20)
        self.DealsView.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.DealsView)


        self.retranslateUi(TaxEstimationDialog)

        QMetaObject.connectSlotsByName(TaxEstimationDialog)
    # setupUi

    def retranslateUi(self, TaxEstimationDialog):
        TaxEstimationDialog.setWindowTitle(QCoreApplication.translate("TaxEstimationDialog", u"Tax Estimation", None))
        self.LastQuoteLbl.setText(QCoreApplication.translate("TaxEstimationDialog", u"Last quote:", None))
        self.QuoteLbl.setText(QCoreApplication.translate("TaxEstimationDialog", u"X.XX", None))
        self.CurrentRateLbl.setText(QCoreApplication.translate("TaxEstimationDialog", u"Current rate:", None))
        self.RateLbl.setText(QCoreApplication.translate("TaxEstimationDialog", u"X.XX", None))
    # retranslateUi

