import sys
import os
import logging
import traceback
from PySide6.QtCore import Qt, QLibraryInfo, QTranslator, qInstallMessageHandler, QtMsgType, qDebug
from PySide6.QtWidgets import QApplication, QMessageBox
from jal import __version__
from jal.widgets.main_window import MainWindow
from jal.db.db import JalDB, JalDBError
from jal.net.web_request import WebRequest
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
    app = QApplication(sys.argv)   # sys.argv is passed to enable Qt built-in options: -style, -stylesheet, -platform, etc.
    app.setApplicationName("JAL")          # Without it macOS shows the interpreter name in the application menu
    app.setApplicationDisplayName("JAL")   # The user-visible name: the macOS application menu and window titles use it
    app.setApplicationVersion(__version__)
    app.setOrganizationName("jal")
    app.setDesktopFileName("jal")          # Matches jal.desktop so Wayland can find the window icon

    error = JalDB().init_db()
    # Qt's own translation has to be loaded separately: it carries the text of the standard buttons that
    # QDialogButtonBox and QMessageBox create themselves ("Cancel", "Save", "Discard", ...), which never pass
    # through jal's .qm file. It may be absent from a given Qt installation - the buttons then stay English.
    qt_translator = QTranslator(app)
    if qt_translator.load("qtbase_" + JalSettings().getLanguage(), QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(qt_translator)
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
    # The last line of defence for the web-requests that are still running: the main window waits for them when it
    # is closed, but the event loop can also end without that happening (a session shutdown, an exit() from
    # elsewhere), and a request outliving the interpreter aborts the process - see WebRequest.wait_for_all().
    app.aboutToQuit.connect(WebRequest.wait_for_all)
    app.exec()
    if translator_installed:
        app.removeTranslator(translator)


#-----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
