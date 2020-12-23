from jal.constants import Setup
import sqlite3
import pandas as pd
import math
import logging

from jal.ui_custom.helpers import g_tr

# ------------------------------------------------------------------------------
backup_list = ["settings", "tags", "categories", "agents", "assets", "accounts", "countries", "corp_actions",
               "dividends", "trades", "actions", "action_details", "transfers", "transfer_notes", "quotes",
               "map_peer", "map_category"]


# ------------------------------------------------------------------------------
def MakeBackup(db_file, backup_path):
    db = sqlite3.connect(db_file)

    for table in backup_list:
        data = pd.read_sql_query(f"SELECT * FROM {table}", db)
        data.to_csv(f"{backup_path}/{table}.csv", sep="|", header=True, index=False)

    db.close()
    logging.info(g_tr('', "Backup saved in: ") + backup_path)


def RestoreBackup(db_file, restore_path):
    db = sqlite3.connect(db_file)
    cursor = db.cursor()

    cursor.executescript("DELETE FROM ledger;"
                         "DELETE FROM ledger_sums;"
                         "DELETE FROM sequence;")
    db.commit()

    # Clean DB
    for table in backup_list:
        cursor.execute(f"DELETE FROM {table}")
    db.commit()
    logging.info(g_tr('', "DB cleanup was completed"))

    for table in backup_list:
        data = pd.read_csv(f"{restore_path}/{table}.csv", sep='|')
        for column in data:
            if data[column].dtype == 'float64':  # Correct possible mistakes due to float data type
                if table == 'transfers' and column == 'rate':  # But rate is calculated value with arbitrary precision
                    continue
                data[column] = data[column].round(int(-math.log10(Setup.CALC_TOLERANCE)))
        data.to_sql(name=table, con=db, if_exists='append', index=False, chunksize=100)

    db.commit()
    db.close()
    logging.info(g_tr('', "Backup restored from: ") + restore_path + g_tr('', " into ") + db_file)


def loadDbFromSQL(db_file, sql_file):
    with open(sql_file, 'r', encoding='utf-8') as sql_file:
        sql_text = sql_file.read()
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    cursor.executescript(sql_text)
    db.commit()
    db.close()
