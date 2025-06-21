# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'trade_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QDateEdit, QDateTimeEdit, QGridLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QWidget)

from jal.widgets.account_select import AccountCurrencyLabel
from jal.widgets.reference_selector import (AccountSelector, AssetSelector)

class Ui_TradeOperation(object):
    def setupUi(self, TradeOperation):
        if not TradeOperation.objectName():
            TradeOperation.setObjectName(u"TradeOperation")
        TradeOperation.resize(968, 210)
        self.layout = QGridLayout(TradeOperation)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.price_label = QLabel(TradeOperation)
        self.price_label.setObjectName(u"price_label")
        self.price_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.price_label, 2, 7, 1, 1)

        self.qty_edit = QLineEdit(TradeOperation)
        self.qty_edit.setObjectName(u"qty_edit")
        self.qty_edit.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.qty_edit, 1, 8, 1, 1)

        self.commit_button = QPushButton(TradeOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 11, 1, 1)

        self.price_edit = QLineEdit(TradeOperation)
        self.price_edit.setObjectName(u"price_edit")
        self.price_edit.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.price_edit, 2, 8, 1, 1)

        self.currency_fee = AccountCurrencyLabel(TradeOperation)
        self.currency_fee.setObjectName(u"currency_fee")

        self.layout.addWidget(self.currency_fee, 3, 9, 1, 1)

        self.date_label = QLabel(TradeOperation)
        self.date_label.setObjectName(u"date_label")

        self.layout.addWidget(self.date_label, 1, 0, 1, 1)

        self.symbol_label = QLabel(TradeOperation)
        self.symbol_label.setObjectName(u"symbol_label")

        self.layout.addWidget(self.symbol_label, 3, 0, 1, 1)

        self.main_label = QLabel(TradeOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.settlement_label = QLabel(TradeOperation)
        self.settlement_label.setObjectName(u"settlement_label")

        self.layout.addWidget(self.settlement_label, 1, 2, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontalSpacer, 2, 10, 1, 1)

        self.comment_label = QLabel(TradeOperation)
        self.comment_label.setObjectName(u"comment_label")

        self.layout.addWidget(self.comment_label, 4, 0, 1, 1)

        self.account_label = QLabel(TradeOperation)
        self.account_label.setObjectName(u"account_label")

        self.layout.addWidget(self.account_label, 2, 0, 1, 1)

        self.fee_label = QLabel(TradeOperation)
        self.fee_label.setObjectName(u"fee_label")
        self.fee_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.fee_label, 3, 7, 1, 1)

        self.qty_label = QLabel(TradeOperation)
        self.qty_label.setObjectName(u"qty_label")
        self.qty_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.qty_label, 1, 7, 1, 1)

        self.currency_price = AccountCurrencyLabel(TradeOperation)
        self.currency_price.setObjectName(u"currency_price")

        self.layout.addWidget(self.currency_price, 2, 9, 1, 1)

        self.fee_edit = QLineEdit(TradeOperation)
        self.fee_edit.setObjectName(u"fee_edit")
        self.fee_edit.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.fee_edit, 3, 8, 1, 1)

        self.revert_button = QPushButton(TradeOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 12, 1, 1)

        self.number_label = QLabel(TradeOperation)
        self.number_label.setObjectName(u"number_label")
        self.number_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.number_label, 1, 5, 1, 1)

        self.timestamp_editor = QDateTimeEdit(TradeOperation)
        self.timestamp_editor.setObjectName(u"timestamp_editor")
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 1)

        self.settlement_editor = QDateEdit(TradeOperation)
        self.settlement_editor.setObjectName(u"settlement_editor")
        self.settlement_editor.setCalendarPopup(True)

        self.layout.addWidget(self.settlement_editor, 1, 3, 1, 1)

        self.account_widget = AccountSelector(TradeOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 2, 1, 1, 6)

        self.note = QLineEdit(TradeOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 4, 1, 1, 9)

        self.asset_widget = AssetSelector(TradeOperation)
        self.asset_widget.setObjectName(u"asset_widget")

        self.layout.addWidget(self.asset_widget, 3, 1, 1, 6)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 5, 0, 1, 1)

        self.number = QLineEdit(TradeOperation)
        self.number.setObjectName(u"number")

        self.layout.addWidget(self.number, 1, 6, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontalSpacer_2, 1, 4, 1, 1)


        self.retranslateUi(TradeOperation)

        QMetaObject.connectSlotsByName(TradeOperation)
    # setupUi

    def retranslateUi(self, TradeOperation):
        TradeOperation.setWindowTitle(QCoreApplication.translate("TradeOperation", u"Form", None))
        self.price_label.setText(QCoreApplication.translate("TradeOperation", u"Price", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("TradeOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
        self.currency_fee.setText(QCoreApplication.translate("TradeOperation", u"CUR", None))
        self.date_label.setText(QCoreApplication.translate("TradeOperation", u"Date/Time", None))
        self.symbol_label.setText(QCoreApplication.translate("TradeOperation", u"Asset", None))
        self.main_label.setText(QCoreApplication.translate("TradeOperation", u"Buy / Sell", None))
        self.settlement_label.setText(QCoreApplication.translate("TradeOperation", u"Settlement", None))
        self.comment_label.setText(QCoreApplication.translate("TradeOperation", u"Note", None))
        self.account_label.setText(QCoreApplication.translate("TradeOperation", u"Account", None))
        self.fee_label.setText(QCoreApplication.translate("TradeOperation", u"Fee", None))
        self.qty_label.setText(QCoreApplication.translate("TradeOperation", u"Qty", None))
        self.currency_price.setText(QCoreApplication.translate("TradeOperation", u"CUR", None))
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("TradeOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.number_label.setText(QCoreApplication.translate("TradeOperation", u"#", None))
        self.timestamp_editor.setDisplayFormat(QCoreApplication.translate("TradeOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.settlement_editor.setDisplayFormat(QCoreApplication.translate("TradeOperation", u"dd/MM/yyyy", None))
    # retranslateUi

