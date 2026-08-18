# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'bridge_operation.ui'
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
    QSpacerItem, QToolButton, QWidget)

from jal.widgets.reference_selector import ReferenceSelectorWidget

class Ui_BridgeOperation(object):
    def setupUi(self, BridgeOperation):
        if not BridgeOperation.objectName():
            BridgeOperation.setObjectName(u"BridgeOperation")
        BridgeOperation.resize(968, 283)
        self.layout = QGridLayout(BridgeOperation)
        self.layout.setObjectName(u"layout")
        self.main_label = QLabel(BridgeOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.commit_button = QPushButton(BridgeOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 13, 1, 1)

        self.revert_button = QPushButton(BridgeOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 14, 1, 1)

        self.date_label = QLabel(BridgeOperation)
        self.date_label.setObjectName(u"date_label")

        self.layout.addWidget(self.date_label, 1, 1, 1, 1)

        self.account_label = QLabel(BridgeOperation)
        self.account_label.setObjectName(u"account_label")

        self.layout.addWidget(self.account_label, 1, 4, 1, 1)

        self.amount_label = QLabel(BridgeOperation)
        self.amount_label.setObjectName(u"amount_label")

        self.layout.addWidget(self.amount_label, 1, 6, 1, 1)

        self.symbol_label = QLabel(BridgeOperation)
        self.symbol_label.setObjectName(u"symbol_label")

        self.layout.addWidget(self.symbol_label, 1, 8, 1, 1)

        self.tx_hash_label = QLabel(BridgeOperation)
        self.tx_hash_label.setObjectName(u"tx_hash_label")

        self.layout.addWidget(self.tx_hash_label, 1, 10, 1, 2)

        self.out_tx_hash = QLineEdit(BridgeOperation)
        self.out_tx_hash.setObjectName(u"out_tx_hash")

        self.layout.addWidget(self.out_tx_hash, 2, 10, 1, 2)

        self.in_tx_hash = QLineEdit(BridgeOperation)
        self.in_tx_hash.setObjectName(u"in_tx_hash")

        self.layout.addWidget(self.in_tx_hash, 3, 10, 1, 2)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 1, 12, 1, 1)

        self.from_account_label = QLabel(BridgeOperation)
        self.from_account_label.setObjectName(u"from_account_label")
        self.from_account_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.from_account_label, 2, 0, 1, 1)

        self.out_timestamp = QDateTimeEdit(BridgeOperation)
        self.out_timestamp.setObjectName(u"out_timestamp")
        self.out_timestamp.setCalendarPopup(True)
        self.out_timestamp.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.out_timestamp, 2, 1, 1, 2)

        self.copy_date_btn = QToolButton(BridgeOperation)
        self.copy_date_btn.setObjectName(u"copy_date_btn")
        self.copy_date_btn.setAutoRaise(True)

        self.layout.addWidget(self.copy_date_btn, 2, 3, 1, 1)

        self.from_account_widget = ReferenceSelectorWidget(BridgeOperation)
        self.from_account_widget.setObjectName(u"from_account_widget")

        self.layout.addWidget(self.from_account_widget, 2, 4, 1, 1)

        self.out_qty = QLineEdit(BridgeOperation)
        self.out_qty.setObjectName(u"out_qty")
        self.out_qty.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.out_qty, 2, 6, 1, 2)

        self.out_symbol_widget = ReferenceSelectorWidget(BridgeOperation)
        self.out_symbol_widget.setObjectName(u"out_symbol_widget")

        self.layout.addWidget(self.out_symbol_widget, 2, 8, 1, 1)

        self.copy_amount_btn = QToolButton(BridgeOperation)
        self.copy_amount_btn.setObjectName(u"copy_amount_btn")
        self.copy_amount_btn.setAutoRaise(True)

        self.layout.addWidget(self.copy_amount_btn, 2, 9, 1, 1)

        self.to_account_label = QLabel(BridgeOperation)
        self.to_account_label.setObjectName(u"to_account_label")
        self.to_account_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.to_account_label, 3, 0, 1, 1)

        self.in_timestamp = QDateTimeEdit(BridgeOperation)
        self.in_timestamp.setObjectName(u"in_timestamp")
        self.in_timestamp.setCalendarPopup(True)
        self.in_timestamp.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.in_timestamp, 3, 1, 1, 2)

        self.to_account_widget = ReferenceSelectorWidget(BridgeOperation)
        self.to_account_widget.setObjectName(u"to_account_widget")

        self.layout.addWidget(self.to_account_widget, 3, 4, 1, 1)

        self.in_qty = QLineEdit(BridgeOperation)
        self.in_qty.setObjectName(u"in_qty")
        self.in_qty.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.in_qty, 3, 6, 1, 2)

        self.in_symbol_widget = ReferenceSelectorWidget(BridgeOperation)
        self.in_symbol_widget.setObjectName(u"in_symbol_widget")

        self.layout.addWidget(self.in_symbol_widget, 3, 8, 1, 1)

        self.fee_check = QCheckBox(BridgeOperation)
        self.fee_check.setObjectName(u"fee_check")

        self.layout.addWidget(self.fee_check, 4, 1, 1, 2, Qt.AlignmentFlag.AlignRight)

        self.fee_qty = QLineEdit(BridgeOperation)
        self.fee_qty.setObjectName(u"fee_qty")
        self.fee_qty.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.fee_qty, 4, 6, 1, 2)

        self.fee_symbol_widget = ReferenceSelectorWidget(BridgeOperation)
        self.fee_symbol_widget.setObjectName(u"fee_symbol_widget")

        self.layout.addWidget(self.fee_symbol_widget, 4, 8, 1, 1)

        self.note_label = QLabel(BridgeOperation)
        self.note_label.setObjectName(u"note_label")
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.note_label, 5, 0, 1, 1)

        self.note = QLineEdit(BridgeOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 5, 1, 1, 11)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 6, 0, 1, 1)

        self.amountGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.amountGroupSpacer, 1, 5, 1, 1)

#if QT_CONFIG(shortcut)
        self.from_account_label.setBuddy(self.out_timestamp)
        self.to_account_label.setBuddy(self.in_timestamp)
        self.note_label.setBuddy(self.note)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.out_timestamp, self.copy_date_btn)
        QWidget.setTabOrder(self.copy_date_btn, self.from_account_widget)
        QWidget.setTabOrder(self.from_account_widget, self.out_qty)
        QWidget.setTabOrder(self.out_qty, self.out_symbol_widget)
        QWidget.setTabOrder(self.out_symbol_widget, self.copy_amount_btn)
        QWidget.setTabOrder(self.copy_amount_btn, self.out_tx_hash)
        QWidget.setTabOrder(self.out_tx_hash, self.in_timestamp)
        QWidget.setTabOrder(self.in_timestamp, self.to_account_widget)
        QWidget.setTabOrder(self.to_account_widget, self.in_qty)
        QWidget.setTabOrder(self.in_qty, self.in_symbol_widget)
        QWidget.setTabOrder(self.in_symbol_widget, self.in_tx_hash)
        QWidget.setTabOrder(self.in_tx_hash, self.fee_check)
        QWidget.setTabOrder(self.fee_check, self.fee_qty)
        QWidget.setTabOrder(self.fee_qty, self.fee_symbol_widget)
        QWidget.setTabOrder(self.fee_symbol_widget, self.note)
        QWidget.setTabOrder(self.note, self.commit_button)
        QWidget.setTabOrder(self.commit_button, self.revert_button)

        self.retranslateUi(BridgeOperation)

        QMetaObject.connectSlotsByName(BridgeOperation)
    # setupUi

    def retranslateUi(self, BridgeOperation):
        BridgeOperation.setWindowTitle(QCoreApplication.translate("BridgeOperation", u"Form", None))
        self.main_label.setText(QCoreApplication.translate("BridgeOperation", u"Bridge", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("BridgeOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("BridgeOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.date_label.setText(QCoreApplication.translate("BridgeOperation", u"Date/Time", None))
        self.account_label.setText(QCoreApplication.translate("BridgeOperation", u"Account", None))
        self.amount_label.setText(QCoreApplication.translate("BridgeOperation", u"Amount", None))
        self.symbol_label.setText(QCoreApplication.translate("BridgeOperation", u"Symbol", None))
        self.tx_hash_label.setText(QCoreApplication.translate("BridgeOperation", u"Tx hash", None))
        self.from_account_label.setText(QCoreApplication.translate("BridgeOperation", u"From", None))
        self.out_timestamp.setDisplayFormat(QCoreApplication.translate("BridgeOperation", u"dd/MM/yyyy hh:mm:ss", None))
#if QT_CONFIG(tooltip)
        self.copy_date_btn.setToolTip(QCoreApplication.translate("BridgeOperation", u"Copy value", None))
#endif // QT_CONFIG(tooltip)
        self.copy_date_btn.setText(QCoreApplication.translate("BridgeOperation", u"\u2193", None))
#if QT_CONFIG(tooltip)
        self.copy_amount_btn.setToolTip(QCoreApplication.translate("BridgeOperation", u"Copy value", None))
#endif // QT_CONFIG(tooltip)
        self.copy_amount_btn.setText(QCoreApplication.translate("BridgeOperation", u"\u2193", None))
        self.to_account_label.setText(QCoreApplication.translate("BridgeOperation", u"To", None))
        self.in_timestamp.setDisplayFormat(QCoreApplication.translate("BridgeOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.fee_check.setText(QCoreApplication.translate("BridgeOperation", u"Include &fee", None))
        self.note_label.setText(QCoreApplication.translate("BridgeOperation", u"Note", None))
    # retranslateUi

