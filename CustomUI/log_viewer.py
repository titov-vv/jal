import logging

from PySide2.QtWidgets import QPlainTextEdit


class LogViewer(QPlainTextEdit, logging.Handler):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        logging.Handler.__init__(self)
        self.setReadOnly(True)
        self.notification = None
        self.last_level = 0

    def emit(self, record):
        # Store message in log window
        msg = self.format(record)
        self.appendPlainText(msg)

        # Raise flag if status bar is set
        if self.notification:
            if self.last_level < record.levelno:
                self.notification.setText("Log: " + record.levelname[0])

        qApp.processEvents()

    def setNotificationLabel(self, label):
        self.notification = label
        self.notification.setFixedWidth(self.notification.fontMetrics().width("Log: X"))

    def removeNoficationLable(self):
        self.notification = None

    def cleanNotification(self):
        self.last_level = 0
        self.notification.setText("")