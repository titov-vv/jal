import sqlite3, time, datetime
import pandas as pd
import numpy as np
import math, sys, getopt
#------------------------------------------------------------------------------
def convert_data_source(val):
    try:
        src = int(val)
    except ValueError:
        src = -1
    return src

def convert_with_null(val):
    val = val.replace('\xa0', '')
    try:
        res = int(val)
    except ValueError:
        res = np.NaN
    return res

def convert_sum(val):
    val = val.replace('\xa0', '')
    val = val.replace(',', '.')
    if val == '':
        res = 0
    else:
        res = float(val)
    return res

def convert_webid(val):
    res = val.replace('\xa0', '')
    if res == '0':
        res = ''
    return res

def convert_datetime(val):
    if val == '':
        return 0
    if val == '01.01.0001 0:00:00':
        return 0
    return time.mktime(datetime.datetime.strptime(val, "%d.%m.%Y %H:%M:%S").timetuple())
#------------------------------------------------------------------------------
def import_1c(db_file, data_path):
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    cursor.executescript("DELETE FROM quotes;"
                         "DELETE FROM transfers;"
                         "DELETE FROM action_details;"
                         "DELETE FROM actions;"
                         "DELETE FROM trades;"
                         "DELETE FROM dividends;"
                         "DELETE FROM accounts;"
                         "DELETE FROM actives;"
                         "DELETE FROM agents;"
                         "DELETE FROM categories;"
                         "DELETE FROM tags;"
                         "DELETE FROM data_sources;"
                         "DELETE FROM active_types;"
                         "DELETE FROM account_types;"
                         "VACUUM;")
    print("DB cleanup completed")
    data = pd.read_csv(data_path + "data_account_types.csv", sep='|', encoding='cp1251', dtype = {'id':int, 'name':str})
    data.to_sql(name="account_types", con = db, if_exists='append', index=False, chunksize=100)

    data = pd.read_csv(data_path + "data_actives_types.csv", sep='|', encoding='cp1251', dtype = {'id':int, 'name':str})
    data.to_sql(name="active_types", con = db, if_exists='append', index=False, chunksize=100)

    data = pd.read_csv(data_path + "data_sources.csv", sep='|', encoding='cp1251', dtype = {'id':int, 'name':str})
    data = data.append({'id': -1, 'name': 'None'}, ignore_index=True)
    data.to_sql(name="data_sources", con = db, if_exists='append', index=False, chunksize=100)

    data = pd.read_csv(data_path + "data_tags.csv", sep='|', encoding='cp1251', dtype = {'id':int, 'tag':str})
    data.to_sql(name="tags", con = db, if_exists='append', index=False, chunksize=100)

    data = pd.read_csv(data_path + "data_categories.csv", sep='|', encoding='cp1251',
                       dtype = {'id':int, 'pid':int, 'name':str, 'often':int, 'special':int})
    data.to_sql(name="categories", con = db, if_exists='append', index=False, chunksize=100)

    data = pd.read_csv(data_path + "data_agents.csv", sep='|', encoding='cp1251', thousands='\xa0',
                       dtype = {'id':int, 'pid':int, 'name':str, 'location':str})
    data.to_sql(name="agents", con = db, if_exists='append', index=False, chunksize=100)

    data = pd.read_csv(data_path + "data_actives.csv", sep='|', encoding='cp1251',
                       dtype = {'id':int, 'name':str, 'type_id':int, 'full_name':str, 'isin':str},
                       converters = {'src_id': convert_data_source, 'web_id': convert_webid})
    data.to_sql(name="actives", con = db, if_exists='append', index=False, chunksize=100)

    data = pd.read_csv(data_path + "data_accounts.csv", sep='|', encoding='cp1251',
                       dtype = {'id':int, 'name':str, 'type_id':int, 'number':str, 'currency_id':int, 'active':int},
                       converters = {'reconciled_on': convert_datetime, 'organization_id': convert_with_null})
    data.to_sql(name="accounts", con = db, if_exists='append', index=False, chunksize=100)
    print("Common data loaded")
    data = pd.read_csv(data_path + "actions_dividends.csv", sep='|', encoding='cp1251',
                       dtype = {'name':str, 'account_id':int, 'sec_id':int, 'note':str, 'note_tax':str, 'number': str},
                       converters = {'timestamp': convert_datetime, 'sum': convert_sum, 'sum_tax': convert_sum})
    data.rename(columns={'sec_id': 'active_id'}, inplace=True)
    data.to_sql(name="dividends", con = db, if_exists='append', index=False, chunksize=100)
    print("Dividends loaded")
    data = pd.read_csv(data_path + "actions_trades.csv", sep='|', encoding='cp1251',
                       dtype = {'type':int, 'number':str, 'account_id':int, 'sec_id':int},
                       converters = {'timestamp': convert_datetime, 'settlement': convert_datetime,
                                     'quantity': convert_sum, 'price': convert_sum, 'coupon': convert_sum,
                                     'fee_broker': convert_sum, 'fee_exchange': convert_sum, 'sum': convert_sum})
    data.rename(columns={'sec_id': 'active_id'}, inplace=True)
    data.rename(columns={'quantity': 'qty'}, inplace=True)
    data.to_sql(name="trades", con = db, if_exists='append', index=False, chunksize=100)
    print("Trades loaded")
    data = pd.read_csv(data_path + "actions_debit_credit.csv", sep='|', encoding='cp1251', thousands='\xa0',
                       dtype = {'type':int, 'id':int, 'account_id':int, 'peer_id':int, 'category_id':int, 'note':str},
                       converters = {'timestamp': convert_datetime, 'sum': convert_sum, 'sum_a': convert_sum,
                                     'currency_id': convert_with_null, 'tag_id': convert_with_null})
    data["new_id"] = np.nan
    details = pd.read_csv(data_path + "actions_splits.csv", sep='|', encoding='cp1251', thousands='\xa0',
                       dtype = {'pid':int, 'type':int, 'category_id':int},
                       converters = {'sum': convert_sum, 'sum_a': convert_sum, 'tag_id': convert_with_null})
    data = data.merge(details, how='left', left_on='id', right_on='pid')
    last_id = 0
    new_id = 0
    for index, row in data.iterrows():
        if (last_id != row['id']):  #insert new action line
            cursor.execute("INSERT INTO actions(timestamp, account_id, peer_id, alt_currency_id) VALUES(?, ?, ?, ?)",
                           (row['timestamp'], row['account_id'], row['peer_id'], row['currency_id']))
            new_id = cursor.lastrowid
            data.loc[index, 'new_id'] = int(new_id)
            last_id = row['id']
        if math.isnan(row['sum_y']):    #insert details from main part if no split
            cursor.execute("INSERT INTO action_details(pid, type, category_id, tag_id, sum, alt_sum, note) "
                           "VALUES(?, ?, ?, ?, ?, ?, ?)",
                           (new_id, row['type_x'], row['category_id_x'], row['tag_id_x'],
                            row['sum_x'], row['sum_a_x'], row['note_x']))
        else:
            cursor.execute("INSERT INTO action_details(pid, type, category_id, tag_id, sum, alt_sum, note) "
                           "VALUES(?, ?, ?, ?, ?, ?, ?)",
                           (new_id, row['type_y'], row['category_id_y'], row['tag_id_y'],
                            row['sum_y'], row['sum_a_y'], row['note_y']))
    print("Actions loaded")
    lookup = data[['id', 'new_id']]
    links = pd.read_csv(data_path + "actions_transfers.csv", sep='|', encoding='cp1251', thousands='\xa0',
                       dtype = {'from_id':int, 'to_id':int},
                       converters = {'fee_id': convert_with_null})
    links = links.merge(lookup, how='left', left_on='from_id', right_on="id")
    links = links.merge(lookup, how='left', left_on='to_id', right_on="id")
    links = links.merge(lookup, how='left', left_on='fee_id', right_on="id")

    for index, row in links.iterrows():
        cursor.execute("INSERT INTO transfers(from_id, to_id, fee_id) VALUES(?, ?, ?)",
                       (row['new_id_x'], row['new_id_y'], row['new_id']))
    print("Transfers loaded")
    data = pd.read_csv(data_path + "reg_quotes.csv", sep='|', encoding='cp1251', thousands='\xa0',
                       dtype = {'active_id':int},
                       converters = {'timestamp': convert_datetime, 'quote': convert_sum})
    data.to_sql(name="quotes", con = db, if_exists='append', index=False, chunksize=100)
    print("Quotes loaded")
    db.commit()
    db.close()
    print("Import completed")
#------------------------------------------------------------------------------
if __name__ == "__main__":
    db_file = ''
    import_path = ''
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hd:s:", ["dbfile=","source="])
    except getopt.GetoptError:
        print("Import data from 1C to SQLITE database")
        print("Usage: import_1c.py -d <db_file> -s <source_directory>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("Import data from 1C to SQLITE database")
            print("Usage: import_1c.py -d <db_file> -i <source_directory>")
            sys.exit()
        elif opt in ("-d", "--dbfile"):
            db_file = arg
        elif opt in ("-s", "--source"):
            import_path = arg
    if (db_file == '' or import_path == ''):
        print("Import data from 1C to SQLITE database")
        print("Usage: import_1c.py -d <db_file> -i <source_directory>")
        sys.exit(2)
    print("Importing from:", import_path, " into DB: ", db_file)
    import_1c(db_file, import_path)
