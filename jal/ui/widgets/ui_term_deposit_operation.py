# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'term_deposit_operation.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
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
    QHeaderView, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpacerItem, QWidget)

from jal.widgets.custom.tableview_with_footer import TableViewWithFooter
from jal.widgets.reference_selector import (AccountSelector, AssetSelector)

class Ui_TermDepositOperation(object):
    def setupUi(self, TermDepositOperation):
        if not TermDepositOperation.objectName():
            TermDepositOperation.setObjectName(u"TermDepositOperation")
        TermDepositOperation.resize(969, 244)
        self.layout = QGridLayout(TermDepositOperation)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.add_button = QPushButton(TermDepositOperation)
        self.add_button.setObjectName(u"add_button")

        self.layout.addWidget(self.add_button, 2, 7, 1, 1)

        self.asset_label = QLabel(TermDepositOperation)
        self.asset_label.setObjectName(u"asset_label")

        self.layout.addWidget(self.asset_label, 3, 3, 1, 1)

        self.qty_edit = QLineEdit(TermDepositOperation)
        self.qty_edit.setObjectName(u"qty_edit")

        self.layout.addWidget(self.qty_edit, 4, 4, 1, 1)

        self.account_label = QLabel(TermDepositOperation)
        self.account_label.setObjectName(u"account_label")

        self.layout.addWidget(self.account_label, 2, 3, 1, 1)

        self.note_label = QLabel(TermDepositOperation)
        self.note_label.setObjectName(u"note_label")

        self.layout.addWidget(self.note_label, 5, 0, 1, 1)

        self.commit_button = QPushButton(TermDepositOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 7, 1, 1)

        self.qty_label = QLabel(TermDepositOperation)
        self.qty_label.setObjectName(u"qty_label")

        self.layout.addWidget(self.qty_label, 4, 3, 1, 1)

        self.main_label = QLabel(TermDepositOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 3)

        self.date_label = QLabel(TermDepositOperation)
        self.date_label.setObjectName(u"date_label")

        self.layout.addWidget(self.date_label, 2, 0, 1, 1)

        self.timestamp_editor = QDateTimeEdit(TermDepositOperation)
        self.timestamp_editor.setObjectName(u"timestamp_editor")
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)

        self.layout.addWidget(self.timestamp_editor, 2, 2, 1, 1)

        self.arrow = QLabel(TermDepositOperation)
        self.arrow.setObjectName(u"arrow")

        self.layout.addWidget(self.arrow, 3, 5, 2, 1)

        self.type_label = QLabel(TermDepositOperation)
        self.type_label.setObjectName(u"type_label")

        self.layout.addWidget(self.type_label, 3, 0, 1, 1)

        self.asset_widget = AssetSelector(TermDepositOperation)
        self.asset_widget.setObjectName(u"asset_widget")

        self.layout.addWidget(self.asset_widget, 3, 4, 1, 1)

        self.account_widget = AccountSelector(TermDepositOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 2, 4, 1, 1)

        self.number = QLineEdit(TermDepositOperation)
        self.number.setObjectName(u"number")

        self.layout.addWidget(self.number, 4, 2, 1, 1)

        self.type = QComboBox(TermDepositOperation)
        self.type.setObjectName(u"type")

        self.layout.addWidget(self.type, 3, 2, 1, 1)

        self.revert_button = QPushButton(TermDepositOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 8, 1, 1)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.layout.addItem(self.vertical_spacer, 6, 0, 1, 1)

        self.note = QLineEdit(TermDepositOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 5, 2, 1, 3)

        self.del_button = QPushButton(TermDepositOperation)
        self.del_button.setObjectName(u"del_button")

        self.layout.addWidget(self.del_button, 2, 8, 1, 1)

        self.number_label = QLabel(TermDepositOperation)
        self.number_label.setObjectName(u"number_label")

        self.layout.addWidget(self.number_label, 4, 0, 1, 1)

        self.results_table = TableViewWithFooter(TermDepositOperation)
        self.results_table.setObjectName(u"results_table")
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setMinimumSectionSize(20)
        self.results_table.verticalHeader().setDefaultSectionSize(20)

        self.layout.addWidget(self.results_table, 3, 6, 3, 3)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout.addItem(self.horizontalSpacer, 2, 6, 1, 1)


        self.retranslateUi(TermDepositOperation)

        QMetaObject.connectSlotsByName(TermDepositOperation)
    # setupUi

    def retranslateUi(self, TermDepositOperation):
        TermDepositOperation.setWindowTitle(QCoreApplication.translate("TermDepositOperation", u"Form", None))
#if QT_CONFIG(tooltip)
        self.add_button.setToolTip(QCoreApplication.translate("TermDepositOperation", u"Add asset", None))
#endif // QT_CONFIG(tooltip)
        self.add_button.setText("")
        self.asset_label.setText(QCoreApplication.translate("TermDepositOperation", u"Asset", None))
        self.account_label.setText(QCoreApplication.translate("TermDepositOperation", u"Account", None))
        self.note_label.setText(QCoreApplication.translate("TermDepositOperation", u"Note", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("TermDepositOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
        self.qty_label.setText(QCoreApplication.translate("TermDepositOperation", u"Qty", None))
        self.main_label.setText(QCoreApplication.translate("TermDepositOperation", u"Term Deposit", None))
        self.date_label.setText(QCoreApplication.translate("TermDepositOperation", u"Date/Time", None))
        self.timestamp_editor.setDisplayFormat(QCoreApplication.translate("TermDepositOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.arrow.setText(QCoreApplication.translate("TermDepositOperation", u" - ", None))
        self.type_label.setText(QCoreApplication.translate("TermDepositOperation", u"Type", None))
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("TermDepositOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
#if QT_CONFIG(tooltip)
        self.del_button.setToolTip(QCoreApplication.translate("TermDepositOperation", u"Remove asset", None))
#endif // QT_CONFIG(tooltip)
        self.del_button.setText("")
        self.number_label.setText(QCoreApplication.translate("TermDepositOperation", u"#", None))
    # retranslateUi

