import sys
import os
import logging
import traceback
from PySide6.QtCore import Qt, QTranslator, qInstallMessageHandler, QtMsgType, qDebug
from PySide6.QtWidgets import QApplication, QMessageBox
from jal.widgets.main_window import MainWindow
from jal.db.db import JalDB, JalDBError
from jal.db.settings import JalSettings

#-----------------------------------------------------------------------------------------------------------------------
def exception_logger(exctype, value, tb):
    info = traceback.format_exception(exctype, value, tb)
    logging.fatal(f"EXCEPTION: {info}")
    sys.__excepthook__(exctype, value, tb)


def make_error_window(error: JalDBError):
    window = QMessageBox()
    window.setAttribute(Qt.WA_DeleteOnClose)
    window.setWindowTitle("JAL: Start-up aborted")
    window.setIcon(QMessageBox.Critical)
    window.setText(error.message)
    window.setInformativeText(error.details)
    return window

def setup_root_logging():
    root_logger = logging.getLogger()
    log_level = os.environ.get('LOGLEVEL', 'INFO').upper()
    root_logger.setLevel(log_level)
    qInstallMessageHandler(systemWideQtLogHandler)

def systemWideQtLogHandler(level, context, message):
    # Mapping Qt message levels to Python logging levels
    level_map = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    category = context.category if hasattr(context, 'file') else ""
    ctx_str = f"{str(context)}:{category}"
    logging.log(
        level_map.get(level, logging.ERROR),
        f"[QT] {message} | {ctx_str}"[:250]
    )

#-----------------------------------------------------------------------------------------------------------------------
def main():
    setup_root_logging()
    translator_installed = False
    sys.excepthook = exception_logger
    app = QApplication([])

    error = JalDB().init_db()
    translator = QTranslator(app)
    if translator.load(JalSettings.path(JalDB.PATH_LANG_FILE)):
        if app.installTranslator(translator):
            translator_installed = True
    if error.code == JalDBError.OutdatedDbSchema:
        error = JalDB().update_db_schema()   # this call isn't a part of JalDB.init_db() intentionally - to provide translation of UI message
    if error.code != JalDBError.NoError:
        window = make_error_window(error)
    else:
        window = MainWindow(translator)
    window.show()
    app.exec()
    if translator_installed:
        app.removeTranslator(translator)


#-----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
