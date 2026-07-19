# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'preferences_dlg.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QGridLayout, QListWidget, QListWidgetItem, QSizePolicy,
    QStackedWidget, QWidget)

class Ui_PreferencesDlg(object):
    def setupUi(self, PreferencesDlg):
        if not PreferencesDlg.objectName():
            PreferencesDlg.setObjectName(u"PreferencesDlg")
        PreferencesDlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        PreferencesDlg.resize(640, 420)
        font = QFont()
        font.setFamilies([u"DejaVu Sans"])
        PreferencesDlg.setFont(font)
        self.gridLayout = QGridLayout(PreferencesDlg)
        self.gridLayout.setObjectName(u"gridLayout")
        self.PagesList = QListWidget(PreferencesDlg)
        self.PagesList.setObjectName(u"PagesList")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.PagesList.sizePolicy().hasHeightForWidth())
        self.PagesList.setSizePolicy(sizePolicy)
        self.PagesList.setMaximumSize(QSize(180, 16777215))

        self.gridLayout.addWidget(self.PagesList, 0, 0, 1, 1)

        self.PagesStack = QStackedWidget(PreferencesDlg)
        self.PagesStack.setObjectName(u"PagesStack")

        self.gridLayout.addWidget(self.PagesStack, 0, 1, 1, 1)

        self.ButtonBox = QDialogButtonBox(PreferencesDlg)
        self.ButtonBox.setObjectName(u"ButtonBox")
        self.ButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.ButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.gridLayout.addWidget(self.ButtonBox, 1, 0, 1, 2)


        self.retranslateUi(PreferencesDlg)
        self.ButtonBox.accepted.connect(PreferencesDlg.accept)
        self.ButtonBox.rejected.connect(PreferencesDlg.reject)

        QMetaObject.connectSlotsByName(PreferencesDlg)
    # setupUi

    def retranslateUi(self, PreferencesDlg):
        PreferencesDlg.setWindowTitle(QCoreApplication.translate("PreferencesDlg", u"Preferences", None))
    # retranslateUi

