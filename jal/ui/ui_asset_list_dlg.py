# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'asset_list_dlg.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog,
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QTableView, QVBoxLayout, QWidget)

class Ui_AssetsListDialog(object):
    def setupUi(self, AssetsListDialog):
        if not AssetsListDialog.objectName():
            AssetsListDialog.setObjectName(u"AssetsListDialog")
        AssetsListDialog.resize(869, 300)
        self.verticalLayout = QVBoxLayout(AssetsListDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.DisplayFrame = QFrame(AssetsListDialog)
        self.DisplayFrame.setObjectName(u"DisplayFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.DisplayFrame.sizePolicy().hasHeightForWidth())
        self.DisplayFrame.setSizePolicy(sizePolicy)
        self.DisplayFrame.setFrameShape(QFrame.Shape.Panel)
        self.DisplayFrame.setFrameShadow(QFrame.Shadow.Plain)
        self.DisplayFrame.setLineWidth(0)
        self.edit_layout = QHBoxLayout(self.DisplayFrame)
        self.edit_layout.setObjectName(u"edit_layout")
        self.edit_layout.setContentsMargins(0, 0, 0, 0)
        self.AssetTypeLbl = QLabel(self.DisplayFrame)
        self.AssetTypeLbl.setObjectName(u"AssetTypeLbl")

        self.edit_layout.addWidget(self.AssetTypeLbl)

        self.AssetTypeCombo = QComboBox(self.DisplayFrame)
        self.AssetTypeCombo.setObjectName(u"AssetTypeCombo")

        self.edit_layout.addWidget(self.AssetTypeCombo)

        self.CurrencyLbl = QLabel(self.DisplayFrame)
        self.CurrencyLbl.setObjectName(u"CurrencyLbl")

        self.edit_layout.addWidget(self.CurrencyLbl)

        self.CurrencyCombo = QComboBox(self.DisplayFrame)
        self.CurrencyCombo.setObjectName(u"CurrencyCombo")

        self.edit_layout.addWidget(self.CurrencyCombo)

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

        self.AddChildBtn = QPushButton(self.DisplayFrame)
        self.AddChildBtn.setObjectName(u"AddChildBtn")

        self.edit_layout.addWidget(self.AddChildBtn)

        self.RemoveBtn = QPushButton(self.DisplayFrame)
        self.RemoveBtn.setObjectName(u"RemoveBtn")

        self.edit_layout.addWidget(self.RemoveBtn)

        self.CommitBtn = QPushButton(self.DisplayFrame)
        self.CommitBtn.setObjectName(u"CommitBtn")
        self.CommitBtn.setEnabled(False)

        self.edit_layout.addWidget(self.CommitBtn)

        self.RevertBtn = QPushButton(self.DisplayFrame)
        self.RevertBtn.setObjectName(u"RevertBtn")
        self.RevertBtn.setEnabled(False)

        self.edit_layout.addWidget(self.RevertBtn)


        self.verticalLayout.addWidget(self.DisplayFrame)

        self.SearchFrame = QFrame(AssetsListDialog)
        self.SearchFrame.setObjectName(u"SearchFrame")
        self.SearchFrame.setFrameShape(QFrame.Shape.Panel)
        self.SearchFrame.setFrameShadow(QFrame.Shadow.Plain)
        self.SearchFrame.setLineWidth(0)
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
        self.DataView.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.DataView)


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
        self.AddChildBtn.setToolTip(QCoreApplication.translate("AssetsListDialog", u"Add child", None))
#endif // QT_CONFIG(tooltip)
        self.AddChildBtn.setText("")
#if QT_CONFIG(tooltip)
        self.RemoveBtn.setToolTip(QCoreApplication.translate("AssetsListDialog", u"Delete", None))
#endif // QT_CONFIG(tooltip)
        self.RemoveBtn.setText("")
#if QT_CONFIG(tooltip)
        self.CommitBtn.setToolTip(QCoreApplication.translate("AssetsListDialog", u"Save changes", None))
#endif // QT_CONFIG(tooltip)
        self.CommitBtn.setText("")
#if QT_CONFIG(tooltip)
        self.RevertBtn.setToolTip(QCoreApplication.translate("AssetsListDialog", u"Revert changes", None))
#endif // QT_CONFIG(tooltip)
        self.RevertBtn.setText("")
        self.SearchLbl.setText(QCoreApplication.translate("AssetsListDialog", u"Search:", None))
    # retranslateUi

