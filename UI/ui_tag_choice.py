# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tag_choice_dlg.ui'
##
## Created by: Qt User Interface Compiler version 5.15.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QDate, QDateTime, QMetaObject,
    QObject, QPoint, QRect, QSize, QTime, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter,
    QPixmap, QRadialGradient)
from PySide2.QtWidgets import *


class Ui_TagChoiceDlg(object):
    def setupUi(self, TagChoiceDlg):
        if not TagChoiceDlg.objectName():
            TagChoiceDlg.setObjectName(u"TagChoiceDlg")
        TagChoiceDlg.resize(393, 300)
        self.verticalLayout = QVBoxLayout(TagChoiceDlg)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(2, 2, 2, 2)
        self.SearchFrame = QFrame(TagChoiceDlg)
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

        self.EditFrame = QFrame(TagChoiceDlg)
        self.EditFrame.setObjectName(u"EditFrame")
        self.EditFrame.setFrameShape(QFrame.NoFrame)
        self.EditFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.EditFrame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.AddTagBtn = QPushButton(self.EditFrame)
        self.AddTagBtn.setObjectName(u"AddTagBtn")

        self.horizontalLayout_2.addWidget(self.AddTagBtn)

        self.RemoveTagBtn = QPushButton(self.EditFrame)
        self.RemoveTagBtn.setObjectName(u"RemoveTagBtn")

        self.horizontalLayout_2.addWidget(self.RemoveTagBtn)

        self.CommitBtn = QPushButton(self.EditFrame)
        self.CommitBtn.setObjectName(u"CommitBtn")
        self.CommitBtn.setEnabled(False)

        self.horizontalLayout_2.addWidget(self.CommitBtn)

        self.RevertBtn = QPushButton(self.EditFrame)
        self.RevertBtn.setObjectName(u"RevertBtn")
        self.RevertBtn.setEnabled(False)

        self.horizontalLayout_2.addWidget(self.RevertBtn)


        self.verticalLayout.addWidget(self.EditFrame)

        self.TagsList = QTableView(TagChoiceDlg)
        self.TagsList.setObjectName(u"TagsList")
        self.TagsList.horizontalHeader().setMinimumSectionSize(8)
        self.TagsList.verticalHeader().setMinimumSectionSize(20)
        self.TagsList.verticalHeader().setDefaultSectionSize(20)

        self.verticalLayout.addWidget(self.TagsList)

        self.buttonBox = QDialogButtonBox(TagChoiceDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(TagChoiceDlg)
        self.buttonBox.accepted.connect(TagChoiceDlg.accept)
        self.buttonBox.rejected.connect(TagChoiceDlg.reject)

        QMetaObject.connectSlotsByName(TagChoiceDlg)
    # setupUi

    def retranslateUi(self, TagChoiceDlg):
        TagChoiceDlg.setWindowTitle(QCoreApplication.translate("TagChoiceDlg", u"Tags", None))
        self.SearchLbl.setText(QCoreApplication.translate("TagChoiceDlg", u"Search", None))
        self.AddTagBtn.setText(QCoreApplication.translate("TagChoiceDlg", u"Add", None))
        self.RemoveTagBtn.setText(QCoreApplication.translate("TagChoiceDlg", u"Del", None))
        self.CommitBtn.setText(QCoreApplication.translate("TagChoiceDlg", u"Commit", None))
        self.RevertBtn.setText(QCoreApplication.translate("TagChoiceDlg", u"Revert", None))
    # retranslateUi

