import sys
import os
import logging
import traceback
from PySide2.QtCore import Qt, QTranslator
from PySide2.QtWidgets import QApplication, QMessageBox
from jal.widgets.main_window import MainWindow
from jal.db.update import JalDB
from jal.db.settings import JalSettings
from jal.db.helpers import init_and_check_db, LedgerInitError, update_db_schema


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
    error = init_and_check_db(own_path)

    if error.code == LedgerInitError.EmptyDbInitialized:  # If DB was just created from SQL - initialize it again
        error = init_and_check_db(own_path)

    app = QApplication([])
    language = JalDB().get_language_code(JalSettings().getValue('Language', default=1))
    translator = QTranslator(app)
    language_file = own_path + "languages" + os.sep + language + '.qm'
    translator.load(language_file)
    app.installTranslator(translator)

    if error.code == LedgerInitError.OutdatedDbSchema:
        error = update_db_schema(own_path)
        if error.code == LedgerInitError.DbInitSuccess:
            error = init_and_check_db(own_path)

    if error.code != LedgerInitError.DbInitSuccess:
        window = QMessageBox()
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.setWindowTitle("JAL: Start-up aborted")
        window.setIcon(QMessageBox.Critical)
        window.setText(error.message)
        window.setInformativeText(error.details)
    else:
        window = MainWindow(own_path, language)
    window.show()

    app.exec_()
    app.removeTranslator(translator)

if __name__ == "__main__":
    main()
