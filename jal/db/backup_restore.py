from jal.constants import Setup
import sqlite3
import logging
import os
import shutil
from dateutil import tz
from datetime import datetime
from tempfile import TemporaryDirectory
import tarfile

from PySide2.QtWidgets import QFileDialog, QMessageBox
from jal.widgets.helpers import g_tr
from jal.db.helpers import db_connection


# ------------------------------------------------------------------------------
class JalBackup:
    tmp_prefix = 'jal_'
    backup_label = 'JAL SQLITE backup. Created: '
    date_fmt = '%Y/%m/%d %H:%M:%S%z'

    def __init__(self, parent, db_file):
        self.parent = parent
        self.file = db_file
        self.backup_name = None
        self._backup_label_date = ''

    # Function returns True if all of following conditions are met (otherwise returns False):
    # - backup contains all required filenames
    # - backup contains file 'label' with valid content
    # - backup contains file 'settings.csv' with valid schema version
    def validate_backup(self):
        with tarfile.open(self.backup_name, "r:gz") as tar:
            # Check backup file list
            backup_file_list = [Setup.DB_PATH, 'label']
            if set(backup_file_list) != set(tar.getnames()):
                logging.debug("Backup content expected: " + str(backup_file_list) +
                              "\nBackup content actual: " + str(tar.getnames()))
                return False

            # Check correctness of backup label
            label_content = tar.extractfile('label').read().decode("utf-8")
            logging.debug("Backup file label: " + label_content)
            if label_content[:len(self.backup_label)] == self.backup_label:
                self._backup_label_date = label_content[len(self.backup_label):]
            else:
                logging.warning(g_tr('JalBackup', "Backup label not recognized"))
                return False
            try:
                _ = datetime.strptime(self._backup_label_date, self.date_fmt)
            except ValueError:
                logging.warning(g_tr('JalBackup', "Can't validate backup date"))
                return False
        return True

    def do_backup(self):
        db_con = sqlite3.connect(self.file)
        with TemporaryDirectory(prefix=self.tmp_prefix) as tmp_path:
            with open(tmp_path + os.sep + 'label', 'w') as label:
                label.write(f"{self.backup_label}{datetime.now().replace(tzinfo=tz.tzlocal()).strftime(self.date_fmt)}")
            backup_con = sqlite3.connect(tmp_path + os.sep + Setup.DB_PATH)
            db_con.backup(backup_con)
            with tarfile.open(self.backup_name, "w:gz") as tar:
                tar.add(tmp_path + os.sep + 'label', arcname='label')
                tar.add(tmp_path + os.sep + Setup.DB_PATH, arcname=Setup.DB_PATH)
        db_con.close()

    def do_restore(self):
        with TemporaryDirectory(prefix=self.tmp_prefix) as tmp_path:
            with tarfile.open(self.backup_name, "r:gz") as tar:
                tar.extractall(tmp_path)
            try:
                shutil.move(tmp_path + os.sep + Setup.DB_PATH, self.file)
            except:
                logging.warning(g_tr('JalBackup', "Failed to restore backup file"))
                return False
        return True

    def get_filename(self, save=True):
        self.backup_name = None
        if save:
            filename, filter = QFileDialog.getSaveFileName(None, g_tr('JalBackup', "Save backup to:"),
                                                           ".", g_tr('JalBackup', "Archives (*.tgz)"))
            if filename:
                if filter == g_tr('JalBackup', "Archives (*.tgz)") and filename[-4:] != '.tgz':
                    filename = filename + '.tgz'
        else:
            filename, _filter = QFileDialog.getOpenFileName(None, g_tr('JalBackup', "Select file with backup"),
                                                            ".", g_tr('JalBackup', "Archives (*.tgz)"))
        if filename:
            self.backup_name = filename

    def create(self):
        self.get_filename(True)
        if self.backup_name is None:
            return
        self.do_backup()
        logging.info(g_tr('JalBackup', "Backup saved in: ") + self.backup_name)

    def restore(self):
        self.get_filename(False)
        if self.backup_name is None:
            return
        db_connection().close()

        if not self.validate_backup():
            logging.error(g_tr('JalBackup', "Wrong format of backup file"))
            return

        if not self.do_restore():
            return
        logging.info(g_tr('JalBackup', "Backup restored from: ") + self.backup_name + self._backup_label_date
                     + g_tr('JalBackup', " into ") + self.file)

        QMessageBox().information(self.parent, g_tr('JalBackup', "Data restored"),
                                  g_tr('JalBackup', "Database was loaded from the backup.\n") +
                                  g_tr('JalBackup', "You should restart application to apply changes\n"
                                                    "Application will be terminated now"),
                                  QMessageBox.Ok)
        self.parent.close()

