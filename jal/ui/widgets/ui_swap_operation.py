# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'swap_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDateTimeEdit, QGridLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QWidget)

from jal.widgets.reference_selector import ReferenceSelectorWidget

class Ui_SwapOperation(object):
    def setupUi(self, SwapOperation):
        if not SwapOperation.objectName():
            SwapOperation.setObjectName(u"SwapOperation")
        SwapOperation.resize(968, 283)
        self.layout = QGridLayout(SwapOperation)
        self.layout.setObjectName(u"layout")
        self.note_label = QLabel(SwapOperation)
        self.note_label.setObjectName(u"note_label")
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.note_label, 7, 0, 1, 1)

        self.amount_label = QLabel(SwapOperation)
        self.amount_label.setObjectName(u"amount_label")

        self.layout.addWidget(self.amount_label, 1, 7, 1, 1)

        self.out_symbol_widget = ReferenceSelectorWidget(SwapOperation)
        self.out_symbol_widget.setObjectName(u"out_symbol_widget")

        self.layout.addWidget(self.out_symbol_widget, 2, 9, 1, 1)

        self.cross_chain_check = QCheckBox(SwapOperation)
        self.cross_chain_check.setObjectName(u"cross_chain_check")
        self.cross_chain_check.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.layout.addWidget(self.cross_chain_check, 0, 2, 1, 1)

        self.in_qty = QLineEdit(SwapOperation)
        self.in_qty.setObjectName(u"in_qty")
        self.in_qty.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.in_qty, 4, 7, 1, 1)

        self.in_timestamp = QDateTimeEdit(SwapOperation)
        self.in_timestamp.setObjectName(u"in_timestamp")
        self.in_timestamp.setCalendarPopup(True)
        self.in_timestamp.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.in_timestamp, 4, 2, 1, 1)

        self.revert_button = QPushButton(SwapOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 14, 1, 1)

        self.date_label = QLabel(SwapOperation)
        self.date_label.setObjectName(u"date_label")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.date_label, 1, 2, 1, 1)

        self.account_label = QLabel(SwapOperation)
        self.account_label.setObjectName(u"account_label")
        self.account_label.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.account_label, 1, 5, 1, 1)

        self.fee_check = QCheckBox(SwapOperation)
        self.fee_check.setObjectName(u"fee_check")
        self.fee_check.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.layout.addWidget(self.fee_check, 6, 5, 1, 1)

        self.in_tx_hash = QLineEdit(SwapOperation)
        self.in_tx_hash.setObjectName(u"in_tx_hash")

        self.layout.addWidget(self.in_tx_hash, 4, 11, 1, 1)

        self.to_label = QLabel(SwapOperation)
        self.to_label.setObjectName(u"to_label")
        self.to_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.to_label, 4, 0, 1, 1)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 2, 12, 1, 1)

        self.assetGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.assetGroupSpacer, 1, 8, 1, 1)

        self.in_account_widget = ReferenceSelectorWidget(SwapOperation)
        self.in_account_widget.setObjectName(u"in_account_widget")

        self.layout.addWidget(self.in_account_widget, 4, 5, 1, 1)

        self.timestamp = QDateTimeEdit(SwapOperation)
        self.timestamp.setObjectName(u"timestamp")
        self.timestamp.setCalendarPopup(True)
        self.timestamp.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.timestamp, 2, 2, 1, 1)

        self.tx_hash = QLineEdit(SwapOperation)
        self.tx_hash.setObjectName(u"tx_hash")

        self.layout.addWidget(self.tx_hash, 2, 11, 1, 1)

        self.txHashGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.txHashGroupSpacer, 1, 10, 1, 1)

        self.fee_qty = QLineEdit(SwapOperation)
        self.fee_qty.setObjectName(u"fee_qty")
        self.fee_qty.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.fee_qty, 6, 7, 1, 1)

        self.amountGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.amountGroupSpacer, 1, 6, 1, 1)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 8, 0, 1, 1)

        self.in_symbol_widget = ReferenceSelectorWidget(SwapOperation)
        self.in_symbol_widget.setObjectName(u"in_symbol_widget")

        self.layout.addWidget(self.in_symbol_widget, 4, 9, 1, 1)

        self.tx_hash_label = QLabel(SwapOperation)
        self.tx_hash_label.setObjectName(u"tx_hash_label")
        self.tx_hash_label.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.tx_hash_label, 1, 11, 1, 1)

        self.account_widget = ReferenceSelectorWidget(SwapOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 2, 5, 1, 1)

        self.accountGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.accountGroupSpacer, 1, 4, 1, 1)

        self.asset_label = QLabel(SwapOperation)
        self.asset_label.setObjectName(u"asset_label")

        self.layout.addWidget(self.asset_label, 1, 9, 1, 1)

        self.note = QLineEdit(SwapOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 7, 2, 1, 10)

        self.fee_symbol_widget = ReferenceSelectorWidget(SwapOperation)
        self.fee_symbol_widget.setObjectName(u"fee_symbol_widget")

        self.layout.addWidget(self.fee_symbol_widget, 6, 9, 1, 1)

        self.main_label = QLabel(SwapOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.from_label = QLabel(SwapOperation)
        self.from_label.setObjectName(u"from_label")
        self.from_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.from_label, 2, 0, 1, 1)

        self.out_qty = QLineEdit(SwapOperation)
        self.out_qty.setObjectName(u"out_qty")
        self.out_qty.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.out_qty, 2, 7, 1, 1)

        self.commit_button = QPushButton(SwapOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 13, 1, 1)

#if QT_CONFIG(shortcut)
        self.note_label.setBuddy(self.note)
        self.to_label.setBuddy(self.in_timestamp)
        self.main_label.setBuddy(self.cross_chain_check)
        self.from_label.setBuddy(self.timestamp)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.cross_chain_check, self.timestamp)
        QWidget.setTabOrder(self.timestamp, self.account_widget)
        QWidget.setTabOrder(self.account_widget, self.out_qty)
        QWidget.setTabOrder(self.out_qty, self.out_symbol_widget)
        QWidget.setTabOrder(self.out_symbol_widget, self.tx_hash)
        QWidget.setTabOrder(self.tx_hash, self.in_timestamp)
        QWidget.setTabOrder(self.in_timestamp, self.in_account_widget)
        QWidget.setTabOrder(self.in_account_widget, self.in_qty)
        QWidget.setTabOrder(self.in_qty, self.in_symbol_widget)
        QWidget.setTabOrder(self.in_symbol_widget, self.in_tx_hash)
        QWidget.setTabOrder(self.in_tx_hash, self.fee_check)
        QWidget.setTabOrder(self.fee_check, self.fee_qty)
        QWidget.setTabOrder(self.fee_qty, self.fee_symbol_widget)
        QWidget.setTabOrder(self.fee_symbol_widget, self.note)

        self.retranslateUi(SwapOperation)

        QMetaObject.connectSlotsByName(SwapOperation)
    # setupUi

    def retranslateUi(self, SwapOperation):
        SwapOperation.setWindowTitle(QCoreApplication.translate("SwapOperation", u"Form", None))
        self.note_label.setText(QCoreApplication.translate("SwapOperation", u"Note", None))
        self.amount_label.setText(QCoreApplication.translate("SwapOperation", u"Amount", None))
#if QT_CONFIG(tooltip)
        self.cross_chain_check.setToolTip(QCoreApplication.translate("SwapOperation", u"The exchanged asset is received on another account (chain), in a separate transaction", None))
#endif // QT_CONFIG(tooltip)
        self.cross_chain_check.setText(QCoreApplication.translate("SwapOperation", u"Cross &chain", None))
        self.in_timestamp.setDisplayFormat(QCoreApplication.translate("SwapOperation", u"dd/MM/yyyy hh:mm:ss", None))
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("SwapOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.date_label.setText(QCoreApplication.translate("SwapOperation", u"Date/Time", None))
        self.account_label.setText(QCoreApplication.translate("SwapOperation", u"Account", None))
        self.fee_check.setText(QCoreApplication.translate("SwapOperation", u"Include &fee", None))
        self.to_label.setText(QCoreApplication.translate("SwapOperation", u"To", None))
        self.timestamp.setDisplayFormat(QCoreApplication.translate("SwapOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.tx_hash_label.setText(QCoreApplication.translate("SwapOperation", u"Tx hash", None))
        self.asset_label.setText(QCoreApplication.translate("SwapOperation", u"Asset", None))
        self.main_label.setText(QCoreApplication.translate("SwapOperation", u"Swap", None))
        self.from_label.setText(QCoreApplication.translate("SwapOperation", u"From", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("SwapOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
    # retranslateUi

