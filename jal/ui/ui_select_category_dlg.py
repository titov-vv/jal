# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'select_category_dlg.ui'
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

from jal.widgets.reference_selector import CategorySelector

class Ui_SelectCategoryDlg(object):
    def setupUi(self, SelectCategoryDlg):
        if not SelectCategoryDlg.objectName():
            SelectCategoryDlg.setObjectName(u"SelectCategoryDlg")
        SelectCategoryDlg.resize(400, 97)
        self.verticalLayout = QVBoxLayout(SelectCategoryDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.DescriptionLbl = QLabel(SelectCategoryDlg)
        self.DescriptionLbl.setObjectName(u"DescriptionLbl")

        self.verticalLayout.addWidget(self.DescriptionLbl)

        self.CategoryWidget = CategorySelector(SelectCategoryDlg)
        self.CategoryWidget.setObjectName(u"CategoryWidget")

        self.verticalLayout.addWidget(self.CategoryWidget)

        self.buttonBox = QDialogButtonBox(SelectCategoryDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)


        self.retranslateUi(SelectCategoryDlg)
        self.buttonBox.accepted.connect(SelectCategoryDlg.close)

        QMetaObject.connectSlotsByName(SelectCategoryDlg)
    # setupUi

    def retranslateUi(self, SelectCategoryDlg):
        SelectCategoryDlg.setWindowTitle(QCoreApplication.translate("SelectCategoryDlg", u"Please select category", None))
        self.DescriptionLbl.setText(QCoreApplication.translate("SelectCategoryDlg", u"TextLabel", None))
    # retranslateUi

