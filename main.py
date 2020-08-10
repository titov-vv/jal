#!/usr/bin/python

import sys
import logging
import traceback
from PySide2.QtWidgets import QApplication
from PySide2 import QtCore
from main_window import MainWindow

def exception_logger(exctype, value, tb):
    info = traceback.format_exception(exctype, value, tb)
    logging.fatal(f"EXCEPTION: {info}")
    sys._excepthook(exctype, value, tb)

if __name__ == "__main__":
    sys.excepthook = exception_logger

    app = QApplication([])
    # font = app.font()
    # font.setPixelSize(15)
    # app.setFont(font)

    window = MainWindow()
    # window.showMaximized()
    window.show()

    sys.exit(app.exec_())
