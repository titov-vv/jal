import logging
from jal.widgets.icons import JalIcon
from jal.widgets.theme import Theme, Meaning
from PySide6.QtCore import Qt, Slot, Signal, QEvent, QObject, QMetaObject, Q_ARG
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel, QPushButton
from PySide6.QtGui import QBrush, QFont

# Code is based on example from https://docs.python.org/3/howto/logging-cookbook.html#a-qt-gui-for-logging


# There is an error with multiple inheritance in Qt, that prevents subclassing LogHandler from both Handler and
# QObject. Thus separate class is required.
class SignalForwarder(QObject):
    signal = Signal(int, str)    # Log level, Log message

# Adapter class to have custom log handler that may be passed to logger.addHandler/logger.removeHandler methods and
# then forward all to the Viewer class for displaying
class LogHandler(logging.Handler):
    def __init__(self, receiver, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self._forwarder = SignalForwarder()
        self._forwarder.signal.connect(receiver)

    def emit(self, record, **kwargs):
        message = self.format(record)
        self._forwarder.signal.emit(record.levelno, message)

    def disconnect(self):
        self._forwarder.signal.disconnect()


# A GUI class to display messages forwarded from python logging unit in a normal multi-line text area
class LogViewer(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        
    def stopLogging(self):
        self._log_handler.disconnect()
        self._logger.removeHandler(self._log_handler)    # Removing handler (but it doesn't prevent exception at exit)

    @Slot(int, str)
    def process_message(self, log_level, message):
        # Can be called from inside of QT rendering process, causing segmentation fault
        QMetaObject.invokeMethod(self, "displayMessage", Qt.QueuedConnection, Q_ARG(int, log_level), Q_ARG(str, message))

    @Slot(int, str)
    def displayMessage(self, log_level, message: str):
        meanings = {
            logging.DEBUG: Meaning.MUTED,
            logging.INFO: None,
            logging.WARNING: Meaning.WARNING,
            logging.ERROR: Meaning.NEGATIVE,
            logging.CRITICAL: Meaning.NEGATIVE
        }
        meaning = meanings[log_level]

        # Store message in log window
        text_format = self.currentCharFormat()
        text_format.setForeground(QBrush(self._ink(meaning, self)))
        text_format.setFontWeight(QFont.Bold if log_level >= logging.CRITICAL else QFont.Normal)
        self.setCurrentCharFormat(text_format)
        self.appendPlainText(message)

        # Show in status bar
        if self.notification:
            palette = self.notification.palette()
            palette.setColor(self.notification.foregroundRole(), self._ink(meaning, self.notification))
            self.notification.setPalette(palette)
            msg = message.replace('\n', "; ")  # Get rid of new lines in error message
            elided_text = self.notification.fontMetrics().elidedText(msg, Qt.ElideRight, self.get_available_width())
            self.notification.setText(elided_text)
        # Set button color
        if self.expandButton:
            palette = self.expandButton.palette()
            palette.setColor(self.expandButton.foregroundRole(), self._ink(meaning, self.expandButton))
            self.expandButton.setPalette(palette)

    # The same message is shown in three places that don't share a ground: the log pane sits on Base while the
    # status bar label and its button sit on Window and Button. So the meaning is resolved once per place.
    def _ink(self, meaning, widget):
        if meaning is None:
            return self._neutral_ink(widget)
        return Theme.text(meaning, widget.palette().color(widget.backgroundRole()))

    # The color an unremarkable message is shown in - read from the application palette rather than from the
    # widget itself, which may still be carrying the color of the last error.
    def _neutral_ink(self, widget):
        return QApplication.palette(widget).color(widget.foregroundRole())

    # A theme switch replaces the palette every color above was derived from. The status bar is put back to the
    # new neutral color; lines already in the pane keep the color they were written with, as any text does.
    def changeEvent(self, event):
        if event.type() == QEvent.ApplicationPaletteChange and self.notification is not None:
            self.clear_color = self._neutral_ink(self.notification)
            if self.expandButton:
                self.expandButton.setPalette(QApplication.palette(self.expandButton))
            self.cleanNotification()
        super().changeEvent(event)

    def showEvent(self, event):
        self.cleanNotification()
        super().showEvent(event)

    def setStatusBar(self, status_bar):
        self.setVisible(False)
        self.status_bar = status_bar

        self.expandButton = QPushButton(self.collapsed_text, parent=self)
        self.expandButton.setCheckable(True)
        self.expandButton.clicked.connect(self.showLogs)
        self.status_bar.addWidget(self.expandButton)

        self.notification = QLabel(self)
        self.status_bar.addWidget(self.notification, stretch=3)
        self.notification.setAutoFillBackground(True)
        self.clear_color = self._neutral_ink(self.notification)

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
