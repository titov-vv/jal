# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'select_tag_dlg.ui'
##
## Created by: Qt User Interface Compiler version 6.4.2
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
    QLabel, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

from jal.widgets.reference_selector import TagSelector

class Ui_SelectTagDlg(object):
    def setupUi(self, SelectTagDlg):
        if not SelectTagDlg.objectName():
            SelectTagDlg.setObjectName(u"SelectTagDlg")
        SelectTagDlg.resize(400, 97)
        self.verticalLayout = QVBoxLayout(SelectTagDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.DescriptionLbl = QLabel(SelectTagDlg)
        self.DescriptionLbl.setObjectName(u"DescriptionLbl")

        self.verticalLayout.addWidget(self.DescriptionLbl)

        self.TagWidget = TagSelector(SelectTagDlg)
        self.TagWidget.setObjectName(u"TagWidget")

        self.verticalLayout.addWidget(self.TagWidget)

        self.buttonBox = QDialogButtonBox(SelectTagDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)


        self.retranslateUi(SelectTagDlg)
        self.buttonBox.accepted.connect(SelectTagDlg.close)

        QMetaObject.connectSlotsByName(SelectTagDlg)
    # setupUi

    def retranslateUi(self, SelectTagDlg):
        SelectTagDlg.setWindowTitle(QCoreApplication.translate("SelectTagDlg", u"Please select tag", None))
        self.DescriptionLbl.setText(QCoreApplication.translate("SelectTagDlg", u"TextLabel", None))
    # retranslateUi

