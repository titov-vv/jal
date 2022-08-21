import sys
import os
import logging
import traceback
from PySide6.QtCore import Qt, QTranslator
from PySide6.QtWidgets import QApplication, QMessageBox
from jal.constants import Setup
from jal.widgets.main_window import MainWindow
from jal.db.db import JalDB, JalDBError
from jal.db.settings import JalSettings
from jal.db.helpers import get_app_path


#-----------------------------------------------------------------------------------------------------------------------
def exception_logger(exctype, value, tb):
    info = traceback.format_exception(exctype, value, tb)
    logging.fatal(f"EXCEPTION: {info}")
    sys.__excepthook__(exctype, value, tb)


#-----------------------------------------------------------------------------------------------------------------------
def main():
    sys.excepthook = exception_logger
    os.environ['QT_MAC_WANTS_LAYER'] = '1'    # Workaround for https://bugreports.qt.io/browse/QTBUG-87014

    error = JalDB().init_db(get_app_path())

    app = QApplication([])
    language = JalSettings().getLanguage()
    translator = QTranslator(app)
    language_file = get_app_path() + Setup.LANG_PATH + os.sep + language + '.qm'
    translator.load(language_file)
    app.installTranslator(translator)

    if error.code == JalDBError.OutdatedDbSchema:
        error = JalDB().update_db_schema(get_app_path())

    if error.code != JalDBError.NoError:
        window = QMessageBox()
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.setWindowTitle("JAL: Start-up aborted")
        window.setIcon(QMessageBox.Critical)
        window.setText(error.message)
        window.setInformativeText(error.details)
    else:
        window = MainWindow(language)
    window.show()

    app.exec()
    app.removeTranslator(translator)


#-----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
