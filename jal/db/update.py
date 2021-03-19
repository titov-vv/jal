import logging
from datetime import datetime
from jal.db.helpers import db_connection, executeSQL, get_asset_name
from jal.widgets.helpers import g_tr


# ----------------------------------------------------------------------------------------------------------------------
class JalDB():
    def __init__(self):
        pass

    def commit(self):
        db_connection().commit()

    def update_quote(self, asset_id, timestamp, quote):
        if (timestamp is None) or (quote is None):
            return
        old_id = 0
        query = executeSQL("SELECT id FROM quotes WHERE asset_id = :asset_id AND timestamp = :timestamp",
                           [(":asset_id", asset_id), (":timestamp", timestamp)])
        if query.next():
            old_id = query.value(0)
        if old_id:
            executeSQL("UPDATE quotes SET quote=:quote WHERE id=:old_id", [(":quote", quote), (":old_id", old_id), ])
        else:
            executeSQL("INSERT INTO quotes(timestamp, asset_id, quote) VALUES (:timestamp, :asset_id, :quote)",
                       [(":timestamp", timestamp), (":asset_id", asset_id), (":quote", quote)])
        logging.info(g_tr('JalDB', "Quote loaded: ") +
                     f"{get_asset_name(asset_id)} @ {datetime.utcfromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')} = {quote}")