# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'merge_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.11.0
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
    QGridLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSizePolicy, QSpacerItem,
    QWidget)

class Ui_MergeFilesToolDialog(object):
    def setupUi(self, MergeFilesToolDialog):
        if not MergeFilesToolDialog.objectName():
            MergeFilesToolDialog.setObjectName(u"MergeFilesToolDialog")
        MergeFilesToolDialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        MergeFilesToolDialog.resize(433, 349)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MergeFilesToolDialog.sizePolicy().hasHeightForWidth())
        MergeFilesToolDialog.setSizePolicy(sizePolicy)
        font = QFont()
        font.setFamilies([u"DejaVu Sans"])
        MergeFilesToolDialog.setFont(font)
        self.gridLayout = QGridLayout(MergeFilesToolDialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.InputLabel = QLabel(MergeFilesToolDialog)
        self.InputLabel.setObjectName(u"InputLabel")

        self.gridLayout.addWidget(self.InputLabel, 0, 0, 1, 1)

        self.OutputLabel = QLabel(MergeFilesToolDialog)
        self.OutputLabel.setObjectName(u"OutputLabel")

        self.gridLayout.addWidget(self.OutputLabel, 3, 0, 1, 1)

        self.AddBtn = QPushButton(MergeFilesToolDialog)
        self.AddBtn.setObjectName(u"AddBtn")

        self.gridLayout.addWidget(self.AddBtn, 0, 2, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 2, 2, 1, 1)

        self.OutputFileName = QLineEdit(MergeFilesToolDialog)
        self.OutputFileName.setObjectName(u"OutputFileName")
        self.OutputFileName.setEnabled(True)
        self.OutputFileName.setReadOnly(True)

        self.gridLayout.addWidget(self.OutputFileName, 3, 1, 1, 1)

        self.RemoveBtn = QPushButton(MergeFilesToolDialog)
        self.RemoveBtn.setObjectName(u"RemoveBtn")

        self.gridLayout.addWidget(self.RemoveBtn, 1, 2, 1, 1)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer_2, 1, 0, 2, 1)

        self.OutputSelectBtn = QPushButton(MergeFilesToolDialog)
        self.OutputSelectBtn.setObjectName(u"OutputSelectBtn")

        self.gridLayout.addWidget(self.OutputSelectBtn, 3, 2, 1, 1)

        self.DialogButtonBox = QDialogButtonBox(MergeFilesToolDialog)
        self.DialogButtonBox.setObjectName(u"DialogButtonBox")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.DialogButtonBox.sizePolicy().hasHeightForWidth())
        self.DialogButtonBox.setSizePolicy(sizePolicy1)
        self.DialogButtonBox.setOrientation(Qt.Orientation.Horizontal)
        self.DialogButtonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.gridLayout.addWidget(self.DialogButtonBox, 4, 0, 1, 3)

        self.InputFilesList = QListWidget(MergeFilesToolDialog)
        self.InputFilesList.setObjectName(u"InputFilesList")

        self.gridLayout.addWidget(self.InputFilesList, 0, 1, 3, 1)


        self.retranslateUi(MergeFilesToolDialog)
        self.DialogButtonBox.accepted.connect(MergeFilesToolDialog.accept)
        self.DialogButtonBox.rejected.connect(MergeFilesToolDialog.reject)

        QMetaObject.connectSlotsByName(MergeFilesToolDialog)
    # setupUi

    def retranslateUi(self, MergeFilesToolDialog):
        MergeFilesToolDialog.setWindowTitle(QCoreApplication.translate("MergeFilesToolDialog", u"Merge tax files", None))
        self.InputLabel.setText(QCoreApplication.translate("MergeFilesToolDialog", u"Input files:", None))
        self.OutputLabel.setText(QCoreApplication.translate("MergeFilesToolDialog", u"Output file:", None))
#if QT_CONFIG(tooltip)
        self.AddBtn.setToolTip(QCoreApplication.translate("MergeFilesToolDialog", u"Add file", None))
#endif // QT_CONFIG(tooltip)
        self.AddBtn.setText("")
#if QT_CONFIG(tooltip)
        self.RemoveBtn.setToolTip(QCoreApplication.translate("MergeFilesToolDialog", u"Remove file", None))
#endif // QT_CONFIG(tooltip)
        self.RemoveBtn.setText("")
        self.OutputSelectBtn.setText(QCoreApplication.translate("MergeFilesToolDialog", u" ... ", None))
    # retranslateUi

