# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'conversion_operation.ui'
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

class Ui_ConversionOperation(object):
    def setupUi(self, ConversionOperation):
        if not ConversionOperation.objectName():
            ConversionOperation.setObjectName(u"ConversionOperation")
        ConversionOperation.resize(968, 247)
        self.layout = QGridLayout(ConversionOperation)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.main_label = QLabel(ConversionOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 0, 6, 1, 1)

        self.commit_button = QPushButton(ConversionOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 7, 1, 1)

        self.revert_button = QPushButton(ConversionOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 8, 1, 1)

        self.date_label = QLabel(ConversionOperation)
        self.date_label.setObjectName(u"date_label")
        self.date_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1)

        self.timestamp = QDateTimeEdit(ConversionOperation)
        self.timestamp.setObjectName(u"timestamp")
        self.timestamp.setCalendarPopup(True)
        self.timestamp.setTimeSpec(Qt.UTC)

        self.layout.addWidget(self.timestamp, 1, 1, 1, 1)

        self.account_label = QLabel(ConversionOperation)
        self.account_label.setObjectName(u"account_label")
        self.account_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.account_label, 1, 2, 1, 1)

        self.account_widget = ReferenceSelectorWidget(ConversionOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 1, 3, 1, 1)

        self.tx_hash_label = QLabel(ConversionOperation)
        self.tx_hash_label.setObjectName(u"tx_hash_label")
        self.tx_hash_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.tx_hash_label, 1, 4, 1, 1)

        self.tx_hash = QLineEdit(ConversionOperation)
        self.tx_hash.setObjectName(u"tx_hash")

        self.layout.addWidget(self.tx_hash, 1, 5, 1, 1)

        self.converted_label = QLabel(ConversionOperation)
        self.converted_label.setObjectName(u"converted_label")
        self.converted_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.converted_label, 2, 0, 1, 1)

        self.out_qty = QLineEdit(ConversionOperation)
        self.out_qty.setObjectName(u"out_qty")
        self.out_qty.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.out_qty, 2, 1, 1, 1)

        self.out_symbol_widget = ReferenceSelectorWidget(ConversionOperation)
        self.out_symbol_widget.setObjectName(u"out_symbol_widget")

        self.layout.addWidget(self.out_symbol_widget, 2, 2, 1, 2)

        self.received_label = QLabel(ConversionOperation)
        self.received_label.setObjectName(u"received_label")
        self.received_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.received_label, 3, 0, 1, 1)

        self.in_qty = QLineEdit(ConversionOperation)
        self.in_qty.setObjectName(u"in_qty")
        self.in_qty.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.in_qty, 3, 1, 1, 1)

        self.in_symbol_widget = ReferenceSelectorWidget(ConversionOperation)
        self.in_symbol_widget.setObjectName(u"in_symbol_widget")

        self.layout.addWidget(self.in_symbol_widget, 3, 2, 1, 2)

        self.basis_hint = QLabel(ConversionOperation)
        self.basis_hint.setObjectName(u"basis_hint")
        self.basis_hint.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)

        self.layout.addWidget(self.basis_hint, 3, 4, 1, 2)

        self.fee_check = QCheckBox(ConversionOperation)
        self.fee_check.setObjectName(u"fee_check")
        self.fee_check.setLayoutDirection(Qt.RightToLeft)

        self.layout.addWidget(self.fee_check, 4, 0, 1, 1)

        self.fee_qty = QLineEdit(ConversionOperation)
        self.fee_qty.setObjectName(u"fee_qty")
        self.fee_qty.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.fee_qty, 4, 1, 1, 1)

        self.fee_symbol_widget = ReferenceSelectorWidget(ConversionOperation)
        self.fee_symbol_widget.setObjectName(u"fee_symbol_widget")

        self.layout.addWidget(self.fee_symbol_widget, 4, 2, 1, 2)

        self.note_label = QLabel(ConversionOperation)
        self.note_label.setObjectName(u"note_label")
        self.note_label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.layout.addWidget(self.note_label, 5, 0, 1, 1)

        self.note = QLineEdit(ConversionOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 5, 1, 1, 5)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 6, 0, 1, 1)


        self.retranslateUi(ConversionOperation)

        QMetaObject.connectSlotsByName(ConversionOperation)
    # setupUi

    def retranslateUi(self, ConversionOperation):
        ConversionOperation.setWindowTitle(QCoreApplication.translate("ConversionOperation", u"Form", None))
        self.main_label.setText(QCoreApplication.translate("ConversionOperation", u"Conversion", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("ConversionOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("ConversionOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.date_label.setText(QCoreApplication.translate("ConversionOperation", u"Date/Time", None))
        self.timestamp.setDisplayFormat(QCoreApplication.translate("ConversionOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.account_label.setText(QCoreApplication.translate("ConversionOperation", u"Account", None))
        self.tx_hash_label.setText(QCoreApplication.translate("ConversionOperation", u"Tx hash", None))
        self.converted_label.setText(QCoreApplication.translate("ConversionOperation", u"Converted", None))
        self.received_label.setText(QCoreApplication.translate("ConversionOperation", u"Received", None))
        self.basis_hint.setText(QCoreApplication.translate("ConversionOperation", u"Cost basis is carried over - no profit or loss is realized", None))
        self.fee_check.setText(QCoreApplication.translate("ConversionOperation", u"Include &fee", None))
        self.note_label.setText(QCoreApplication.translate("ConversionOperation", u"Note", None))
    # retranslateUi

