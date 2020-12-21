#!/usr/bin/python

import sys
import sqlite3

TARGET_SCHEMA = 12

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: update_db_schema.py <db_file_name>")
        exit()
    db_file = sys.argv[1]

    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    try:
        cursor.execute("SELECT value FROM settings WHERE name='SchemaVersion'")
    except:
        print("Can't get current schema version from database")
        exit()

    current_schema = cursor.fetchone()[0]
    print(f"Current schema: {current_schema}")
    print(f"Updating to: {TARGET_SCHEMA}")

    for step in range(current_schema, TARGET_SCHEMA):
        print(f"Appling delta {step}->{step+1}")
        delta_name = f"delta_schema_{step+1}.sql"
        with open(delta_name) as queryfile:
            cursor.executescript(queryfile.read())

    db.close()
    print("Schema update completed")
