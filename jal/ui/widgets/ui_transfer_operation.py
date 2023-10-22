# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'transfer_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDateTimeEdit, QGridLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QWidget)

from jal.widgets.account_select import AccountCurrencyLabel
from jal.widgets.reference_selector import (AccountSelector, AssetSelector)

class Ui_TransferOperation(object):
    def setupUi(self, TransferOperation):
        if not TransferOperation.objectName():
            TransferOperation.setObjectName(u"TransferOperation")
        TransferOperation.resize(968, 283)
        self.layout = QGridLayout(TransferOperation)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.to_currency = AccountCurrencyLabel(TransferOperation)
        self.to_currency.setObjectName(u"to_currency")

        self.layout.addWidget(self.to_currency, 3, 7, 1, 1)

        self.from_currency = AccountCurrencyLabel(TransferOperation)
        self.from_currency.setObjectName(u"from_currency")

        self.layout.addWidget(self.from_currency, 2, 7, 1, 1)

        self.from_account_label = QLabel(TransferOperation)
        self.from_account_label.setObjectName(u"from_account_label")
        self.from_account_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.from_account_label, 2, 0, 1, 1)

        self.to_account_widget = AccountSelector(TransferOperation)
        self.to_account_widget.setObjectName(u"to_account_widget")

        self.layout.addWidget(self.to_account_widget, 3, 4, 1, 1)

        self.note_label = QLabel(TransferOperation)
        self.note_label.setObjectName(u"note_label")
        self.note_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.note_label, 7, 0, 1, 1)

        self.copy_amount_btn = QPushButton(TransferOperation)
        self.copy_amount_btn.setObjectName(u"copy_amount_btn")

        self.layout.addWidget(self.copy_amount_btn, 1, 6, 1, 1)

        self.deposit_timestamp = QDateTimeEdit(TransferOperation)
        self.deposit_timestamp.setObjectName(u"deposit_timestamp")
        self.deposit_timestamp.setCalendarPopup(True)
        self.deposit_timestamp.setTimeSpec(Qt.UTC)

        self.layout.addWidget(self.deposit_timestamp, 3, 2, 1, 2)

        self.main_label = QLabel(TransferOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.number_label = QLabel(TransferOperation)
        self.number_label.setObjectName(u"number_label")
        self.number_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.number_label, 1, 7, 1, 1)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 1, 10, 1, 1)

        self.fee_account_widget = AccountSelector(TransferOperation)
        self.fee_account_widget.setObjectName(u"fee_account_widget")

        self.layout.addWidget(self.fee_account_widget, 5, 4, 1, 1)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.layout.addItem(self.vertical_spacer, 8, 0, 1, 1)

        self.withdrawal = QLineEdit(TransferOperation)
        self.withdrawal.setObjectName(u"withdrawal")
        self.withdrawal.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.withdrawal, 2, 5, 1, 2)

        self.note = QLineEdit(TransferOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 7, 2, 1, 8)

        self.commit_button = QPushButton(TransferOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 11, 1, 1)

        self.copy_date_btn = QPushButton(TransferOperation)
        self.copy_date_btn.setObjectName(u"copy_date_btn")

        self.layout.addWidget(self.copy_date_btn, 1, 3, 1, 1)

        self.withdrawal_timestamp = QDateTimeEdit(TransferOperation)
        self.withdrawal_timestamp.setObjectName(u"withdrawal_timestamp")
        self.withdrawal_timestamp.setCalendarPopup(True)
        self.withdrawal_timestamp.setTimeSpec(Qt.UTC)

        self.layout.addWidget(self.withdrawal_timestamp, 2, 2, 1, 2)

        self.number = QLineEdit(TransferOperation)
        self.number.setObjectName(u"number")

        self.layout.addWidget(self.number, 1, 9, 1, 1)

        self.from_account_widget = AccountSelector(TransferOperation)
        self.from_account_widget.setObjectName(u"from_account_widget")

        self.layout.addWidget(self.from_account_widget, 2, 4, 1, 1)

        self.fee_check = QCheckBox(TransferOperation)
        self.fee_check.setObjectName(u"fee_check")

        self.layout.addWidget(self.fee_check, 5, 2, 1, 2, Qt.AlignRight)

        self.to_account_label = QLabel(TransferOperation)
        self.to_account_label.setObjectName(u"to_account_label")
        self.to_account_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.to_account_label, 3, 0, 1, 1)

        self.date_label = QLabel(TransferOperation)
        self.date_label.setObjectName(u"date_label")

        self.layout.addWidget(self.date_label, 1, 2, 1, 1)

        self.revert_button = QPushButton(TransferOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 12, 1, 1)

        self.amount_label = QLabel(TransferOperation)
        self.amount_label.setObjectName(u"amount_label")

        self.layout.addWidget(self.amount_label, 1, 5, 1, 1)

        self.fee_currency = AccountCurrencyLabel(TransferOperation)
        self.fee_currency.setObjectName(u"fee_currency")

        self.layout.addWidget(self.fee_currency, 5, 7, 1, 1)

        self.asset_widget = AssetSelector(TransferOperation)
        self.asset_widget.setObjectName(u"asset_widget")

        self.layout.addWidget(self.asset_widget, 2, 9, 1, 1)

        self.asset_check = QCheckBox(TransferOperation)
        self.asset_check.setObjectName(u"asset_check")

        self.layout.addWidget(self.asset_check, 5, 9, 1, 1)

        self.account_label = QLabel(TransferOperation)
        self.account_label.setObjectName(u"account_label")

        self.layout.addWidget(self.account_label, 1, 4, 1, 1)

        self.fee = QLineEdit(TransferOperation)
        self.fee.setObjectName(u"fee")
        self.fee.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.fee, 5, 5, 1, 2)

        self.deposit = QLineEdit(TransferOperation)
        self.deposit.setObjectName(u"deposit")
        self.deposit.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.deposit, 3, 5, 1, 2)

        self.value_label = QLabel(TransferOperation)
        self.value_label.setObjectName(u"value_label")

        self.layout.addWidget(self.value_label, 3, 9, 1, 1)


        self.retranslateUi(TransferOperation)

        QMetaObject.connectSlotsByName(TransferOperation)
    # setupUi

    def retranslateUi(self, TransferOperation):
        TransferOperation.setWindowTitle(QCoreApplication.translate("TransferOperation", u"Form", None))
        self.to_currency.setText(QCoreApplication.translate("TransferOperation", u"CUR", None))
        self.from_currency.setText(QCoreApplication.translate("TransferOperation", u"CUR", None))
        self.from_account_label.setText(QCoreApplication.translate("TransferOperation", u"From", None))
        self.note_label.setText(QCoreApplication.translate("TransferOperation", u"Note", None))
#if QT_CONFIG(tooltip)
        self.copy_amount_btn.setToolTip(QCoreApplication.translate("TransferOperation", u"Copy value", None))
#endif // QT_CONFIG(tooltip)
        self.copy_amount_btn.setText(QCoreApplication.translate("TransferOperation", u"\u2193", None))
        self.deposit_timestamp.setDisplayFormat(QCoreApplication.translate("TransferOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.main_label.setText(QCoreApplication.translate("TransferOperation", u"Transfer", None))
        self.number_label.setText(QCoreApplication.translate("TransferOperation", u"#", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("TransferOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
#if QT_CONFIG(tooltip)
        self.copy_date_btn.setToolTip(QCoreApplication.translate("TransferOperation", u"Copy value", None))
#endif // QT_CONFIG(tooltip)
        self.copy_date_btn.setText(QCoreApplication.translate("TransferOperation", u"\u2193", None))
        self.withdrawal_timestamp.setDisplayFormat(QCoreApplication.translate("TransferOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.fee_check.setText(QCoreApplication.translate("TransferOperation", u"Include &fee", None))
        self.to_account_label.setText(QCoreApplication.translate("TransferOperation", u"To", None))
        self.date_label.setText(QCoreApplication.translate("TransferOperation", u"Date/Time", None))
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("TransferOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.amount_label.setText(QCoreApplication.translate("TransferOperation", u"Amount", None))
        self.fee_currency.setText(QCoreApplication.translate("TransferOperation", u"CUR", None))
        self.asset_check.setText(QCoreApplication.translate("TransferOperation", u"Asset transfer", None))
        self.account_label.setText(QCoreApplication.translate("TransferOperation", u"Account", None))
        self.value_label.setText(QCoreApplication.translate("TransferOperation", u"(asset cost basis in new currency)", None))
    # retranslateUi

