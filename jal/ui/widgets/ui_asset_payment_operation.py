# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'asset_payment_operation.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDateEdit, QDateTimeEdit,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpacerItem, QWidget)

from jal.widgets.account_select import AccountCurrencyLabel
from jal.widgets.reference_selector import ReferenceSelectorWidget

class Ui_AssetPaymentOperation(object):
    def setupUi(self, AssetPaymentOperation):
        if not AssetPaymentOperation.objectName():
            AssetPaymentOperation.setObjectName(u"AssetPaymentOperation")
        AssetPaymentOperation.resize(968, 195)
        self.layout = QGridLayout(AssetPaymentOperation)
        self.layout.setObjectName(u"layout")
        self.note = QLineEdit(AssetPaymentOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 4, 1, 1, 12)

        self.date_label = QLabel(AssetPaymentOperation)
        self.date_label.setObjectName(u"date_label")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1)

        self.number_label = QLabel(AssetPaymentOperation)
        self.number_label.setObjectName(u"number_label")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.number_label, 1, 10, 1, 1)

        self.commit_button = QPushButton(AssetPaymentOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 14, 1, 1)

        self.price_edit = QLineEdit(AssetPaymentOperation)
        self.price_edit.setObjectName(u"price_edit")
        self.price_edit.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.price_edit, 2, 11, 1, 1)

        self.type_label = QLabel(AssetPaymentOperation)
        self.type_label.setObjectName(u"type_label")
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.type_label, 1, 7, 1, 1)

        self.tax_label = QLabel(AssetPaymentOperation)
        self.tax_label.setObjectName(u"tax_label")
        self.tax_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.tax_label, 3, 7, 1, 1)

        self.number = QLineEdit(AssetPaymentOperation)
        self.number.setObjectName(u"number")

        self.layout.addWidget(self.number, 1, 11, 1, 1)

        self.symbol_label = QLabel(AssetPaymentOperation)
        self.symbol_label.setObjectName(u"symbol_label")
        self.symbol_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.symbol_label, 3, 0, 1, 1)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 5, 0, 1, 1)

        self.main_label = QLabel(AssetPaymentOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 2, 13, 1, 1)

        self.ex_date_editor = QDateEdit(AssetPaymentOperation)
        self.ex_date_editor.setObjectName(u"ex_date_editor")
        self.ex_date_editor.setMinimumDate(QDate(1970, 1, 1))
        self.ex_date_editor.setMaximumTime(QTime(23, 59, 59))
        self.ex_date_editor.setCalendarPopup(True)
        self.ex_date_editor.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.ex_date_editor, 1, 4, 1, 1)

        self.account_widget = ReferenceSelectorWidget(AssetPaymentOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 2, 1, 1, 5)

        self.symbol_widget = ReferenceSelectorWidget(AssetPaymentOperation)
        self.symbol_widget.setObjectName(u"symbol_widget")

        self.layout.addWidget(self.symbol_widget, 3, 1, 1, 5)

        self.note_label = QLabel(AssetPaymentOperation)
        self.note_label.setObjectName(u"note_label")
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.note_label, 4, 0, 1, 1)

        self.account_label = QLabel(AssetPaymentOperation)
        self.account_label.setObjectName(u"account_label")
        self.account_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.account_label, 2, 0, 1, 1)

        self.ex_date_label = QLabel(AssetPaymentOperation)
        self.ex_date_label.setObjectName(u"ex_date_label")

        self.layout.addWidget(self.ex_date_label, 1, 3, 1, 1)

        self.revert_button = QPushButton(AssetPaymentOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 15, 1, 1)

        self.amount_label = QLabel(AssetPaymentOperation)
        self.amount_label.setObjectName(u"amount_label")
        self.amount_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.amount_label, 2, 7, 1, 1)

        self.dividend_edit = QLineEdit(AssetPaymentOperation)
        self.dividend_edit.setObjectName(u"dividend_edit")
        self.dividend_edit.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.dividend_edit, 2, 8, 1, 1)

        self.type = QComboBox(AssetPaymentOperation)
        self.type.setObjectName(u"type")

        self.layout.addWidget(self.type, 1, 8, 1, 1)

        self.timestamp_editor = QDateTimeEdit(AssetPaymentOperation)
        self.timestamp_editor.setObjectName(u"timestamp_editor")
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 1)

        self.price_label = QLabel(AssetPaymentOperation)
        self.price_label.setObjectName(u"price_label")

        self.layout.addWidget(self.price_label, 2, 10, 1, 1)

        self.dateGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.dateGroupSpacer, 1, 2, 1, 1)

        self.typeGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.typeGroupSpacer, 1, 6, 1, 1)

        self.numberGroupSpacer = QSpacerItem(0, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.numberGroupSpacer, 1, 9, 1, 1)

        self.taxCurrencyBox = QHBoxLayout()
        self.taxCurrencyBox.setSpacing(3)
        self.taxCurrencyBox.setObjectName(u"taxCurrencyBox")
        self.taxCurrencyBox.setContentsMargins(0, 0, 0, 0)
        self.tax_edit = QLineEdit(AssetPaymentOperation)
        self.tax_edit.setObjectName(u"tax_edit")
        self.tax_edit.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.taxCurrencyBox.addWidget(self.tax_edit)

        self.currency = AccountCurrencyLabel(AssetPaymentOperation)
        self.currency.setObjectName(u"currency")

        self.taxCurrencyBox.addWidget(self.currency)


        self.layout.addLayout(self.taxCurrencyBox, 3, 8, 1, 1)

#if QT_CONFIG(shortcut)
        self.date_label.setBuddy(self.timestamp_editor)
        self.number_label.setBuddy(self.number)
        self.type_label.setBuddy(self.type)
        self.tax_label.setBuddy(self.tax_edit)
        self.symbol_label.setBuddy(self.symbol_widget)
        self.note_label.setBuddy(self.note)
        self.account_label.setBuddy(self.account_widget)
        self.ex_date_label.setBuddy(self.ex_date_editor)
        self.amount_label.setBuddy(self.dividend_edit)
        self.price_label.setBuddy(self.price_edit)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.timestamp_editor, self.ex_date_editor)
        QWidget.setTabOrder(self.ex_date_editor, self.type)
        QWidget.setTabOrder(self.type, self.number)
        QWidget.setTabOrder(self.number, self.account_widget)
        QWidget.setTabOrder(self.account_widget, self.symbol_widget)
        QWidget.setTabOrder(self.symbol_widget, self.dividend_edit)
        QWidget.setTabOrder(self.dividend_edit, self.price_edit)
        QWidget.setTabOrder(self.price_edit, self.tax_edit)
        QWidget.setTabOrder(self.tax_edit, self.note)
        QWidget.setTabOrder(self.note, self.commit_button)
        QWidget.setTabOrder(self.commit_button, self.revert_button)

        self.retranslateUi(AssetPaymentOperation)

        QMetaObject.connectSlotsByName(AssetPaymentOperation)
    # setupUi

    def retranslateUi(self, AssetPaymentOperation):
        AssetPaymentOperation.setWindowTitle(QCoreApplication.translate("AssetPaymentOperation", u"Form", None))
        self.date_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"D&ate/Time", None))
        self.number_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"#", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("AssetPaymentOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
        self.type_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"T&ype", None))
        self.tax_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"Ta&x", None))
        self.symbol_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"Ass&et", None))
        self.main_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"Asset Payment", None))
        self.ex_date_editor.setSpecialValueText(QCoreApplication.translate("AssetPaymentOperation", u"unknown", None))
        self.ex_date_editor.setDisplayFormat(QCoreApplication.translate("AssetPaymentOperation", u"dd/MM/yyyy", None))
        self.note_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"&Note", None))
        self.account_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"A&ccount", None))
        self.ex_date_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"Ex-Date", None))
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("AssetPaymentOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.amount_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"Di&vidend", None))
        self.timestamp_editor.setDisplayFormat(QCoreApplication.translate("AssetPaymentOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.price_label.setText(QCoreApplication.translate("AssetPaymentOperation", u"P&rice", None))
        self.currency.setText(QCoreApplication.translate("AssetPaymentOperation", u"CUR", None))
    # retranslateUi

