# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'select_reference_dlg.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QFrame, QLabel, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_SelectReferenceDlg(object):
    def setupUi(self, SelectReferenceDlg):
        if not SelectReferenceDlg.objectName():
            SelectReferenceDlg.setObjectName(u"SelectReferenceDlg")
        SelectReferenceDlg.resize(400, 97)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(SelectReferenceDlg.sizePolicy().hasHeightForWidth())
        SelectReferenceDlg.setSizePolicy(sizePolicy)
        SelectReferenceDlg.setWindowTitle(u"Title")
        self.WindowLayout = QVBoxLayout(SelectReferenceDlg)
        self.WindowLayout.setObjectName(u"WindowLayout")
        self.DescriptionLabel = QLabel(SelectReferenceDlg)
        self.DescriptionLabel.setObjectName(u"DescriptionLabel")
        self.DescriptionLabel.setText(u"Description")

        self.WindowLayout.addWidget(self.DescriptionLabel)

        self.SelectorFrame = QFrame(SelectReferenceDlg)
        self.SelectorFrame.setObjectName(u"SelectorFrame")
        self.SelectorFrame.setFrameShape(QFrame.NoFrame)
        self.SelectorFrame.setFrameShadow(QFrame.Plain)
        self.SelectorFrame.setLineWidth(0)
        self.SelectorFrame.setMidLineWidth(0)
        self.FrameLayout = QVBoxLayout(self.SelectorFrame)
        self.FrameLayout.setSpacing(0)
        self.FrameLayout.setObjectName(u"FrameLayout")
        self.FrameLayout.setContentsMargins(0, 0, 0, 0)

        self.WindowLayout.addWidget(self.SelectorFrame)

        self.buttonBox = QDialogButtonBox(SelectReferenceDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.WindowLayout.addWidget(self.buttonBox)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.WindowLayout.addItem(self.verticalSpacer)


        self.retranslateUi(SelectReferenceDlg)
        self.buttonBox.accepted.connect(SelectReferenceDlg.close)
        self.buttonBox.rejected.connect(SelectReferenceDlg.reject)

        QMetaObject.connectSlotsByName(SelectReferenceDlg)
    # setupUi

    def retranslateUi(self, SelectReferenceDlg):
        pass
    # retranslateUi

