# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'position_details_window.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFormLayout,
    QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QSizePolicy, QSpacerItem, QSplitter,
    QVBoxLayout, QWidget)

from jal.widgets.custom.tableview_with_footer import TableViewWithFooter

class Ui_PositionDetailsWindow(object):
    def setupUi(self, PositionDetailsWindow):
        if not PositionDetailsWindow.objectName():
            PositionDetailsWindow.setObjectName(u"PositionDetailsWindow")
        PositionDetailsWindow.resize(1100, 560)
        self.WindowLayout = QVBoxLayout(PositionDetailsWindow)
        self.WindowLayout.setObjectName(u"WindowLayout")
        self.QuoteLbl = QLabel(PositionDetailsWindow)
        self.QuoteLbl.setObjectName(u"QuoteLbl")
        self.QuoteLbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.WindowLayout.addWidget(self.QuoteLbl)

        self.PositionDetailsSplitter = QSplitter(PositionDetailsWindow)
        self.PositionDetailsSplitter.setObjectName(u"PositionDetailsSplitter")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.PositionDetailsSplitter.sizePolicy().hasHeightForWidth())
        self.PositionDetailsSplitter.setSizePolicy(sizePolicy)
        self.PositionDetailsSplitter.setOrientation(Qt.Orientation.Horizontal)
        self.PositionDetailsSplitter.setChildrenCollapsible(False)
        self.LotsView = TableViewWithFooter(self.PositionDetailsSplitter)
        self.LotsView.setObjectName(u"LotsView")
        self.LotsView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.LotsView.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.LotsView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.PositionDetailsSplitter.addWidget(self.LotsView)
        self.LotsView.verticalHeader().setVisible(False)
        self.LotsView.verticalHeader().setMinimumSectionSize(20)
        self.ChartFrame = QFrame(self.PositionDetailsSplitter)
        self.ChartFrame.setObjectName(u"ChartFrame")
        self.ChartFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.ChartLayout = QHBoxLayout(self.ChartFrame)
        self.ChartLayout.setObjectName(u"ChartLayout")
        self.ChartLayout.setContentsMargins(0, 0, 0, 0)
        self.PositionDetailsSplitter.addWidget(self.ChartFrame)

        self.WindowLayout.addWidget(self.PositionDetailsSplitter)

        self.TaxGroup = QGroupBox(PositionDetailsWindow)
        self.TaxGroup.setObjectName(u"TaxGroup")
        self.TaxLayout = QFormLayout(self.TaxGroup)
        self.TaxLayout.setObjectName(u"TaxLayout")
        self.CountryLbl = QLabel(self.TaxGroup)
        self.CountryLbl.setObjectName(u"CountryLbl")

        self.TaxLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.CountryLbl)

        self.CountryLayout = QHBoxLayout()
        self.CountryLayout.setObjectName(u"CountryLayout")
        self.CountryCombo = QComboBox(self.TaxGroup)
        self.CountryCombo.setObjectName(u"CountryCombo")

        self.CountryLayout.addWidget(self.CountryCombo)

        self.CountrySpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.CountryLayout.addItem(self.CountrySpacer)


        self.TaxLayout.setLayout(0, QFormLayout.ItemRole.FieldRole, self.CountryLayout)

        self.GainLbl = QLabel(self.TaxGroup)
        self.GainLbl.setObjectName(u"GainLbl")

        self.TaxLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.GainLbl)

        self.GainValue = QLabel(self.TaxGroup)
        self.GainValue.setObjectName(u"GainValue")
        self.GainValue.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.TaxLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.GainValue)

        self.RateLbl = QLabel(self.TaxGroup)
        self.RateLbl.setObjectName(u"RateLbl")

        self.TaxLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.RateLbl)

        self.RateValue = QLabel(self.TaxGroup)
        self.RateValue.setObjectName(u"RateValue")
        self.RateValue.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.TaxLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.RateValue)

        self.BaseRateLbl = QLabel(self.TaxGroup)
        self.BaseRateLbl.setObjectName(u"BaseRateLbl")

        self.TaxLayout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.BaseRateLbl)

        self.BaseRateValue = QLabel(self.TaxGroup)
        self.BaseRateValue.setObjectName(u"BaseRateValue")

        self.TaxLayout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.BaseRateValue)

        self.TaxLbl = QLabel(self.TaxGroup)
        self.TaxLbl.setObjectName(u"TaxLbl")

        self.TaxLayout.setWidget(4, QFormLayout.ItemRole.LabelRole, self.TaxLbl)

        self.TaxValue = QLabel(self.TaxGroup)
        self.TaxValue.setObjectName(u"TaxValue")
        self.TaxValue.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.TaxLayout.setWidget(4, QFormLayout.ItemRole.FieldRole, self.TaxValue)

        self.NoteLbl = QLabel(self.TaxGroup)
        self.NoteLbl.setObjectName(u"NoteLbl")
        self.NoteLbl.setWordWrap(True)

        self.TaxLayout.setWidget(5, QFormLayout.ItemRole.SpanningRole, self.NoteLbl)


        self.WindowLayout.addWidget(self.TaxGroup)

        QWidget.setTabOrder(self.LotsView, self.CountryCombo)

        self.retranslateUi(PositionDetailsWindow)

        QMetaObject.connectSlotsByName(PositionDetailsWindow)
    # setupUi

    def retranslateUi(self, PositionDetailsWindow):
        PositionDetailsWindow.setWindowTitle(QCoreApplication.translate("PositionDetailsWindow", u"Position details", None))
        self.TaxGroup.setTitle(QCoreApplication.translate("PositionDetailsWindow", u"Tax estimate", None))
        self.CountryLbl.setText(QCoreApplication.translate("PositionDetailsWindow", u"Tax residence:", None))
        self.GainLbl.setText(QCoreApplication.translate("PositionDetailsWindow", u"P/L:", None))
        self.RateLbl.setText(QCoreApplication.translate("PositionDetailsWindow", u"Rate:", None))
        self.BaseRateLbl.setText(QCoreApplication.translate("PositionDetailsWindow", u"Base rate:", None))
        self.TaxLbl.setText(QCoreApplication.translate("PositionDetailsWindow", u"Tax:", None))
    # retranslateUi

