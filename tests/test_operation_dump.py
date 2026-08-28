# Tests for LedgerTransaction.dump(): it renders the raw operation record for a human reader - ids into names and
# timestamps into dates - and it may never alter the operation it dumps, as it builds the text of every LedgerError
# and is therefore called on operations that are still being processed.
import re

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, symbol_id_for, create_stocks, create_trades, create_actions, \
    create_corporate_actions
from jal.db.db import JalDB
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.peer import JalPeer
from jal.widgets.helpers import ts2dt
from jal.db.operations import LedgerTransaction, AssetPayment, CorporateAction


def _last(table: str) -> int:
    return JalDB._read(f"SELECT MAX(oid) FROM {table}")


def _prepare_account():
    JalAccountCreator(currency_id=2, number='U1', name='Acc', investing=1, organization=1).commit()
    create_stocks([('AAPL', 'Apple Inc.')], currency_id=2)  # asset id 4


def test_dump_doesnt_modify_operation(prepare_db):
    _prepare_account()
    create_trades(1, [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])
    operation = LedgerTransaction.get_operation(LedgerTransaction.Trade, _last("trades"))

    dumped = operation.dump()
    assert operation._data['account_id'] == 1        # the operation keeps its own values...
    assert operation._data['timestamp'] == d2t(220201)
    assert operation.dump() == dumped                # ... so a second dump has the same record to render


def test_dump_renders_ids_and_timestamps(prepare_db):
    _prepare_account()
    create_trades(1, [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])
    operation = LedgerTransaction.get_operation(LedgerTransaction.Trade, _last("trades"))

    dumped = operation.dump()
    assert "'account_id': 'Acc'" in dumped
    assert "'symbol_id': 'AAPL'" in dumped
    assert f"'timestamp': '{ts2dt(d2t(220201))}'" in dumped
    assert f"'settlement': '{ts2dt(d2t(220203))}'" in dumped    # a timestamp that isn't named one


def test_dump_renders_payment_type_and_ex_date(prepare_db):
    _prepare_account()
    data = {'timestamp': d2t(220301), 'ex_date': d2t(220215), 'type': AssetPayment.Dividend, 'account_id': 1,
            'symbol_id': symbol_id_for(4, 2), 'amount': '5', 'tax': '0.5', 'note': ''}
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment, data)
    operation = LedgerTransaction.get_operation(LedgerTransaction.AssetPayment, _last("asset_payments"))

    dumped = operation.dump()
    assert f"'ex_date': '{ts2dt(d2t(220215))}'" in dumped
    assert f"'type': '{operation.name()}'" in dumped
    assert "'symbol_id': 'AAPL'" in dumped


def test_dump_renders_alt_currency(prepare_db):
    _prepare_account()
    JalPeer(data={'name': 'Shop', 'parent': 0}, create=True)
    create_actions([(d2t(220101), 1, 1, [(4, 100.0)])])
    operation = LedgerTransaction.get_operation(LedgerTransaction.IncomeSpending, _last("actions"))
    JalDB._exec(f"UPDATE actions SET alt_currency_id=1 WHERE oid={operation.oid()}")
    operation = LedgerTransaction.get_operation(LedgerTransaction.IncomeSpending, _last("actions"))

    assert f"'currency': '{JalAsset(1).symbol()}'" in operation.dump()   # 'alt_currency_id' holds an asset id


def test_dump_leaves_no_bare_id(prepare_db):
    _prepare_account()
    create_trades(1, [(d2t(220201), d2t(220203), 4, 10.0, 100.0, 1.0)])
    create_corporate_actions(1, [(d2t(220401), CorporateAction.Split, 4, 10.0, '', [(4, 20.0, 1.0)])])
    operations = [LedgerTransaction.get_operation(LedgerTransaction.Trade, _last("trades")),
                  LedgerTransaction.get_operation(LedgerTransaction.CorporateAction, _last("asset_actions"))]
    for operation in operations:
        # Nothing that names an id or a timestamp may be left as the number it is stored as
        assert not re.search(r"'\w*(_id|timestamp|settlement|ex_date)': \d", operation.dump()), operation.dump()
