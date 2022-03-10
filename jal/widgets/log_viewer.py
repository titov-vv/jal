import logging
from jal.constants import CustomColor
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QLabel, QPushButton
from PySide6.QtGui import QBrush


class LogViewer(QPlainTextEdit, logging.Handler):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        logging.Handler.__init__(self)
        self.app = QApplication.instance()
        self.setReadOnly(True)
        self.status_bar = None    # Status bar where notifications and control are located
        self.expandButton = None  # Button that shows/hides log window
        self.notification = None  # Here is QLabel element to display LOG update status
        self.clear_color = None   # Variable to store initial "clear" background color
        self.collapsed_text = self.tr("▶ logs")
        self.expanded_text = self.tr("▲ logs")

    def emit(self, record, **kwargs):
        predefinded_colors = {
            logging.DEBUG: CustomColor.Grey,
            logging.INFO: self.clear_color,
            logging.WARNING: CustomColor.LightRed,
            logging.ERROR: CustomColor.LightRed,
            logging.CRITICAL: CustomColor.LightRed
        }
        try:
            msg_color = predefinded_colors[record.levelno]
        except KeyError:
            self.appendPlainText(self.tr("Unknown logging level provided: ") + f"{record.levelno}")
            msg_color = CustomColor.LightRed

        # Store message in log window
        msg = self.format(record)
        tf = self.currentCharFormat()
        tf.setForeground(QBrush(msg_color))
        self.setCurrentCharFormat(tf)
        self.appendPlainText(msg)

        # Show in status bar
        if self.notification:
            palette = self.notification.palette()
            palette.setColor(self.notification.foregroundRole(), msg_color)
            self.notification.setPalette(palette)
            msg = msg.replace('\n', "; ")  # Get rid of new lines in error message
            elided_text = self.notification.fontMetrics().elidedText(msg, Qt.ElideRight, self.get_available_width())
            self.notification.setText(elided_text)
        # Set button color
        if self.expandButton:
            palette = self.expandButton.palette()
            palette.setColor(self.expandButton.foregroundRole(), msg_color)

        self.app.processEvents()

    def showEvent(self, event):
        self.cleanNotification()
        super().showEvent(event)

    def setStatusBar(self, status_bar):
        self.setVisible(False)
        self.status_bar = status_bar

        self.expandButton = QPushButton(self.collapsed_text, parent=self)
        self.expandButton.setFixedWidth(self.expandButton.fontMetrics().horizontalAdvance(self.collapsed_text) * 1.25)
        self.expandButton.setCheckable(True)
        self.expandButton.clicked.connect(self.showLogs)
        self.status_bar.addWidget(self.expandButton)

        self.notification = QLabel(self)
        self.status_bar.addWidget(self.notification)
        self.notification.setAutoFillBackground(True)
        self.clear_color = self.expandButton.palette().color(self.notification.foregroundRole())
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def removeStatusBar(self):
        self.cleanNotification()
        self.notification = None

    def cleanNotification(self):
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
