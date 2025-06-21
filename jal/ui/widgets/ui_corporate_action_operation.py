# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'corporate_action_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QDateTimeEdit, QGridLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpacerItem, QWidget)

from jal.widgets.custom.tableview_with_footer import TableViewWithFooter
from jal.widgets.reference_selector import (AccountSelector, AssetSelector)

class Ui_CorporateActionOperation(object):
    def setupUi(self, CorporateActionOperation):
        if not CorporateActionOperation.objectName():
            CorporateActionOperation.setObjectName(u"CorporateActionOperation")
        CorporateActionOperation.resize(969, 244)
        self.layout = QGridLayout(CorporateActionOperation)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.add_button = QPushButton(CorporateActionOperation)
        self.add_button.setObjectName(u"add_button")

        self.layout.addWidget(self.add_button, 2, 7, 1, 1)

        self.asset_label = QLabel(CorporateActionOperation)
        self.asset_label.setObjectName(u"asset_label")

        self.layout.addWidget(self.asset_label, 3, 3, 1, 1)

        self.qty_edit = QLineEdit(CorporateActionOperation)
        self.qty_edit.setObjectName(u"qty_edit")

        self.layout.addWidget(self.qty_edit, 4, 4, 1, 1)

        self.account_label = QLabel(CorporateActionOperation)
        self.account_label.setObjectName(u"account_label")

        self.layout.addWidget(self.account_label, 2, 3, 1, 1)

        self.note_label = QLabel(CorporateActionOperation)
        self.note_label.setObjectName(u"note_label")

        self.layout.addWidget(self.note_label, 5, 0, 1, 1)

        self.commit_button = QPushButton(CorporateActionOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 7, 1, 1)

        self.qty_label = QLabel(CorporateActionOperation)
        self.qty_label.setObjectName(u"qty_label")

        self.layout.addWidget(self.qty_label, 4, 3, 1, 1)

        self.main_label = QLabel(CorporateActionOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 3)

        self.date_label = QLabel(CorporateActionOperation)
        self.date_label.setObjectName(u"date_label")

        self.layout.addWidget(self.date_label, 2, 0, 1, 1)

        self.timestamp_editor = QDateTimeEdit(CorporateActionOperation)
        self.timestamp_editor.setObjectName(u"timestamp_editor")
        self.timestamp_editor.setCalendarPopup(True)
        self.timestamp_editor.setTimeSpec(Qt.UTC)

        self.layout.addWidget(self.timestamp_editor, 2, 2, 1, 1)

        self.arrow = QLabel(CorporateActionOperation)
        self.arrow.setObjectName(u"arrow")

        self.layout.addWidget(self.arrow, 3, 5, 2, 1)

        self.type_label = QLabel(CorporateActionOperation)
        self.type_label.setObjectName(u"type_label")

        self.layout.addWidget(self.type_label, 3, 0, 1, 1)

        self.asset_widget = AssetSelector(CorporateActionOperation)
        self.asset_widget.setObjectName(u"asset_widget")

        self.layout.addWidget(self.asset_widget, 3, 4, 1, 1)

        self.account_widget = AccountSelector(CorporateActionOperation)
        self.account_widget.setObjectName(u"account_widget")

        self.layout.addWidget(self.account_widget, 2, 4, 1, 1)

        self.number = QLineEdit(CorporateActionOperation)
        self.number.setObjectName(u"number")

        self.layout.addWidget(self.number, 4, 2, 1, 1)

        self.type = QComboBox(CorporateActionOperation)
        self.type.setObjectName(u"type")

        self.layout.addWidget(self.type, 3, 2, 1, 1)

        self.revert_button = QPushButton(CorporateActionOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 8, 1, 1)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.layout.addItem(self.vertical_spacer, 6, 0, 1, 1)

        self.note = QLineEdit(CorporateActionOperation)
        self.note.setObjectName(u"note")

        self.layout.addWidget(self.note, 5, 2, 1, 3)

        self.del_button = QPushButton(CorporateActionOperation)
        self.del_button.setObjectName(u"del_button")

        self.layout.addWidget(self.del_button, 2, 8, 1, 1)

        self.number_label = QLabel(CorporateActionOperation)
        self.number_label.setObjectName(u"number_label")

        self.layout.addWidget(self.number_label, 4, 0, 1, 1)

        self.results_table = TableViewWithFooter(CorporateActionOperation)
        self.results_table.setObjectName(u"results_table")
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setMinimumSectionSize(20)
        self.results_table.verticalHeader().setDefaultSectionSize(20)

        self.layout.addWidget(self.results_table, 3, 6, 3, 3)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout.addItem(self.horizontalSpacer, 2, 6, 1, 1)


        self.retranslateUi(CorporateActionOperation)

        QMetaObject.connectSlotsByName(CorporateActionOperation)
    # setupUi

    def retranslateUi(self, CorporateActionOperation):
        CorporateActionOperation.setWindowTitle(QCoreApplication.translate("CorporateActionOperation", u"Form", None))
#if QT_CONFIG(tooltip)
        self.add_button.setToolTip(QCoreApplication.translate("CorporateActionOperation", u"Add asset", None))
#endif // QT_CONFIG(tooltip)
        self.add_button.setText("")
        self.asset_label.setText(QCoreApplication.translate("CorporateActionOperation", u"Asset", None))
        self.account_label.setText(QCoreApplication.translate("CorporateActionOperation", u"Account", None))
        self.note_label.setText(QCoreApplication.translate("CorporateActionOperation", u"Note", None))
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("CorporateActionOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
        self.qty_label.setText(QCoreApplication.translate("CorporateActionOperation", u"Qty", None))
        self.main_label.setText(QCoreApplication.translate("CorporateActionOperation", u"Corporate Action", None))
        self.date_label.setText(QCoreApplication.translate("CorporateActionOperation", u"Date/Time", None))
        self.timestamp_editor.setDisplayFormat(QCoreApplication.translate("CorporateActionOperation", u"dd/MM/yyyy hh:mm:ss", None))
        self.arrow.setText(QCoreApplication.translate("CorporateActionOperation", u" - ", None))
        self.type_label.setText(QCoreApplication.translate("CorporateActionOperation", u"Type", None))
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("CorporateActionOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
#if QT_CONFIG(tooltip)
        self.del_button.setToolTip(QCoreApplication.translate("CorporateActionOperation", u"Remove asset", None))
#endif // QT_CONFIG(tooltip)
        self.del_button.setText("")
        self.number_label.setText(QCoreApplication.translate("CorporateActionOperation", u"#", None))
    # retranslateUi

