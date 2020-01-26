# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'category_choice_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.14.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QMetaObject, QObject, QPoint,
    QRect, QSize, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QFont,
    QFontDatabase, QIcon, QLinearGradient, QPalette, QPainter, QPixmap,
    QRadialGradient)
from PySide2.QtWidgets import *

class Ui_CategoryChoiceDlg(object):
    def setupUi(self, CategoryChoiceDlg):
        if CategoryChoiceDlg.objectName():
            CategoryChoiceDlg.setObjectName(u"CategoryChoiceDlg")
        CategoryChoiceDlg.resize(831, 300)
        self.verticalLayout = QVBoxLayout(CategoryChoiceDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.SearchFrame = QFrame(CategoryChoiceDlg)
        self.SearchFrame.setObjectName(u"SearchFrame")
        self.SearchFrame.setFrameShape(QFrame.NoFrame)
        self.SearchFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.SearchFrame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.SearchLbl = QLabel(self.SearchFrame)
        self.SearchLbl.setObjectName(u"SearchLbl")

        self.horizontalLayout.addWidget(self.SearchLbl)

        self.SearchString = QLineEdit(self.SearchFrame)
        self.SearchString.setObjectName(u"SearchString")

        self.horizontalLayout.addWidget(self.SearchString)


        self.verticalLayout.addWidget(self.SearchFrame)

        self.EditFrame = QFrame(CategoryChoiceDlg)
        self.EditFrame.setObjectName(u"EditFrame")
        self.EditFrame.setFrameShape(QFrame.NoFrame)
        self.EditFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.EditFrame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.UpBtn = QPushButton(self.EditFrame)
        self.UpBtn.setObjectName(u"UpBtn")

        self.horizontalLayout_2.addWidget(self.UpBtn)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.AddCategoryBtn = QPushButton(self.EditFrame)
        self.AddCategoryBtn.setObjectName(u"AddCategoryBtn")

        self.horizontalLayout_2.addWidget(self.AddCategoryBtn)

        self.RemoveCategoryBtn = QPushButton(self.EditFrame)
        self.RemoveCategoryBtn.setObjectName(u"RemoveCategoryBtn")

        self.horizontalLayout_2.addWidget(self.RemoveCategoryBtn)

        self.CommitBtn = QPushButton(self.EditFrame)
        self.CommitBtn.setObjectName(u"CommitBtn")
        self.CommitBtn.setEnabled(False)

        self.horizontalLayout_2.addWidget(self.CommitBtn)

        self.RevertBtn = QPushButton(self.EditFrame)
        self.RevertBtn.setObjectName(u"RevertBtn")
        self.RevertBtn.setEnabled(False)

        self.horizontalLayout_2.addWidget(self.RevertBtn)


        self.verticalLayout.addWidget(self.EditFrame)

        self.CategoriesList = QTableView(CategoryChoiceDlg)
        self.CategoriesList.setObjectName(u"CategoriesList")
        self.CategoriesList.horizontalHeader().setMinimumSectionSize(8)
        self.CategoriesList.verticalHeader().setMinimumSectionSize(20)
        self.CategoriesList.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.CategoriesList)

        self.buttonBox = QDialogButtonBox(CategoryChoiceDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(CategoryChoiceDlg)
        self.buttonBox.accepted.connect(CategoryChoiceDlg.accept)
        self.buttonBox.rejected.connect(CategoryChoiceDlg.reject)

        QMetaObject.connectSlotsByName(CategoryChoiceDlg)
    # setupUi

    def retranslateUi(self, CategoryChoiceDlg):
        CategoryChoiceDlg.setWindowTitle(QCoreApplication.translate("CategoryChoiceDlg", u"Dialog", None))
        self.SearchLbl.setText(QCoreApplication.translate("CategoryChoiceDlg", u"Search", None))
        self.UpBtn.setText(QCoreApplication.translate("CategoryChoiceDlg", u"Up", None))
        self.AddCategoryBtn.setText(QCoreApplication.translate("CategoryChoiceDlg", u"Add", None))
        self.RemoveCategoryBtn.setText(QCoreApplication.translate("CategoryChoiceDlg", u"Del", None))
        self.CommitBtn.setText(QCoreApplication.translate("CategoryChoiceDlg", u"Commit", None))
        self.RevertBtn.setText(QCoreApplication.translate("CategoryChoiceDlg", u"Revert", None))
    # retranslateUi

