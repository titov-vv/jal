# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'chain_action_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDateTimeEdit, QGridLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QWidget)

from jal.widgets.fee_widget import FeeWidget
from jal.widgets.reference_selector import ReferenceSelectorWidget

class Ui_ChainActionOperation(object):
    def setupUi(self, ChainActionOperation):
        if not ChainActionOperation.objectName():
            ChainActionOperation.setObjectName(u"ChainActionOperation")
        ChainActionOperation.resize(968, 247)
        self.layout = QGridLayout(ChainActionOperation)
        self.layout.setObjectName(u"layout")
        self.main_label = QLabel(ChainActionOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 0, 7, 1, 1)

        self.commit_button = QPushButton(ChainActionOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 8, 1, 1)

        self.revert_button = QPushButton(ChainActionOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 9, 1, 1)

        self.date_label = QLabel(ChainActionOperation)
        self.date_label.setObjectName(u"date_label")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.date_label, 1, 0, 1, 1)

        self.timestamp = QDateTimeEdit(ChainActionOperation)
        self.timestamp.setObjectName(u"timestamp")
        self.timestamp.setCalendarPopup(True)
        self.timestamp.setTimeSpec(Qt.TimeSpec.UTC)

        self.layout.addWidget(self.timestamp, 1, 1, 1, 1)

        self.type_label = QLabel(ChainActionOperation)
        self.type_label.setObjectName(u"type_label")
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.type_label, 1, 2, 1, 1)

        self.type = QComboBox(ChainActionOperation)
        self.type.setObjectName(u"type")

        self.layout.addWidget(self.type, 1, 3, 1, 1)

        self.tx_hash_label = QLabel(ChainActionOperation)
        self.tx_hash_label.setObjectName(u"tx_hash_label")
        self.tx_hash_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.tx_hash_label, 1, 5, 1, 1)

        self.number = QLineEdit(ChainActionOperation)
        self.number.setObjectName(u"number")

        self.layout.addWidget(self.number, 1, 6, 1, 1)

        self.account_label = QLabel(ChainActionOperation)
        self.account_label.setObjectName(u"account_label")
        self.account_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.account_label, 2, 0, 1, 1)

        self.account_widget = ReferenceSelectorWidget(ChainActionOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 2, 1, 1, 3)

        self.symbol_label = QLabel(ChainActionOperation)
        self.symbol_label.setObjectName(u"symbol_label")
        self.symbol_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.symbol_label, 3, 0, 1, 1)

        self.symbol_widget = ReferenceSelectorWidget(ChainActionOperation)
        self.symbol_widget.setObjectName(u"symbol_widget")

        self.layout.addWidget(self.symbol_widget, 3, 1, 1, 3)

        self.fee_label = QLabel(ChainActionOperation)
        self.fee_label.setObjectName(u"fee_label")
        self.fee_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.fee_label, 4, 0, 1, 1)

        self.fee_widget = FeeWidget(ChainActionOperation)
        self.fee_widget.setObjectName(u"fee_widget")

        self.layout.addWidget(self.fee_widget, 4, 1, 1, 3)

        self.note_label = QLabel(ChainActionOperation)
        self.note_label.setObjectName(u"note_label")
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.note_label, 5, 0, 1, 1)

        self.note = QLineEdit(ChainActionOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 5, 1, 1, 9)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 6, 0, 1, 1)

#if QT_CONFIG(shortcut)
        self.date_label.setBuddy(self.timestamp)
        self.type_label.setBuddy(self.type)
        self.tx_hash_label.setBuddy(self.number)
        self.account_label.setBuddy(self.account_widget)
        self.symbol_label.setBuddy(self.symbol_widget)
        self.fee_label.setBuddy(self.fee_widget)
        self.note_label.setBuddy(self.note)
#endif // QT_CONFIG(shortcut)
        QWidget.setTabOrder(self.timestamp, self.type)
        QWidget.setTabOrder(self.type, self.number)
        QWidget.setTabOrder(self.number, self.account_widget)
        QWidget.setTabOrder(self.account_widget, self.symbol_widget)
        QWidget.setTabOrder(self.symbol_widget, self.fee_widget)
        QWidget.setTabOrder(self.fee_widget, self.note)
        QWidget.setTabOrder(self.note, self.commit_button)
        QWidget.setTabOrder(self.commit_button, self.revert_button)

        self.retranslateUi(ChainActionOperation)

        QMetaObject.connectSlotsByName(ChainActionOperation)
    # setupUi

    def retranslateUi(self, ChainActionOperation):
        ChainActionOperation.setWindowTitle(QCoreApplication.translate("ChainActionOperation", u"Form", None))
        self.main_label.setText(QCoreApplication.translate("ChainActionOperation", u"Action", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("ChainActionOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("ChainActionOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.date_label.setText(QCoreApplication.translate("ChainActionOperation", u"D&ate/Time", None))
        self.timestamp.setDisplayFormat(QCoreApplication.translate("ChainActionOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.type_label.setText(QCoreApplication.translate("ChainActionOperation", u"E&vent", None))
        self.tx_hash_label.setText(QCoreApplication.translate("ChainActionOperation", u"T&x hash", None))
        self.account_label.setText(QCoreApplication.translate("ChainActionOperation", u"A&ccount", None))
        self.symbol_label.setText(QCoreApplication.translate("ChainActionOperation", u"Su&bject", None))
#if QT_CONFIG(tooltip)
        self.symbol_label.setToolTip(QCoreApplication.translate("ChainActionOperation", u"What the event was about - the token approved, for example. Left empty when it is not an asset JAL knows.", None))
#endif // QT_CONFIG(tooltip)
        self.fee_label.setText(QCoreApplication.translate("ChainActionOperation", u"C&ost", None))
        self.note_label.setText(QCoreApplication.translate("ChainActionOperation", u"&Note", None))
    # retranslateUi

