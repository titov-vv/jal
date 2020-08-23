#!/usr/bin/python

import sys
import os
import logging
import traceback
from PySide2.QtWidgets import QApplication
from main_window import MainWindow, AbortWindow
from DB.helpers import init_and_check_db


#-----------------------------------------------------------------------------------------------------------------------
def exception_logger(exctype, value, tb):
    info = traceback.format_exception(exctype, value, tb)
    logging.fatal(f"EXCEPTION: {info}")
    sys._excepthook(exctype, value, tb)


#-----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.excepthook = exception_logger

    own_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
    db, error = init_and_check_db(own_path)

    app = QApplication([])
    if db is None:
        window = AbortWindow(error.message)
    else:
        window = MainWindow(db)
    window.show()

    sys.exit(app.exec_())
