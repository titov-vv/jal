# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login_lidl_plus_dlg.ui'
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
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QFrame, QSizePolicy, QVBoxLayout, QWidget)

class Ui_LoginLidlPlusDialog(object):
    def setupUi(self, LoginLidlPlusDialog):
        if not LoginLidlPlusDialog.objectName():
            LoginLidlPlusDialog.setObjectName(u"LoginLidlPlusDialog")
        LoginLidlPlusDialog.resize(400, 500)
        self.verticalLayout_3 = QVBoxLayout(LoginLidlPlusDialog)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.LidlPlusWebView = QWebEngineView(LoginLidlPlusDialog)
        self.LidlPlusWebView.setObjectName(u"LidlPlusWebView")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.LidlPlusWebView.sizePolicy().hasHeightForWidth())
        self.LidlPlusWebView.setSizePolicy(sizePolicy)
        self.LidlPlusWebView.setUrl(QUrl(u"about:blank"))

        self.verticalLayout_3.addWidget(self.LidlPlusWebView)

        self.ButtonFrame = QFrame(LoginLidlPlusDialog)
        self.ButtonFrame.setObjectName(u"ButtonFrame")
        self.ButtonFrame.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalLayout_6 = QVBoxLayout(self.ButtonFrame)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 6)
        self.SplitLine = QFrame(self.ButtonFrame)
        self.SplitLine.setObjectName(u"SplitLine")
        self.SplitLine.setFrameShape(QFrame.Shape.HLine)
        self.SplitLine.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_6.addWidget(self.SplitLine)

        self.DialogButtonBox = QDialogButtonBox(self.ButtonFrame)
        self.DialogButtonBox.setObjectName(u"DialogButtonBox")
        self.DialogButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.DialogButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        self.verticalLayout_6.addWidget(self.DialogButtonBox)


        self.verticalLayout_3.addWidget(self.ButtonFrame)

        QWidget.setTabOrder(self.LidlPlusWebView, self.DialogButtonBox)

        self.retranslateUi(LoginLidlPlusDialog)
        self.DialogButtonBox.rejected.connect(LoginLidlPlusDialog.reject)

        QMetaObject.connectSlotsByName(LoginLidlPlusDialog)
    # setupUi

    def retranslateUi(self, LoginLidlPlusDialog):
        LoginLidlPlusDialog.setWindowTitle(QCoreApplication.translate("LoginLidlPlusDialog", u"Authorization Lidl Plus", None))
    # retranslateUi

