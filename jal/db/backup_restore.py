from jal.constants import Setup
import sqlite3
import logging
import os
from dateutil import tz
from datetime import datetime
from tempfile import TemporaryDirectory
import tarfile
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from jal.db.db import JalDB
from jal.db.settings import JalSettings


# ------------------------------------------------------------------------------
class JalBackup:
    tmp_prefix = 'jal_'
    backup_label = 'JAL SQLITE backup. Created: '
    date_fmt = '%Y/%m/%d %H:%M:%S%z'

    def __init__(self, parent):
        self.parent = parent
        self.file = JalSettings.path(JalSettings.PATH_DB_FILE)
        self.backup_name = None
        self._backup_label_date = ''

    def tr(self, text):
        return QApplication.translate("JalBackup", text)

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
                logging.warning(self.tr("Backup label not recognized"))
                return False
            try:
                _ = datetime.strptime(self._backup_label_date, self.date_fmt)
            except ValueError:
                logging.warning(self.tr("Can't validate backup date"))
                return False
        return True

    def do_backup(self):
        with TemporaryDirectory(prefix=self.tmp_prefix) as tmp_path:
            with open(tmp_path + os.sep + 'label', 'w') as label:
                label.write(f"{self.backup_label}{datetime.now().replace(tzinfo=tz.tzlocal()).strftime(self.date_fmt)}")
            # Copy database file
            original_db_connection = sqlite3.connect(self.file)
            backup_db_connection = sqlite3.connect(tmp_path + os.sep + Setup.DB_PATH)
            original_db_connection.backup(backup_db_connection)
            original_db_connection.close()
            backup_db_connection.close()
            # Pack files
            with tarfile.open(self.backup_name, "w:gz") as tar:
                tar.add(tmp_path + os.sep + 'label', arcname='label')
                tar.add(tmp_path + os.sep + Setup.DB_PATH, arcname=Setup.DB_PATH)

    def do_restore(self):
        with TemporaryDirectory(prefix=self.tmp_prefix) as tmp_path:
            with tarfile.open(self.backup_name, "r:gz") as tar:
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                    tar.extractall(path, members, numeric_owner=numeric_owner)
                
                safe_extract(tar, tmp_path)
            try:
                os.rename(tmp_path + os.sep + Setup.DB_PATH, self.file)
            except:
                logging.warning(self.tr("Failed to restore backup file"))
                return False
        return True

    def get_filename(self, save=True):
        self.backup_name = None
        if save:
            filename, filter = QFileDialog.getSaveFileName(None, self.tr("Save backup to:"),
                                                           ".", self.tr("Archives (*.tgz)"))
            if filename:
                if filter == self.tr("Archives (*.tgz)") and filename[-4:] != '.tgz':
                    filename = filename + '.tgz'
        else:
            filename, _filter = QFileDialog.getOpenFileName(None, self.tr("Select file with backup"),
                                                            ".", self.tr("Archives (*.tgz)"))
        if filename:
            self.backup_name = filename

    def create(self):
        self.get_filename(True)
        if self.backup_name is None:
            return
        self.do_backup()
        logging.info(self.tr("Backup saved in: ") + self.backup_name)

    def restore(self):
        self.get_filename(False)
        if self.backup_name is None:
            return
        JalDB.connection().close()

        if not self.validate_backup():
            logging.error(self.tr("Wrong format of backup file"))
            return

        if not self.do_restore():
            return
        logging.info(self.tr("Backup restored from: ") + self.backup_name + self._backup_label_date
                     + self.tr(" into ") + self.file)

        QMessageBox().information(self.parent, self.tr("Data restored"),
                                  self.tr("Database was loaded from the backup.\n") +
                                  self.tr("You should restart application to apply changes\n"
                                                    "Application will be terminated now"),
                                  QMessageBox.Ok)
        self.parent.close()

