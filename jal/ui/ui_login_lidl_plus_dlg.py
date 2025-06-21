# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login_lidl_plus_dlg.ui'
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
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_LoginLidlPlusDialog(object):
    def setupUi(self, LoginLidlPlusDialog):
        if not LoginLidlPlusDialog.objectName():
            LoginLidlPlusDialog.setObjectName(u"LoginLidlPlusDialog")
        LoginLidlPlusDialog.resize(400, 500)
        self.verticalLayout_3 = QVBoxLayout(LoginLidlPlusDialog)
        self.verticalLayout_3.setSpacing(6)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(2, 2, 2, 2)
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
        self.ButtonFrame.setFrameShape(QFrame.NoFrame)
        self.ButtonFrame.setFrameShadow(QFrame.Plain)
        self.verticalLayout_6 = QVBoxLayout(self.ButtonFrame)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 6)
        self.SplitLine = QFrame(self.ButtonFrame)
        self.SplitLine.setObjectName(u"SplitLine")
        self.SplitLine.setFrameShape(QFrame.Shape.HLine)
        self.SplitLine.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout_6.addWidget(self.SplitLine)

        self.CloseBtn = QPushButton(self.ButtonFrame)
        self.CloseBtn.setObjectName(u"CloseBtn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.CloseBtn.sizePolicy().hasHeightForWidth())
        self.CloseBtn.setSizePolicy(sizePolicy1)

        self.verticalLayout_6.addWidget(self.CloseBtn, 0, Qt.AlignHCenter)


        self.verticalLayout_3.addWidget(self.ButtonFrame)


        self.retranslateUi(LoginLidlPlusDialog)
        self.CloseBtn.clicked.connect(LoginLidlPlusDialog.close)

        QMetaObject.connectSlotsByName(LoginLidlPlusDialog)
    # setupUi

    def retranslateUi(self, LoginLidlPlusDialog):
        LoginLidlPlusDialog.setWindowTitle(QCoreApplication.translate("LoginLidlPlusDialog", u"Authorization Lidl Plus", None))
        self.CloseBtn.setText(QCoreApplication.translate("LoginLidlPlusDialog", u"Close", None))
    # retranslateUi

