import sys
import os
import logging
import traceback
from PySide6.QtCore import Qt, QTranslator
from PySide6.QtWidgets import QApplication, QMessageBox
from jal.widgets.main_window import MainWindow
from jal.db.db import JalDB, JalDBError
from jal.db.settings import JalSettings

#-----------------------------------------------------------------------------------------------------------------------
def exception_logger(exctype, value, tb):
    info = traceback.format_exception(exctype, value, tb)
    logging.fatal(f"EXCEPTION: {info}")
    sys.__excepthook__(exctype, value, tb)


#-----------------------------------------------------------------------------------------------------------------------
def main():
    sys.excepthook = exception_logger
    os.environ['QT_MAC_WANTS_LAYER'] = '1'    # Workaround for https://bugreports.qt.io/browse/QTBUG-87014
    app = QApplication([])

    error = JalDB().init_db()

    translator = QTranslator(app)
    translator.load(JalDB.get_path(JalDB.PATH_LANG_FILE, language=JalSettings().getLanguage()))
    app.installTranslator(translator)

    if error.code == JalDBError.OutdatedDbSchema:
        error = JalDB().update_db_schema()

    if error.code != JalDBError.NoError:
        window = QMessageBox()
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.setWindowTitle("JAL: Start-up aborted")
        window.setIcon(QMessageBox.Critical)
        window.setText(error.message)
        window.setInformativeText(error.details)
    else:
        window = MainWindow()
    window.show()

    app.exec()
    app.removeTranslator(translator)


#-----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
