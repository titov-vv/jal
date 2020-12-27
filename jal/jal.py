import sys
import os
import logging
import traceback
from PySide2.QtCore import QTranslator
from PySide2.QtWidgets import QApplication
from jal.widgets.main_window import MainWindow, AbortWindow
from jal.db.helpers import init_and_check_db, LedgerInitError, get_language


#-----------------------------------------------------------------------------------------------------------------------
def exception_logger(exctype, value, tb):
    info = traceback.format_exception(exctype, value, tb)
    logging.fatal(f"EXCEPTION: {info}")
    sys.__excepthook__(exctype, value, tb)


#-----------------------------------------------------------------------------------------------------------------------
def main():
    sys.excepthook = exception_logger
    os.environ['QT_MAC_WANTS_LAYER'] = '1'    # Workaround for https://bugreports.qt.io/browse/QTBUG-87014

    own_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
    db, error = init_and_check_db(own_path)

    if error.code == LedgerInitError.EmptyDbInitialized:
        db, error = init_and_check_db(own_path)

    app = QApplication([])
    language = get_language(db)
    translator = QTranslator(app)
    language_file = own_path + "languages" + os.sep + language + '.qm'
    translator.load(language_file)
    app.installTranslator(translator)

    if db is None:
        window = AbortWindow(error.message)
    else:
        window = MainWindow(db, own_path, language)
    window.show()

    app.exec_()
    app.removeTranslator(translator)

if __name__ == "__main__":
    main()
