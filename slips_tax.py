import uuid
import json
import logging
import requests

from datetime import datetime
from DB.helpers import readSQL
from CustomUI.helpers import g_tr


class SlipsTaxAPI:
    def __init__(self, db):
        self.db = db

    def get_ru_tax_session(self):
        return readSQL(self.db, "SELECT value FROM settings WHERE name='RuTaxSessionId'")

    def get_slip(self, timestamp, amount, fn, fd, fp, slip_type):
        date_time = datetime.fromtimestamp(timestamp).strftime('%Y%m%dT%H%M%S')

        session_id = self.get_ru_tax_session()
        if session_id == '':
            logging.warning(g_tr('ImportSlipDialog', "No Russian Tax SessionId available"))
            return
        s = requests.Session()
        s.headers['ClientVersion'] = '2.9.0'
        s.headers['Device-Id'] = str(uuid.uuid1())
        s.headers['Device-OS'] = 'Android'
        s.headers['sessionId'] = session_id
        s.headers['Content-Type'] = 'application/json; charset=UTF-8'
        s.headers['Accept-Encoding'] = 'gzip'
        s.headers['User-Agent'] = 'okhttp/4.2.2'
        payload = '{' + f'"qr": "t={date_time}&s={amount:.2f}&fn={fn}&i={fd}&fp={fp}&n={slip_type}"' + '}'
        response = s.post('https://irkkt-mobile.nalog.ru:8888/v2/ticket', data=payload)
        if response.status_code != 200:
            logging.error(
                g_tr('ImportSlipDialog', "Get ticket id failed with response ") +
                f"{response}/{response.text} for {payload}")
            return
        logging.info(g_tr('ImportSlipDialog', "Slip found: " + response.text))
        json_content = json.loads(response.text)
        url = "https://irkkt-mobile.nalog.ru:8888/v2/tickets/" + json_content['id']
        response = s.get(url)
        if response.status_code != 200:
            logging.error(g_tr('ImportSlipDialog', "Get ticket failed with response ") + f"{response}/{response.text}")
            return
        logging.info(g_tr('ImportSlipDialog', "Slip loaded: " + response.text))
        slip_json = json.loads(response.text)
        return slip_json