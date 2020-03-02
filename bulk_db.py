#!/usr/bin/python

from constants import *
import sqlite3
import pandas as pd
import math
#------------------------------------------------------------------------------
backup_list = ["settings", "tags", "categories", "agents", "assets", "accounts", "corp_actions",
               "dividends", "trades", "actions", "action_details", "transfers", "transfer_notes", "quotes"]
#------------------------------------------------------------------------------
def MakeBackup(db_file, backup_path):
    db = sqlite3.connect(db_file)

    for table in backup_list:
        data = pd.read_sql_query(f"SELECT * FROM {table}", db)
        data.to_csv(f"{backup_path}/{table}.csv", sep="|", header=True, index=False)

    db.close()
    print("Backup saved in: " + backup_path)

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

    for table in backup_list:
        data = pd.read_csv(f"{restore_path}/{table}.csv", sep='|')
        for column in data:
            if data[column].dtype == 'float64':   # Correct possible mistakes due to float data type
                if table == 'transfers' and column == 'rate':  # But rate is calculated value with arbitrary precision
                    continue
                data[column] = data[column].round(int(-math.log10(CALC_TOLERANCE)))
        data.to_sql(name=table, con=db, if_exists='append', index=False, chunksize=100)

    db.commit()
    db.close()

def loadDbFromSQL(db_file, sql_file):
    print("Load SQL-script: ", sql_file)
    print("Into database:   ", db_file)

    with open(sql_file, 'r') as sql_file:
        sql_text = sql_file.read()
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    cursor.executescript(sql_text)
    db.commit()
    db.close()
    print("DB script loaded")

