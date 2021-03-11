import logging
from jal.constants import CustomColor
from PySide2.QtCore import Qt
from PySide2 import QtWidgets
from PySide2.QtWidgets import QPlainTextEdit


class LogViewer(QPlainTextEdit, logging.Handler):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        logging.Handler.__init__(self)
        self.app = QtWidgets.QApplication.instance()
        self.setReadOnly(True)
        self.notification = None  # Here is QLabel element to display LOG update status
        self.clear_color = None   # Variable to store initial "clear" background color

    def emit(self, record, **kwargs):
        # Store message in log window
        msg = self.format(record)
        self.appendPlainText(msg)

        # Show in status bar
        if self.notification:
            palette = self.notification.palette()
            if record.levelno <= logging.INFO:
                palette.setColor(self.notification.backgroundRole(), self.clear_color)
            elif record.levelno <= logging.WARNING:
                palette.setColor(self.notification.backgroundRole(), CustomColor.LightYellow)
            else:
                palette.setColor(self.notification.backgroundRole(), CustomColor.LightRed)
            self.notification.setPalette(palette)

            available_width = self.notification.parent().width() - 64
            elided_text = self.notification.fontMetrics().elidedText(msg, Qt.ElideRight, available_width)
            self.notification.setText(elided_text)

        self.app.processEvents()

    def showEvent(self, event):
        self.cleanNotification()
        super().showEvent(event)

    def setNotificationLabel(self, label):
        self.notification = label
        self.notification.setAutoFillBackground(True)
        self.clear_color = self.notification.palette().color(self.notification.backgroundRole())

    def removeNotificationLabel(self):
        self.cleanNotification()
        self.notification = None

    def cleanNotification(self):
        self.last_level = 0
        palette = self.notification.palette()
        palette.setColor(self.notification.backgroundRole(), self.clear_color)
        self.notification.setPalette(palette)
        self.notification.setText("")

