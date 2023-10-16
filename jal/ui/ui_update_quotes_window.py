# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'quotes_update.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QDateEdit,
    QDialog, QDialogButtonBox, QGridLayout, QLabel,
    QListWidget, QListWidgetItem, QSizePolicy, QWidget)

class Ui_UpdateQuotesDlg(object):
    def setupUi(self, UpdateQuotesDlg):
        if not UpdateQuotesDlg.objectName():
            UpdateQuotesDlg.setObjectName(u"UpdateQuotesDlg")
        UpdateQuotesDlg.setWindowModality(Qt.ApplicationModal)
        UpdateQuotesDlg.resize(256, 308)
        self.gridLayout = QGridLayout(UpdateQuotesDlg)
        self.gridLayout.setObjectName(u"gridLayout")
        self.StartDateEdit = QDateEdit(UpdateQuotesDlg)
        self.StartDateEdit.setObjectName(u"StartDateEdit")
        self.StartDateEdit.setCalendarPopup(True)
        self.StartDateEdit.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.StartDateEdit, 0, 1, 1, 1)

        self.buttonBox = QDialogButtonBox(UpdateQuotesDlg)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.gridLayout.addWidget(self.buttonBox, 3, 1, 1, 1)

        self.EndDateEdit = QDateEdit(UpdateQuotesDlg)
        self.EndDateEdit.setObjectName(u"EndDateEdit")
        self.EndDateEdit.setCalendarPopup(True)
        self.EndDateEdit.setTimeSpec(Qt.UTC)

        self.gridLayout.addWidget(self.EndDateEdit, 1, 1, 1, 1)

        self.EndDateLbl = QLabel(UpdateQuotesDlg)
        self.EndDateLbl.setObjectName(u"EndDateLbl")

        self.gridLayout.addWidget(self.EndDateLbl, 1, 0, 1, 1)

        self.StartDateLbl = QLabel(UpdateQuotesDlg)
        self.StartDateLbl.setObjectName(u"StartDateLbl")

        self.gridLayout.addWidget(self.StartDateLbl, 0, 0, 1, 1)

        self.SourcesList = QListWidget(UpdateQuotesDlg)
        self.SourcesList.setObjectName(u"SourcesList")
        self.SourcesList.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.SourcesList.setAlternatingRowColors(True)
        self.SourcesList.setSortingEnabled(True)

        self.gridLayout.addWidget(self.SourcesList, 2, 1, 1, 1)

        self.SourcesLbl = QLabel(UpdateQuotesDlg)
        self.SourcesLbl.setObjectName(u"SourcesLbl")

        self.gridLayout.addWidget(self.SourcesLbl, 2, 0, 1, 1)


        self.retranslateUi(UpdateQuotesDlg)
        self.buttonBox.accepted.connect(UpdateQuotesDlg.accept)
        self.buttonBox.rejected.connect(UpdateQuotesDlg.reject)

        QMetaObject.connectSlotsByName(UpdateQuotesDlg)
    # setupUi

    def retranslateUi(self, UpdateQuotesDlg):
        UpdateQuotesDlg.setWindowTitle(QCoreApplication.translate("UpdateQuotesDlg", u"Update asset's quotes", None))
        self.StartDateEdit.setDisplayFormat(QCoreApplication.translate("UpdateQuotesDlg", u"dd/MM/yyyy", None))
        self.EndDateEdit.setDisplayFormat(QCoreApplication.translate("UpdateQuotesDlg", u"dd/MM/yyyy", None))
        self.EndDateLbl.setText(QCoreApplication.translate("UpdateQuotesDlg", u"End date", None))
        self.StartDateLbl.setText(QCoreApplication.translate("UpdateQuotesDlg", u"Start date", None))
        self.SourcesLbl.setText(QCoreApplication.translate("UpdateQuotesDlg", u"Sources", None))
    # retranslateUi

