import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import pinned_tz
from jal.db.settings import JalSettings
from jal.data_import.receipt_api.ru_fns import ReceiptRuFNS

FNS_URL = "https://irkkt-mobile.nalog.ru:8888/v2/"


class _Answer:
    def __init__(self, data):
        self.status_code = 200
        self.text = json.dumps(data, ensure_ascii=False)


# Answers of FNS recorded on 2026-10-13 for a real receipt (100.00 RUB paid to a mobile operator), with the buyer's
# contacts and the numbers that identify the receipt replaced
class _RecordedFNS:
    def __init__(self, recorded: dict):
        self.headers = {}
        self.posted = []
        self._recorded = recorded

    def get(self, url):
        if url == FNS_URL + "tickets":      # the authorization check
            return _Answer([])
        assert url == FNS_URL + "tickets/" + self._recorded['found']['id']
        return _Answer(self._recorded['loaded'])

    def post(self, url, data=None):
        assert url == FNS_URL + "ticket"
        self.posted.append(data)
        return _Answer(self._recorded['found'])


@pytest.fixture
def fns_receipt(prepare_db, data_path):
    with open(data_path + "fns_receipt.json", 'r', encoding='utf-8') as f:
        recorded = json.load(f)
    JalSettings().setValue('RuTaxSessionId', "session")      # a stored session: no login dialog
    receipt = ReceiptRuFNS(qr_text=recorded['qr'])
    receipt.web_session = _RecordedFNS(recorded)
    return receipt


def test_fns_receipt_is_read_as_the_paper_states_it(fns_receipt):
    loaded = []
    fns_receipt.slip_load_ok.connect(lambda: loaded.append(True))
    assert fns_receipt.activate_session()
    fns_receipt.query_slip()
    assert loaded == [True]
    assert fns_receipt.web_session.posted == \
           ['{"qr": "t=20260824T123300&s=100.00&fn=7380440900000000&i=100001&fp=1234567890&n=1"}']
    assert fns_receipt.shop_name() == 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "Т2 МОБАЙЛ"'
    assert fns_receipt.number() == "7380440900000000:100001:1234567890"
    with pinned_tz("Europe/Moscow"):      # the till's clock, which the QR code states as 12:33
        assert fns_receipt.datetime().toString("yyyy-MM-dd HH:mm") == "2026-08-24 12:33"
    lines = fns_receipt.slip_lines()
    assert [(x['name'], x['quantity'], x['unit_price'], x['amount']) for x in lines] == \
           [("Аванс за услуги связи 70000000000", Decimal('1'), Decimal('100'), Decimal('-100'))]
    assert all(type(x[key]) is Decimal for x in lines for key in ('quantity', 'unit_price', 'amount'))
    assert -sum(x['amount'] for x in lines) == fns_receipt.amount == Decimal('100.00')
