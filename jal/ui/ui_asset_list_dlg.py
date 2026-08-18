# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'asset_list_dlg.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
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
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QComboBox,
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QTableView, QVBoxLayout, QWidget)

class Ui_AssetsListDialog(object):
    def setupUi(self, AssetsListDialog):
        if not AssetsListDialog.objectName():
            AssetsListDialog.setObjectName(u"AssetsListDialog")
        AssetsListDialog.resize(869, 300)
        self.verticalLayout = QVBoxLayout(AssetsListDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.DisplayFrame = QWidget(AssetsListDialog)
        self.DisplayFrame.setObjectName(u"DisplayFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.DisplayFrame.sizePolicy().hasHeightForWidth())
        self.DisplayFrame.setSizePolicy(sizePolicy)
        self.edit_layout = QHBoxLayout(self.DisplayFrame)
        self.edit_layout.setObjectName(u"edit_layout")
        self.edit_layout.setContentsMargins(0, 0, 0, 0)
        self.AssetTypeLbl = QLabel(self.DisplayFrame)
        self.AssetTypeLbl.setObjectName(u"AssetTypeLbl")

        self.edit_layout.addWidget(self.AssetTypeLbl)

        self.AssetTypeCombo = QComboBox(self.DisplayFrame)
        self.AssetTypeCombo.setObjectName(u"AssetTypeCombo")

        self.edit_layout.addWidget(self.AssetTypeCombo)

        self.currencyGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.edit_layout.addItem(self.currencyGroupSpacer)

        self.CurrencyLbl = QLabel(self.DisplayFrame)
        self.CurrencyLbl.setObjectName(u"CurrencyLbl")

        self.edit_layout.addWidget(self.CurrencyLbl)

        self.CurrencyCombo = QComboBox(self.DisplayFrame)
        self.CurrencyCombo.setObjectName(u"CurrencyCombo")

        self.edit_layout.addWidget(self.CurrencyCombo)

        self.locationGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.edit_layout.addItem(self.locationGroupSpacer)

        self.LocationLbl = QLabel(self.DisplayFrame)
        self.LocationLbl.setObjectName(u"LocationLbl")

        self.edit_layout.addWidget(self.LocationLbl)

        self.LocationCombo = QComboBox(self.DisplayFrame)
        self.LocationCombo.setObjectName(u"LocationCombo")

        self.edit_layout.addWidget(self.LocationCombo)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.edit_layout.addItem(self.horizontalSpacer)

        self.AddBtn = QPushButton(self.DisplayFrame)
        self.AddBtn.setObjectName(u"AddBtn")

        self.edit_layout.addWidget(self.AddBtn)

        self.EditBtn = QPushButton(self.DisplayFrame)
        self.EditBtn.setObjectName(u"EditBtn")

        self.edit_layout.addWidget(self.EditBtn)

        self.RemoveBtn = QPushButton(self.DisplayFrame)
        self.RemoveBtn.setObjectName(u"RemoveBtn")

        self.edit_layout.addWidget(self.RemoveBtn)


        self.verticalLayout.addWidget(self.DisplayFrame)

        self.SearchFrame = QWidget(AssetsListDialog)
        self.SearchFrame.setObjectName(u"SearchFrame")
        self.search_layout = QHBoxLayout(self.SearchFrame)
        self.search_layout.setObjectName(u"search_layout")
        self.search_layout.setContentsMargins(0, 0, 0, 0)
        self.SearchLbl = QLabel(self.SearchFrame)
        self.SearchLbl.setObjectName(u"SearchLbl")

        self.search_layout.addWidget(self.SearchLbl)

        self.SearchString = QLineEdit(self.SearchFrame)
        self.SearchString.setObjectName(u"SearchString")

        self.search_layout.addWidget(self.SearchString)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.search_layout.addItem(self.horizontalSpacer_2)


        self.verticalLayout.addWidget(self.SearchFrame)

        self.DataView = QTableView(AssetsListDialog)
        self.DataView.setObjectName(u"DataView")
        self.DataView.setEditTriggers(QAbstractItemView.EditTrigger.AnyKeyPressed|QAbstractItemView.EditTrigger.EditKeyPressed|QAbstractItemView.EditTrigger.SelectedClicked)
        self.DataView.setAlternatingRowColors(True)
        self.DataView.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.DataView.verticalHeader().setVisible(True)
        self.DataView.verticalHeader().setMinimumSectionSize(20)

        self.verticalLayout.addWidget(self.DataView)

        self.DialogButtonBox = QDialogButtonBox(AssetsListDialog)
        self.DialogButtonBox.setObjectName(u"DialogButtonBox")
        self.DialogButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.DialogButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.verticalLayout.addWidget(self.DialogButtonBox)

#if QT_CONFIG(shortcut)
        self.AssetTypeLbl.setBuddy(self.AssetTypeCombo)
        self.CurrencyLbl.setBuddy(self.CurrencyCombo)
        self.LocationLbl.setBuddy(self.LocationCombo)
        self.SearchLbl.setBuddy(self.SearchString)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.AssetTypeCombo, self.CurrencyCombo)
        QWidget.setTabOrder(self.CurrencyCombo, self.LocationCombo)
        QWidget.setTabOrder(self.LocationCombo, self.AddBtn)
        QWidget.setTabOrder(self.AddBtn, self.EditBtn)
        QWidget.setTabOrder(self.EditBtn, self.RemoveBtn)
        QWidget.setTabOrder(self.RemoveBtn, self.SearchString)
        QWidget.setTabOrder(self.SearchString, self.DataView)
        QWidget.setTabOrder(self.DataView, self.DialogButtonBox)

        self.retranslateUi(AssetsListDialog)

        QMetaObject.connectSlotsByName(AssetsListDialog)
    # setupUi

    def retranslateUi(self, AssetsListDialog):
        AssetsListDialog.setWindowTitle(QCoreApplication.translate("AssetsListDialog", u"Assets", None))
        self.AssetTypeLbl.setText(QCoreApplication.translate("AssetsListDialog", u"Type:", None))
        self.CurrencyLbl.setText(QCoreApplication.translate("AssetsListDialog", u"Currency:", None))
        self.LocationLbl.setText(QCoreApplication.translate("AssetsListDialog", u"Location:", None))
#if QT_CONFIG(tooltip)
        self.AddBtn.setToolTip(QCoreApplication.translate("AssetsListDialog", u"Add new", None))
#endif // QT_CONFIG(tooltip)
        self.AddBtn.setText("")
#if QT_CONFIG(tooltip)
        self.EditBtn.setToolTip(QCoreApplication.translate("AssetsListDialog", u"Edit", None))
#endif // QT_CONFIG(tooltip)
        self.EditBtn.setText("")
#if QT_CONFIG(tooltip)
        self.RemoveBtn.setToolTip(QCoreApplication.translate("AssetsListDialog", u"Delete", None))
#endif // QT_CONFIG(tooltip)
        self.RemoveBtn.setText("")
        self.SearchLbl.setText(QCoreApplication.translate("AssetsListDialog", u"Search:", None))
    # retranslateUi

