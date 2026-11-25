from jal.constants import Setup
import sqlite3
import logging
import os
from dateutil import tz
from datetime import datetime
import shutil
from tempfile import TemporaryDirectory, mkstemp
import tarfile
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from jal.db.db import JalDB
from jal.db.settings import JalSettings


# ------------------------------------------------------------------------------
class JalBackup:
    tmp_prefix = 'jal_'
    backup_label = 'JAL SQLITE backup. Created: '
    date_fmt = '%Y/%m/%d %H:%M:%S%z'
    sqlite_header = b'SQLite format 3\x00'

    def __init__(self, parent):
        self.parent = parent
        self.file = JalSettings.path(JalSettings.PATH_DB_FILE)
        self.backup_name = None
        self._backup_label_date = ''

    def tr(self, text):
        return QApplication.translate("JalBackup", text)

    # Function returns True if all of following conditions are met (otherwise returns False):
    # - backup contains exactly the required files, each once and each a regular file (no links)
    # - backup contains file 'label' with valid content
    # - backup file 'jal.sqlite' starts with SQLite header
    def validate_backup(self):
        try:
            with tarfile.open(self.backup_name, "r:gz") as tar:
                members = self._backup_members(tar)
                if members is None:
                    return False

                # Check correctness of backup label
                label_content = tar.extractfile(members['label']).read().decode("utf-8")
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

                if tar.extractfile(members[Setup.DB_PATH]).read(len(self.sqlite_header)) != self.sqlite_header:
                    logging.warning(self.tr("Backup doesn't contain SQLite database"))
                    return False
        except (tarfile.TarError, OSError, UnicodeDecodeError) as e:
            logging.warning(self.tr("Can't read backup file: ") + str(e))
            return False
        return True

    # Returns {name: member} if archive holds exactly the expected regular files, None otherwise
    def _backup_members(self, tar):
        expected = [Setup.DB_PATH, 'label']
        members = tar.getmembers()
        names = [x.name for x in members]
        if sorted(names) != sorted(expected) or not all(x.isfile() for x in members):
            logging.debug("Backup content expected: " + str(expected) +
                          "\nBackup content actual: " + str([(x.name, x.type) for x in members]))
            return None
        return {x.name: x for x in members}

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
        tmp_file = None
        try:
            with tarfile.open(self.backup_name, "r:gz") as tar:
                members = self._backup_members(tar)
                if members is None:
                    logging.warning(self.tr("Wrong format of backup file"))
                    return False
                source = tar.extractfile(members[Setup.DB_PATH])
                header = source.read(len(self.sqlite_header))
                if header != self.sqlite_header:
                    logging.warning(self.tr("Backup doesn't contain SQLite database"))
                    return False
                # Temporary file is created next to the database to allow atomic replace
                fd, tmp_file = mkstemp(prefix=self.tmp_prefix, dir=os.path.dirname(os.path.abspath(self.file)))
                with os.fdopen(fd, 'wb') as target:
                    target.write(header)
                    shutil.copyfileobj(source, target)
            os.replace(tmp_file, self.file)
        except (tarfile.TarError, OSError) as e:
            if tmp_file is not None and os.path.exists(tmp_file):
                os.remove(tmp_file)
            logging.warning(self.tr("Failed to restore backup file") + ": " + str(e))
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
        if not self.validate_backup():
            logging.error(self.tr("Wrong format of backup file"))
            return

        JalDB.connection().close()
        if not self.do_restore():
            JalDB.connection().open()   # Original database is intact - continue with it
            return
        logging.info(self.tr("Backup restored from: ") + self.backup_name + self._backup_label_date
                     + self.tr(" into ") + self.file)

        QMessageBox().information(self.parent, self.tr("Data restored"),
                                  self.tr("Database was loaded from the backup.\n") +
                                  self.tr("You should restart application to apply changes\n"
                                                    "Application will be terminated now"),
                                  QMessageBox.Ok)
        self.parent.close()

