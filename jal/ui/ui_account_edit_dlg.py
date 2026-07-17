# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'account_edit_dlg.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QTableView, QWidget)

from jal.constants import AccountTypeComboBox
from jal.widgets.custom.db_lookup_combobox import DbLookupComboBox

class Ui_AccountDialog(object):
    def setupUi(self, AccountDialog):
        if not AccountDialog.objectName():
            AccountDialog.setObjectName(u"AccountDialog")
        AccountDialog.resize(560, 440)
        self.gridLayout = QGridLayout(AccountDialog)
        self.gridLayout.setSpacing(2)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.MainFrame = QFrame(AccountDialog)
        self.MainFrame.setObjectName(u"MainFrame")
        self.MainFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.MainFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_2 = QGridLayout(self.MainFrame)
        self.gridLayout_2.setSpacing(2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.NameLbl = QLabel(self.MainFrame)
        self.NameLbl.setObjectName(u"NameLbl")

        self.gridLayout_2.addWidget(self.NameLbl, 0, 0, 1, 1)

        self.InvestingCheck = QCheckBox(self.MainFrame)
        self.InvestingCheck.setObjectName(u"InvestingCheck")

        self.gridLayout_2.addWidget(self.InvestingCheck, 4, 2, 1, 1)

        self.CurrencyLbl = QLabel(self.MainFrame)
        self.CurrencyLbl.setObjectName(u"CurrencyLbl")

        self.gridLayout_2.addWidget(self.CurrencyLbl, 1, 0, 1, 1)

        self.TypeLbl = QLabel(self.MainFrame)
        self.TypeLbl.setObjectName(u"TypeLbl")

        self.gridLayout_2.addWidget(self.TypeLbl, 2, 0, 1, 1)

        self.ActiveCheck = QCheckBox(self.MainFrame)
        self.ActiveCheck.setObjectName(u"ActiveCheck")

        self.gridLayout_2.addWidget(self.ActiveCheck, 4, 0, 1, 1)

        self.OrganizationLbl = QLabel(self.MainFrame)
        self.OrganizationLbl.setObjectName(u"OrganizationLbl")

        self.gridLayout_2.addWidget(self.OrganizationLbl, 3, 0, 1, 1)

        self.ReconciledValue = QLabel(self.MainFrame)
        self.ReconciledValue.setObjectName(u"ReconciledValue")
        self.ReconciledValue.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard|Qt.TextInteractionFlag.TextSelectableByMouse)

        self.gridLayout_2.addWidget(self.ReconciledValue, 4, 5, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_2.addItem(self.horizontalSpacer, 4, 3, 1, 1)

        self.OrganizationCombo = DbLookupComboBox(self.MainFrame)
        self.OrganizationCombo.setObjectName(u"OrganizationCombo")

        self.gridLayout_2.addWidget(self.OrganizationCombo, 3, 2, 1, 4)

        self.TypeCombo = AccountTypeComboBox(self.MainFrame)
        self.TypeCombo.setObjectName(u"TypeCombo")

        self.gridLayout_2.addWidget(self.TypeCombo, 2, 2, 1, 4)

        self.NameEdit = QLineEdit(self.MainFrame)
        self.NameEdit.setObjectName(u"NameEdit")

        self.gridLayout_2.addWidget(self.NameEdit, 0, 2, 1, 4)

        self.CurrencyCombo = DbLookupComboBox(self.MainFrame)
        self.CurrencyCombo.setObjectName(u"CurrencyCombo")

        self.gridLayout_2.addWidget(self.CurrencyCombo, 1, 2, 1, 4)


        self.gridLayout.addWidget(self.MainFrame, 0, 0, 1, 1)

        self.ButtonsFrame = QFrame(AccountDialog)
        self.ButtonsFrame.setObjectName(u"ButtonsFrame")
        self.ButtonsFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.ButtonsFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout = QHBoxLayout(self.ButtonsFrame)
        self.horizontalLayout.setSpacing(2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.buttonsSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.buttonsSpacer)

        self.OkButton = QPushButton(self.ButtonsFrame)
        self.OkButton.setObjectName(u"OkButton")

        self.horizontalLayout.addWidget(self.OkButton)

        self.CancelButton = QPushButton(self.ButtonsFrame)
        self.CancelButton.setObjectName(u"CancelButton")

        self.horizontalLayout.addWidget(self.CancelButton)


        self.gridLayout.addWidget(self.ButtonsFrame, 2, 0, 1, 1)

        self.DetailsFrame = QFrame(AccountDialog)
        self.DetailsFrame.setObjectName(u"DetailsFrame")
        self.DetailsFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.DetailsFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_3 = QGridLayout(self.DetailsFrame)
        self.gridLayout_3.setSpacing(2)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.dataHeaderSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_3.addItem(self.dataHeaderSpacer, 0, 1, 1, 1)

        self.DataLbl = QLabel(self.DetailsFrame)
        self.DataLbl.setObjectName(u"DataLbl")

        self.gridLayout_3.addWidget(self.DataLbl, 0, 0, 1, 1)

        self.AddDataButton = QPushButton(self.DetailsFrame)
        self.AddDataButton.setObjectName(u"AddDataButton")

        self.gridLayout_3.addWidget(self.AddDataButton, 0, 2, 1, 1)

        self.RemoveDataButton = QPushButton(self.DetailsFrame)
        self.RemoveDataButton.setObjectName(u"RemoveDataButton")

        self.gridLayout_3.addWidget(self.RemoveDataButton, 0, 3, 1, 1)

        self.DataTable = QTableView(self.DetailsFrame)
        self.DataTable.setObjectName(u"DataTable")
        self.DataTable.setFrameShadow(QFrame.Shadow.Plain)
        self.DataTable.verticalHeader().setVisible(False)
        self.DataTable.verticalHeader().setMinimumSectionSize(20)
        self.DataTable.verticalHeader().setDefaultSectionSize(20)

        self.gridLayout_3.addWidget(self.DataTable, 2, 0, 1, 4)


        self.gridLayout.addWidget(self.DetailsFrame, 1, 0, 1, 1)


        self.retranslateUi(AccountDialog)
        self.OkButton.clicked.connect(AccountDialog.accept)
        self.CancelButton.clicked.connect(AccountDialog.reject)

        QMetaObject.connectSlotsByName(AccountDialog)
    # setupUi

    def retranslateUi(self, AccountDialog):
        AccountDialog.setWindowTitle(QCoreApplication.translate("AccountDialog", u"Account", None))
        self.NameLbl.setText(QCoreApplication.translate("AccountDialog", u"Name:", None))
        self.InvestingCheck.setText(QCoreApplication.translate("AccountDialog", u"Investing", None))
        self.CurrencyLbl.setText(QCoreApplication.translate("AccountDialog", u"Currency:", None))
        self.TypeLbl.setText(QCoreApplication.translate("AccountDialog", u"Type:", None))
        self.ActiveCheck.setText(QCoreApplication.translate("AccountDialog", u"Active", None))
        self.OrganizationLbl.setText(QCoreApplication.translate("AccountDialog", u"Bank/Broker:", None))
#if QT_CONFIG(tooltip)
        self.ReconciledValue.setToolTip(QCoreApplication.translate("AccountDialog", u"Set automatically when this account is reconciled by an operation", None))
#endif // QT_CONFIG(tooltip)
        self.ReconciledValue.setText("")
        self.OkButton.setText(QCoreApplication.translate("AccountDialog", u"OK", None))
        self.CancelButton.setText(QCoreApplication.translate("AccountDialog", u"Cancel", None))
        self.DataLbl.setText(QCoreApplication.translate("AccountDialog", u"Account details:", None))
#if QT_CONFIG(tooltip)
        self.AddDataButton.setToolTip(QCoreApplication.translate("AccountDialog", u"Add new", None))
#endif // QT_CONFIG(tooltip)
        self.AddDataButton.setText("")
#if QT_CONFIG(tooltip)
        self.RemoveDataButton.setToolTip(QCoreApplication.translate("AccountDialog", u"Delete", None))
#endif // QT_CONFIG(tooltip)
        self.RemoveDataButton.setText("")
    # retranslateUi

