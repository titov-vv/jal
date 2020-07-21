from PySide2.QtWidgets import QPlainTextEdit
import logging

class LogViewer(QPlainTextEdit, logging.Handler):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        logging.Handler.__init__(self)
        self.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.appendPlainText(msg)
