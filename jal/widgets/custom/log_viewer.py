import os
import logging
from datetime import datetime
from jal.constants import CustomColor
from jal.widgets.icons import JalIcon
from PySide6.QtCore import Qt, Slot, Signal, QObject, qInstallMessageHandler, QtMsgType
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel, QPushButton
from PySide6.QtGui import QBrush

# Code is based on example from https://docs.python.org/3/howto/logging-cookbook.html#a-qt-gui-for-logging


# There is an error with multiple inheritance in Qt, that prevents subclassing LogHandler from both Handler and
# QObject. Thus separate class is required.
class SignalForwarder(QObject):
    signal = Signal(int, str)    # Log level, Log message


# Adapter class to have custom log handler that may be passed to logger.addHandler/logger.removeHandler methods and
# then forward all to the Viewer class for displaying
class LogHandler(logging.Handler):
    def __init__(self, receiver):
        super().__init__()
        self._forwarder = SignalForwarder()
        self._forwarder.signal.connect(receiver)

    def emit(self, record, **kwargs):
        message = self.format(record)
        self._forwarder.signal.emit(record.levelno, message)


# A GUI class to display messages forwarded from python logging unit in a normal multi-line text area
class LogViewer(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = QApplication.instance()
        self._logger = None     # Here an instance of current logger will be stored
        self._log_handler = LogHandler(self.process_message)
        self.setReadOnly(True)
        self.status_bar = None    # Status bar where notifications and control are located
        self.expandButton = None  # Button that shows/hides log window
        self.notification = None  # Here is QLabel element to display LOG update status
        self.clear_color = None   # Variable to store initial "clear" background color
        self.collapsed_text = self.tr("▶ logs")
        self.expanded_text = self.tr("▲ logs")

        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.addAction(JalIcon[JalIcon.COPY], self.tr('Copy'), self._copy2clipboard)
        self.addAction(self.tr('Select all'), self.selectAll)
        self.addAction(JalIcon[JalIcon.CLEAN], self.tr('Clear'), self.clear)

    def _copy2clipboard(self):
        cursor = self.textCursor()
        text = cursor.selectedText() if cursor.selectedText() else self.toPlainText()
        QApplication.clipboard().setText(text)

    def startLogging(self):
        self._logger = logging.getLogger()
        self._logger.addHandler(self._log_handler)
        log_level = os.environ.get('LOGLEVEL', 'INFO').upper()
        self._logger.setLevel(log_level)
        self._log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        qInstallMessageHandler(self.qtLogHandler)

    def stopLogging(self):
        self._logger.removeHandler(self._log_handler)    # Removing handler (but it doesn't prevent exception at exit)
        logging.raiseExceptions = False                  # Silencing logging module exceptions

    def qtLogHandler(self, mode, _context, message):
        colors = {
            QtMsgType.QtDebugMsg: CustomColor.Grey,
            QtMsgType.QtInfoMsg: None,
            QtMsgType.QtWarningMsg: CustomColor.LightRed,
            QtMsgType.QtCriticalMsg: CustomColor.LightRed,
            QtMsgType.QtFatalMsg: CustomColor.LightRed,
            QtMsgType.QtSystemMsg: CustomColor.LightRed
        }
        try:
            message_color = colors[mode]
        except KeyError:
            message_color = CustomColor.LightRed
        message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - Qt - {message}"
        self.displayMessage(message, message_color)

    @Slot(int, str)
    def process_message(self, log_level, message):
        colors = {
            logging.DEBUG: CustomColor.Grey,
            logging.INFO: None,
            logging.WARNING: CustomColor.LightRed,
            logging.ERROR: CustomColor.LightRed,
            logging.CRITICAL: CustomColor.LightRed
        }
        try:
            message_color = colors[log_level]
        except KeyError:
            message_color = CustomColor.LightRed
        self.displayMessage(message, message_color)

    def displayMessage(self, message: str, color: CustomColor = None):
        color = self.clear_color if color is None else color

        # Store message in log window
        text_format = self.currentCharFormat()
        text_format.setForeground(QBrush(color))
        self.setCurrentCharFormat(text_format)
        self.appendPlainText(message)

        # Show in status bar
        if self.notification:
            palette = self.notification.palette()
            palette.setColor(self.notification.foregroundRole(), color)
            self.notification.setPalette(palette)
            msg = message.replace('\n', "; ")  # Get rid of new lines in error message
            elided_text = self.notification.fontMetrics().elidedText(msg, Qt.ElideRight, self.get_available_width())
            self.notification.setText(elided_text)
        # Set button color
        if self.expandButton:
            palette = self.expandButton.palette()
            palette.setColor(self.expandButton.foregroundRole(), color)
        self.app.processEvents()

    def showEvent(self, event):
        self.cleanNotification()
        super().showEvent(event)

    def setStatusBar(self, status_bar):
        self.setVisible(False)
        self.status_bar = status_bar

        self.expandButton = QPushButton(self.collapsed_text, parent=self)
        self.expandButton.setFixedWidth(int(self.expandButton.fontMetrics().horizontalAdvance(self.collapsed_text) * 1.5))
        self.expandButton.setCheckable(True)
        self.expandButton.clicked.connect(self.showLogs)
        self.status_bar.addWidget(self.expandButton)

        self.notification = QLabel(self)
        self.status_bar.addWidget(self.notification, stretch=3)
        self.notification.setAutoFillBackground(True)
        self.clear_color = self.expandButton.palette().color(self.notification.foregroundRole())

    def removeStatusBar(self):
        self.cleanNotification()
        self.notification = None

    def cleanNotification(self):
        if self.notification:
            palette = self.notification.palette()
            palette.setColor(self.notification.foregroundRole(), self.clear_color)
            self.notification.setPalette(palette)
            self.notification.setText("")

    @Slot()
    def showLogs(self):
        self.setVisible(self.expandButton.isChecked())
        text = self.expanded_text if self.expandButton.isChecked() else self.collapsed_text
        self.expandButton.setText(text)

    # Calculates maximum width that is free on status bar
    def get_available_width(self):
        width = self.status_bar.width()
        for child in self.status_bar.children():
            if hasattr(child, "width") and child != self.notification:
                width -= child.width()
        return width - 8    # return calculated width reduced by small safety gap
