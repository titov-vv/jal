# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'income_spending_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QDateTimeEdit, QGridLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSizePolicy,
    QSpacerItem, QWidget)

from jal.widgets.account_select import (AccountCurrencyLabel, OptionalCurrencyComboBox)
from jal.widgets.custom.tableview_with_footer import TableViewWithFooter
from jal.widgets.reference_selector import (AccountSelector, PeerSelector)

class Ui_IncomeSpendingOperation(object):
    def setupUi(self, IncomeSpendingOperation):
        if not IncomeSpendingOperation.objectName():
            IncomeSpendingOperation.setObjectName(u"IncomeSpendingOperation")
        IncomeSpendingOperation.resize(968, 231)
        self.layout = QGridLayout(IncomeSpendingOperation)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.note = QLineEdit(IncomeSpendingOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 2, 7, 1, 1)

        self.account_label = QLabel(IncomeSpendingOperation)
        self.account_label.setObjectName(u"account_label")

        self.layout.addWidget(self.account_label, 1, 4, 1, 1)

        self.date_label = QLabel(IncomeSpendingOperation)
        self.date_label.setObjectName(u"date_label")

        self.layout.addWidget(self.date_label, 1, 0, 1, 1)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.layout.addItem(self.vertical_spacer, 4, 0, 1, 1)

        self.add_button = QPushButton(IncomeSpendingOperation)
        self.add_button.setObjectName(u"add_button")

        self.layout.addWidget(self.add_button, 2, 1, 1, 1)

        self.del_button = QPushButton(IncomeSpendingOperation)
        self.del_button.setObjectName(u"del_button")

        self.layout.addWidget(self.del_button, 2, 3, 1, 1)

        self.copy_button = QPushButton(IncomeSpendingOperation)
        self.copy_button.setObjectName(u"copy_button")

        self.layout.addWidget(self.copy_button, 2, 2, 1, 1)

        self.account_widget = AccountSelector(IncomeSpendingOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 1, 5, 1, 1)

        self.note_label = QLabel(IncomeSpendingOperation)
        self.note_label.setObjectName(u"note_label")

        self.layout.addWidget(self.note_label, 2, 6, 1, 1)

        self.commit_button = QPushButton(IncomeSpendingOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 9, 1, 1)

        self.peer_label = QLabel(IncomeSpendingOperation)
        self.peer_label.setObjectName(u"peer_label")

        self.layout.addWidget(self.peer_label, 2, 4, 1, 1)

        self.timestamp_editor = QDateTimeEdit(IncomeSpendingOperation)
        self.timestamp_editor.setObjectName(u"timestamp_editor")
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)

        self.layout.addWidget(self.timestamp_editor, 1, 1, 1, 3)

        self.main_label = QLabel(IncomeSpendingOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.details_label = QLabel(IncomeSpendingOperation)
        self.details_label.setObjectName(u"details_label")

        self.layout.addWidget(self.details_label, 2, 0, 1, 1)

        self.revert_button = QPushButton(IncomeSpendingOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 10, 1, 1)

        self.peer_widget = PeerSelector(IncomeSpendingOperation)
        self.peer_widget.setObjectName(u"peer_widget")

        self.layout.addWidget(self.peer_widget, 2, 5, 1, 1)

        self.details_table = TableViewWithFooter(IncomeSpendingOperation)
        self.details_table.setObjectName(u"details_table")
        self.details_table.setAlternatingRowColors(True)
        self.details_table.verticalHeader().setVisible(False)
        self.details_table.verticalHeader().setMinimumSectionSize(20)
        self.details_table.verticalHeader().setDefaultSectionSize(20)

        self.layout.addWidget(self.details_table, 3, 0, 1, 11)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 2, 8, 1, 1)

        self.a_currency = OptionalCurrencyComboBox(IncomeSpendingOperation)
        self.a_currency.setObjectName(u"a_currency")

        self.layout.addWidget(self.a_currency, 1, 7, 1, 1)

        self.currency = AccountCurrencyLabel(IncomeSpendingOperation)
        self.currency.setObjectName(u"currency")

        self.layout.addWidget(self.currency, 1, 6, 1, 1)


        self.retranslateUi(IncomeSpendingOperation)

        QMetaObject.connectSlotsByName(IncomeSpendingOperation)
    # setupUi

    def retranslateUi(self, IncomeSpendingOperation):
        IncomeSpendingOperation.setWindowTitle(QCoreApplication.translate("IncomeSpendingOperation", u"Form", None))
        self.account_label.setText(QCoreApplication.translate("IncomeSpendingOperation", u"Account", None))
        self.date_label.setText(QCoreApplication.translate("IncomeSpendingOperation", u"Date/Time", None))
#if QT_CONFIG(tooltip)
        self.add_button.setToolTip(QCoreApplication.translate("IncomeSpendingOperation", u"Add detail", None))
#endif // QT_CONFIG(tooltip)
        self.add_button.setText("")
#if QT_CONFIG(tooltip)
        self.del_button.setToolTip(QCoreApplication.translate("IncomeSpendingOperation", u"Remove detail", None))
#endif // QT_CONFIG(tooltip)
        self.del_button.setText("")
#if QT_CONFIG(tooltip)
        self.copy_button.setToolTip(QCoreApplication.translate("IncomeSpendingOperation", u"Copy detail", None))
#endif // QT_CONFIG(tooltip)
        self.copy_button.setText("")
        self.note_label.setText(QCoreApplication.translate("IncomeSpendingOperation", u"Note", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("IncomeSpendingOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
        self.peer_label.setText(QCoreApplication.translate("IncomeSpendingOperation", u"Peer", None))
        self.timestamp_editor.setDisplayFormat(QCoreApplication.translate("IncomeSpendingOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.main_label.setText(QCoreApplication.translate("IncomeSpendingOperation", u"Income / Spending", None))
        self.details_label.setText(QCoreApplication.translate("IncomeSpendingOperation", u"Details", None))
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("IncomeSpendingOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.currency.setText(QCoreApplication.translate("IncomeSpendingOperation", u"CUR", None))
    # retranslateUi

