#!/usr/bin/python

import sys
import os
import logging
import traceback
from PySide2.QtCore import QTranslator
from PySide2.QtWidgets import QApplication
from main_window import MainWindow, AbortWindow
from DB.helpers import init_and_check_db, LedgerInitError, get_language


#-----------------------------------------------------------------------------------------------------------------------
def exception_logger(exctype, value, tb):
    info = traceback.format_exception(exctype, value, tb)
    logging.fatal(f"EXCEPTION: {info}")
    sys.__excepthook__(exctype, value, tb)


#-----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.excepthook = exception_logger

    own_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
    db, error = init_and_check_db(own_path)

    if error.code == LedgerInitError.EmptyDbInitialized:
        db, error = init_and_check_db(own_path)

    language = get_language(db)
    translator = QTranslator()
    language_file = own_path + "languages" + os.sep + language + '.qm'
    translator.load(language_file)
    app = QApplication([])
    app.installTranslator(translator)

    if db is None:
        window = AbortWindow(error.message)
    else:
        window = MainWindow(db, own_path, language)
    window.show()

    sys.exit(app.exec_())
