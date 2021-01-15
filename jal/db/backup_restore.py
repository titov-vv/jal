from jal.constants import Setup
import sqlite3
import pandas as pd
import math
import logging
import os
from datetime import datetime
from tempfile import TemporaryDirectory
import tarfile

from PySide2.QtWidgets import QFileDialog, QMessageBox
from jal.ui_custom.helpers import g_tr


# ------------------------------------------------------------------------------
class JalBackup:
    tmp_prefix = 'jal_'
    backup_label = 'JAL backup. Created: '
    backup_list = ["settings", "tags", "categories", "agents", "assets", "accounts", "countries", "corp_actions",
                   "dividends", "trades", "actions", "action_details", "transfers", "transfer_notes", "quotes",
                   "map_peer", "map_category"]

    def __init__(self, parent, db_file):
        self.parent = parent
        self.file = db_file
        self.backup_name = None
        self._backup_label_date = ''

    def clean_db(self):
        db = sqlite3.connect(self.file)
        cursor = db.cursor()

        cursor.executescript("DELETE FROM ledger;"
                             "DELETE FROM ledger_sums;"
                             "DELETE FROM sequence;")
        db.commit()

        cursor.execute("DROP TRIGGER IF EXISTS keep_predefined_categories")
        for table in JalBackup.backup_list:
            cursor.execute(f"DELETE FROM {table}")
        db.commit()

        logging.info(g_tr('JalBackup', "DB cleanup was completed"))
        db.close()

    def validate_backup(self):
        with tarfile.open(self.backup_name, "r:gz") as tar:
            if 'label' in tar.getnames():
                label_content = tar.extractfile('label').read().decode("utf-8")
                logging.debug("Backup file label: " + label_content)
                if label_content[:len(self.backup_label)] == self.backup_label:
                    self._backup_label_date = label_content[len(self.backup_label):]
                    return True
                else:
                    return False

    def do_backup(self):
        db = sqlite3.connect(self.file)
        with TemporaryDirectory(prefix=self.tmp_prefix) as tmp_path:
            with open(tmp_path + os.sep + 'label', 'w') as label:
                label.write(f"{self.backup_label}{datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
            for table in JalBackup.backup_list:
                data = pd.read_sql_query(f"SELECT * FROM {table}", db)
                data.to_csv(f"{tmp_path}/{table}.csv", sep="|", header=True, index=False)
            with tarfile.open(self.backup_name, "w:gz") as tar:
                tar.add(tmp_path, arcname='')
        db.close()

    def do_restore(self):
        db = sqlite3.connect(self.file)
        cursor = db.cursor()

        with TemporaryDirectory(prefix=self.tmp_prefix) as tmp_path:
            with tarfile.open(self.backup_name, "r:gz") as tar:
                tar.extractall(tmp_path)
            for table in JalBackup.backup_list:
                data = pd.read_csv(f"{tmp_path}/{table}.csv", sep='|', keep_default_na=False)
                for column in data:
                    if data[column].dtype == 'float64':  # Correct possible mistakes due to float data type
                        if table == 'transfers' and column == 'rate':  # But rate is calculated value with arbitrary precision
                            continue
                        data[column] = data[column].round(int(-math.log10(Setup.CALC_TOLERANCE)))
                data.to_sql(name=table, con=db, if_exists='append', index=False, chunksize=100)

        cursor.execute("CREATE TRIGGER keep_predefined_categories "
                       "BEFORE DELETE ON categories FOR EACH ROW WHEN OLD.special = 1 "
                       "BEGIN SELECT RAISE(ABORT, \"Can't delete predefined category\"); END;")
        db.commit()
        db.close()

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
        self.parent.closeDatabase()

        if not self.validate_backup():
            logging.error(g_tr('JalBackup', "Wrong format of backup file"))
            return

        self.clean_db()
        self.do_restore()
        logging.info(g_tr('JalBackup', "Backup restored from: ") + self.backup_name + self._backup_label_date
                     + g_tr('JalBackup', " into ") + self.file)

        QMessageBox().information(self.parent, g_tr('JalBackup', "Data restored"),
                                  g_tr('JalBackup', "Database was loaded from the backup.\n") +
                                  g_tr('JalBackup', "You should restart application to apply changes\n"
                                                    "Application will be terminated now"),
                                  QMessageBox.Ok)
        self.parent.close()

