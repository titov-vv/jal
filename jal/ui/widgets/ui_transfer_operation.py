# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'transfer_operation.ui'
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
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QWidget)

class Ui_TransferOperation(object):
    def setupUi(self, TransferOperation):
        if not TransferOperation.objectName():
            TransferOperation.setObjectName(u"TransferOperation")
        TransferOperation.resize(550, 189)
        self.layout = QGridLayout(TransferOperation)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.revert_button = QPushButton(TransferOperation)
        self.revert_button.setObjectName(u"revert_button")
        self.revert_button.setEnabled(False)
        self.revert_button.setAcceptDrops(False)

        self.layout.addWidget(self.revert_button, 0, 3, 1, 1)

        self.commit_button = QPushButton(TransferOperation)
        self.commit_button.setObjectName(u"commit_button")
        self.commit_button.setEnabled(False)

        self.layout.addWidget(self.commit_button, 0, 2, 1, 1)

        self.horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout.addItem(self.horizontal_spacer, 0, 1, 1, 1)

        self.main_label = QLabel(TransferOperation)
        self.main_label.setObjectName(u"main_label")
        font = QFont()
        font.setBold(True)
        self.main_label.setFont(font)

        self.layout.addWidget(self.main_label, 0, 0, 1, 1)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.layout.addItem(self.vertical_spacer, 1, 0, 1, 1)


        self.retranslateUi(TransferOperation)

        QMetaObject.connectSlotsByName(TransferOperation)
    # setupUi

    def retranslateUi(self, TransferOperation):
        TransferOperation.setWindowTitle(QCoreApplication.translate("TransferOperation", u"Form", None))
#if QT_CONFIG(tooltip)
        self.revert_button.setToolTip(QCoreApplication.translate("TransferOperation", u"Cancel changes", None))
#endif // QT_CONFIG(tooltip)
        self.revert_button.setText("")
#if QT_CONFIG(tooltip)
        self.commit_button.setToolTip(QCoreApplication.translate("TransferOperation", u"Commit changes", None))
#endif // QT_CONFIG(tooltip)
        self.commit_button.setText("")
        self.main_label.setText(QCoreApplication.translate("TransferOperation", u"Transfer", None))
    # retranslateUi

