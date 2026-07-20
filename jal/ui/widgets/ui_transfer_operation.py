# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'transfer_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDateTimeEdit, QFrame,
    QGridLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpacerItem, QStackedWidget, QWidget)

from jal.widgets.account_select import AccountCurrencyLabel
from jal.widgets.reference_selector import ReferenceSelectorWidget

class Ui_TransferOperation(object):
    def setupUi(self, TransferOperation):
        if not TransferOperation.objectName():
            TransferOperation.setObjectName(u"TransferOperation")
        TransferOperation.resize(1272, 369)
        self.layout = QGridLayout(TransferOperation)
        self.layout.setSpacing(2)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 7, 2, 1, 1)

        self.to_account_label = QLabel(TransferOperation)
        self.to_account_label.setObjectName(u"to_account_label")
        self.to_account_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.to_account_label, 4, 0, 1, 1)

        self.to_account_widget = ReferenceSelectorWidget(TransferOperation)
        self.to_account_widget.setObjectName(u"to_account_widget")

        self.layout.addWidget(self.to_account_widget, 4, 4, 1, 1)

        self.TransferTypeCombo = QComboBox(TransferOperation)
        self.TransferTypeCombo.addItem("")
        self.TransferTypeCombo.addItem("")
        self.TransferTypeCombo.setObjectName(u"TransferTypeCombo")

        self.layout.addWidget(self.TransferTypeCombo, 1, 2, 1, 2)

        self.account_label = QLabel(TransferOperation)
        self.account_label.setObjectName(u"account_label")

        self.layout.addWidget(self.account_label, 2, 4, 1, 1)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 2, 9, 1, 1)

        self.commit_button = QPushButton(TransferOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 10, 1, 1)

        self.TransferTypeLabel = QLabel(TransferOperation)
        self.TransferTypeLabel.setObjectName(u"TransferTypeLabel")
        self.TransferTypeLabel.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.TransferTypeLabel, 1, 0, 1, 1)

        self.date_label = QLabel(TransferOperation)
        self.date_label.setObjectName(u"date_label")

        self.layout.addWidget(self.date_label, 2, 2, 1, 1)

        self.FeeGasPages = QStackedWidget(TransferOperation)
        self.FeeGasPages.setObjectName(u"FeeGasPages")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.FeeGasPages.sizePolicy().hasHeightForWidth())
        self.FeeGasPages.setSizePolicy(sizePolicy)
        self.FeeGasPages.setFrameShape(QFrame.Shape.NoFrame)
        self.NoFeePage = QWidget()
        self.NoFeePage.setObjectName(u"NoFeePage")
        self.FeeGasPages.addWidget(self.NoFeePage)
        self.FeePage = QWidget()
        self.FeePage.setObjectName(u"FeePage")
        self.gridLayout = QGridLayout(self.FeePage)
        self.gridLayout.setSpacing(2)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.fee_currency = AccountCurrencyLabel(self.FeePage)
        self.fee_currency.setObjectName(u"fee_currency")

        self.gridLayout.addWidget(self.fee_currency, 0, 2, 1, 1)

        self.fee = QLineEdit(self.FeePage)
        self.fee.setObjectName(u"fee")
        self.fee.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout.addWidget(self.fee, 0, 1, 1, 1)

        self.fee_account_widget = ReferenceSelectorWidget(self.FeePage)
        self.fee_account_widget.setObjectName(u"fee_account_widget")

        self.gridLayout.addWidget(self.fee_account_widget, 0, 0, 1, 1)

        self.FeeGasPages.addWidget(self.FeePage)
        self.GasPage = QWidget()
        self.GasPage.setObjectName(u"GasPage")
        self.gridLayout_2 = QGridLayout(self.GasPage)
        self.gridLayout_2.setSpacing(2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.gas = QLineEdit(self.GasPage)
        self.gas.setObjectName(u"gas")
        self.gas.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_2.addWidget(self.gas, 0, 0, 1, 1)

        self.gas_symbol_widget = ReferenceSelectorWidget(self.GasPage)
        self.gas_symbol_widget.setObjectName(u"gas_symbol_widget")

        self.gridLayout_2.addWidget(self.gas_symbol_widget, 0, 1, 1, 1)

        self.FeeGasPages.addWidget(self.GasPage)

        self.layout.addWidget(self.FeeGasPages, 5, 4, 1, 5)

        self.number_label = QLabel(TransferOperation)
        self.number_label.setObjectName(u"number_label")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.number_label, 1, 4, 1, 1)

        self.note_label = QLabel(TransferOperation)
        self.note_label.setObjectName(u"note_label")
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.note_label, 6, 0, 1, 1)

        self.MoneyAssetPages = QStackedWidget(TransferOperation)
        self.MoneyAssetPages.setObjectName(u"MoneyAssetPages")
        sizePolicy.setHeightForWidth(self.MoneyAssetPages.sizePolicy().hasHeightForWidth())
        self.MoneyAssetPages.setSizePolicy(sizePolicy)
        self.MoneyAssetPages.setLineWidth(1)
        self.MoneyTransferPage = QWidget()
        self.MoneyTransferPage.setObjectName(u"MoneyTransferPage")
        self.gridLayout_3 = QGridLayout(self.MoneyTransferPage)
        self.gridLayout_3.setSpacing(2)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.from_currency = AccountCurrencyLabel(self.MoneyTransferPage)
        self.from_currency.setObjectName(u"from_currency")

        self.gridLayout_3.addWidget(self.from_currency, 2, 2, 1, 1)

        self.to_currency = AccountCurrencyLabel(self.MoneyTransferPage)
        self.to_currency.setObjectName(u"to_currency")

        self.gridLayout_3.addWidget(self.to_currency, 3, 2, 1, 1)

        self.amount_label = QLabel(self.MoneyTransferPage)
        self.amount_label.setObjectName(u"amount_label")

        self.gridLayout_3.addWidget(self.amount_label, 0, 0, 1, 1)

        self.copy_amount_btn = QPushButton(self.MoneyTransferPage)
        self.copy_amount_btn.setObjectName(u"copy_amount_btn")

        self.gridLayout_3.addWidget(self.copy_amount_btn, 0, 1, 1, 1)

        self.withdrawal = QLineEdit(self.MoneyTransferPage)
        self.withdrawal.setObjectName(u"withdrawal")
        self.withdrawal.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_3.addWidget(self.withdrawal, 2, 0, 1, 2)

        self.deposit = QLineEdit(self.MoneyTransferPage)
        self.deposit.setObjectName(u"deposit")
        self.deposit.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_3.addWidget(self.deposit, 3, 0, 1, 2)

        self.MoneyAssetPages.addWidget(self.MoneyTransferPage)
        self.AssetTransferPage = QWidget()
        self.AssetTransferPage.setObjectName(u"AssetTransferPage")
        self.gridLayout_4 = QGridLayout(self.AssetTransferPage)
        self.gridLayout_4.setSpacing(2)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.gridLayout_4.setContentsMargins(0, 0, 0, 0)
        self.asset_cost_basis = QLineEdit(self.AssetTransferPage)
        self.asset_cost_basis.setObjectName(u"asset_cost_basis")

        self.gridLayout_4.addWidget(self.asset_cost_basis, 2, 1, 1, 1)

        self.value_label = QLabel(self.AssetTransferPage)
        self.value_label.setObjectName(u"value_label")

        self.gridLayout_4.addWidget(self.value_label, 2, 0, 1, 1)

        self.asset_amount = QLineEdit(self.AssetTransferPage)
        self.asset_amount.setObjectName(u"asset_amount")

        self.gridLayout_4.addWidget(self.asset_amount, 1, 1, 1, 1)

        self.AssetLabel = QLabel(self.AssetTransferPage)
        self.AssetLabel.setObjectName(u"AssetLabel")

        self.gridLayout_4.addWidget(self.AssetLabel, 1, 0, 1, 1)

        self.CostBasisCurrencyLabel = AccountCurrencyLabel(self.AssetTransferPage)
        self.CostBasisCurrencyLabel.setObjectName(u"CostBasisCurrencyLabel")

        self.gridLayout_4.addWidget(self.CostBasisCurrencyLabel, 2, 2, 1, 1)

        self.symbol_widget = ReferenceSelectorWidget(self.AssetTransferPage)
        self.symbol_widget.setObjectName(u"symbol_widget")

        self.gridLayout_4.addWidget(self.symbol_widget, 1, 2, 1, 1)

        self.AmountLabel = QLabel(self.AssetTransferPage)
        self.AmountLabel.setObjectName(u"AmountLabel")

        self.gridLayout_4.addWidget(self.AmountLabel, 0, 1, 1, 1)

        self.MoneyAssetPages.addWidget(self.AssetTransferPage)

        self.layout.addWidget(self.MoneyAssetPages, 2, 5, 3, 4)

        self.number = QLineEdit(TransferOperation)
        self.number.setObjectName(u"number")

        self.layout.addWidget(self.number, 1, 5, 1, 4)

        self.withdrawal_timestamp = QDateTimeEdit(TransferOperation)
        self.withdrawal_timestamp.setObjectName(u"withdrawal_timestamp")
        self.withdrawal_timestamp.setCalendarPopup(True)
        self.withdrawal_timestamp.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.withdrawal_timestamp, 3, 2, 1, 2)

        self.FeeGasCombo = QComboBox(TransferOperation)
        self.FeeGasCombo.addItem("")
        self.FeeGasCombo.addItem("")
        self.FeeGasCombo.addItem("")
        self.FeeGasCombo.setObjectName(u"FeeGasCombo")

        self.layout.addWidget(self.FeeGasCombo, 5, 2, 1, 2)

        self.revert_button = QPushButton(TransferOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 11, 1, 1)

        self.deposit_timestamp = QDateTimeEdit(TransferOperation)
        self.deposit_timestamp.setObjectName(u"deposit_timestamp")
        self.deposit_timestamp.setCalendarPopup(True)
        self.deposit_timestamp.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.deposit_timestamp, 4, 2, 1, 2)

        self.copy_date_btn = QPushButton(TransferOperation)
        self.copy_date_btn.setObjectName(u"copy_date_btn")

        self.layout.addWidget(self.copy_date_btn, 2, 3, 1, 1)

        self.main_label = QLabel(TransferOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.from_account_widget = ReferenceSelectorWidget(TransferOperation)
        self.from_account_widget.setObjectName(u"from_account_widget")

        self.layout.addWidget(self.from_account_widget, 3, 4, 1, 1)

        self.from_account_label = QLabel(TransferOperation)
        self.from_account_label.setObjectName(u"from_account_label")
        self.from_account_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.from_account_label, 3, 0, 1, 1)

        self.note = QLineEdit(TransferOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 6, 2, 1, 7)


        self.retranslateUi(TransferOperation)

        self.FeeGasPages.setCurrentIndex(0)
        self.MoneyAssetPages.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(TransferOperation)
    # setupUi

    def retranslateUi(self, TransferOperation):
        TransferOperation.setWindowTitle(QCoreApplication.translate("TransferOperation", u"Form", None))
        self.to_account_label.setText(QCoreApplication.translate("TransferOperation", u"To", None))
        self.TransferTypeCombo.setItemText(0, QCoreApplication.translate("TransferOperation", u"Money transfer", None))
        self.TransferTypeCombo.setItemText(1, QCoreApplication.translate("TransferOperation", u"Asset transfer", None))

        self.account_label.setText(QCoreApplication.translate("TransferOperation", u"Account", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("TransferOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
        self.TransferTypeLabel.setText(QCoreApplication.translate("TransferOperation", u"Type", None))
        self.date_label.setText(QCoreApplication.translate("TransferOperation", u"Date/Time", None))
        self.fee_currency.setText(QCoreApplication.translate("TransferOperation", u"CUR", None))
        self.number_label.setText(QCoreApplication.translate("TransferOperation", u"#", None))
        self.note_label.setText(QCoreApplication.translate("TransferOperation", u"Note", None))
        self.from_currency.setText(QCoreApplication.translate("TransferOperation", u"CUR", None))
        self.to_currency.setText(QCoreApplication.translate("TransferOperation", u"CUR", None))
        self.amount_label.setText(QCoreApplication.translate("TransferOperation", u"Amount", None))
#if QT_CONFIG(tooltip)
        self.copy_amount_btn.setToolTip(QCoreApplication.translate("TransferOperation", u"Copy value", None))
#endif // QT_CONFIG(tooltip)
        self.copy_amount_btn.setText(QCoreApplication.translate("TransferOperation", u"\u2193", None))
        self.value_label.setText(QCoreApplication.translate("TransferOperation", u"Cost basis", None))
        self.AssetLabel.setText(QCoreApplication.translate("TransferOperation", u"Asset", None))
        self.CostBasisCurrencyLabel.setText(QCoreApplication.translate("TransferOperation", u"CUR", None))
        self.AmountLabel.setText(QCoreApplication.translate("TransferOperation", u"Amount", None))
        self.withdrawal_timestamp.setDisplayFormat(QCoreApplication.translate("TransferOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.FeeGasCombo.setItemText(0, QCoreApplication.translate("TransferOperation", u"No fee", None))
        self.FeeGasCombo.setItemText(1, QCoreApplication.translate("TransferOperation", u"Fee", None))
        self.FeeGasCombo.setItemText(2, QCoreApplication.translate("TransferOperation", u"Gas", None))

#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("TransferOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.deposit_timestamp.setDisplayFormat(QCoreApplication.translate("TransferOperation", u"dd/MM/yyyy hh:mm:ss", None))
#if QT_CONFIG(tooltip)
        self.copy_date_btn.setToolTip(QCoreApplication.translate("TransferOperation", u"Copy value", None))
#endif // QT_CONFIG(tooltip)
        self.copy_date_btn.setText(QCoreApplication.translate("TransferOperation", u"\u2193", None))
        self.main_label.setText(QCoreApplication.translate("TransferOperation", u"Transfer", None))
        self.from_account_label.setText(QCoreApplication.translate("TransferOperation", u"From", None))
    # retranslateUi

