import json
import logging

from jal.widgets.helpers import g_tr
# -----------------------------------------------------------------------------------------------------------------------


class Statement:
    S_TIMESTAMP = "from"
    E_TIMESTAMP = "to"
    ACCOUNTS = "accounts"
    ASSETS = "assets"
    TRADES = "trades"
    TRANSFERS = "transfers"

    def __init__(self):
        self._data = {}

    def load(self, filename: str) -> None:
        self._data = {}
        try:
            with open(filename, 'r') as exchange_file:
                try:
                    self._data = json.load(exchange_file)
                except json.JSONDecodeError:
                    logging.error(g_tr('Statement', "Failed to read JSON from file: ") + filename)
        except Exception as err:
            logging.error(g_tr('Statement', "Failed to read file: ") + err)

