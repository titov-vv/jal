#!/usr/bin/env python
# Screenshots of JAL as it looks the very first time it is started: an empty database, no accounts, no operations.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from demo_env import prepare_environment, assert_demo_database

from PySide6.QtWidgets import QApplication
from capture import save, WINDOW_SIZE, operations_window


def main():
    prepare_environment(subdir="empty")
    app = QApplication.instance() or QApplication([])
    from jal.db.db import JalDB, JalDBError
    path = assert_demo_database("empty")
    if os.path.isfile(path):
        os.remove(path)
    error = JalDB().init_db()
    if error.code != JalDBError.NoError:
        raise RuntimeError(f"Can't initialize an empty database: {error.message}")

    from jal.widgets.main_window import MainWindow
    window = MainWindow(None)
    window.resize(*WINDOW_SIZE)
    window.show()
    QApplication.processEvents()
    operations = operations_window(window)
    operations.ui.BalanceOperationsSplitter.setSizes([430, WINDOW_SIZE[0] - 430])
    QApplication.processEvents()
    save(window, "first_run_main_window")

    from jal.widgets.reference_dialogs import ResidenceDialog, AccountListDialog
    residence = ResidenceDialog(window)
    residence.resize(700, 260)
    residence.show()
    QApplication.processEvents()
    save(residence, "first_run_residence")
    residence.close()

    accounts = AccountListDialog(window)
    accounts.resize(860, 300)
    accounts.show()
    QApplication.processEvents()
    save(accounts, "first_run_accounts")
    accounts.close()
    window.close()


if __name__ == "__main__":
    main()
