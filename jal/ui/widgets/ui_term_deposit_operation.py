# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'term_deposit_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QGridLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QTableView, QWidget)

from jal.widgets.reference_selector import AccountSelector

class Ui_TermDepositOperation(object):
    def setupUi(self, TermDepositOperation):
        if not TermDepositOperation.objectName():
            TermDepositOperation.setObjectName(u"TermDepositOperation")
        TermDepositOperation.resize(969, 260)
        self.layout = QGridLayout(TermDepositOperation)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.account_label = QLabel(TermDepositOperation)
        self.account_label.setObjectName(u"account_label")

        self.layout.addWidget(self.account_label, 2, 0, 1, 1)

        self.note = QLineEdit(TermDepositOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 3, 1, 1, 5)

        self.note_label = QLabel(TermDepositOperation)
        self.note_label.setObjectName(u"note_label")

        self.layout.addWidget(self.note_label, 3, 0, 1, 1)

        self.add_button = QPushButton(TermDepositOperation)
        self.add_button.setObjectName(u"add_button")

        self.layout.addWidget(self.add_button, 4, 4, 1, 1)

        self.del_button = QPushButton(TermDepositOperation)
        self.del_button.setObjectName(u"del_button")

        self.layout.addWidget(self.del_button, 4, 5, 1, 1)

        self.revert_button = QPushButton(TermDepositOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 9, 1, 1)

        self.main_label = QLabel(TermDepositOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 2)

        self.account_widget = AccountSelector(TermDepositOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 2, 1, 1, 2)

        self.actions_table = QTableView(TermDepositOperation)
        self.actions_table.setObjectName(u"actions_table")
        self.actions_table.setAlternatingRowColors(True)
        self.actions_table.verticalHeader().setVisible(False)
        self.actions_table.verticalHeader().setMinimumSectionSize(20)
        self.actions_table.verticalHeader().setDefaultSectionSize(20)

        self.layout.addWidget(self.actions_table, 5, 0, 1, 6)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontalSpacer, 3, 6, 1, 1)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 6, 0, 1, 1)

        self.commit_button = QPushButton(TermDepositOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 8, 1, 1)

        self.details_label = QLabel(TermDepositOperation)
        self.details_label.setObjectName(u"details_label")

        self.layout.addWidget(self.details_label, 4, 0, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontalSpacer_2, 4, 3, 1, 1)


        self.retranslateUi(TermDepositOperation)

        QMetaObject.connectSlotsByName(TermDepositOperation)
    # setupUi

    def retranslateUi(self, TermDepositOperation):
        TermDepositOperation.setWindowTitle(QCoreApplication.translate("TermDepositOperation", u"Form", None))
        self.account_label.setText(QCoreApplication.translate("TermDepositOperation", u"Account", None))
        self.note_label.setText(QCoreApplication.translate("TermDepositOperation", u"Note", None))
#if QT_CONFIG(tooltip)
        self.add_button.setToolTip(QCoreApplication.translate("TermDepositOperation", u"Add activity", None))
#endif // QT_CONFIG(tooltip)
        self.add_button.setText("")
#if QT_CONFIG(tooltip)
        self.del_button.setToolTip(QCoreApplication.translate("TermDepositOperation", u"Remove activity", None))
#endif // QT_CONFIG(tooltip)
        self.del_button.setText("")
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("TermDepositOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
        self.main_label.setText(QCoreApplication.translate("TermDepositOperation", u"Term Deposit", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("TermDepositOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
        self.details_label.setText(QCoreApplication.translate("TermDepositOperation", u"Deposit activity", None))
    # retranslateUi

