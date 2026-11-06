import pytest
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_quotes, create_trades, create_actions, create_coupons, \
    create_dividends, create_transfers, create_corporate_actions, symbol_id_for
from tests.test_taxes_crypto import create_crypto_scenario
from jal.constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, CorporateActionType
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, TaxStatus, AssetPayment, AssetIncome, ChainAction, \
    CorporateAction, IncomeSpending, Trade, Transfer, Conversion, Swap, Bridge

NOT, TAX, BASE = TaxStatus.NotTaxable, TaxStatus.Taxable, TaxStatus.BaseImpacting


# ----------------------------------------------------------------------------------------------------------------------
# Every kind of operation answers for itself, and every subtype it knows has an explicit entry
def test_every_subtype_has_a_tax_status():
    classes = (IncomeSpending, AssetPayment, AssetIncome, Trade, Transfer, CorporateAction, Conversion, Swap, Bridge,
               ChainAction)
    assert all(x.taxable is not LedgerTransaction.taxable for x in classes)
    for cls in (AssetPayment, AssetIncome, ChainAction):
        assert set(cls.TaxStatusBySubtype) == set(cls.subtype_names()) - {cls.NA}, cls.__name__
    action_types = {v for k, v in vars(CorporateActionType).items() if not k.startswith('_')}
    assert set(CorporateAction.TaxStatusBySubtype) == action_types


# (otype, trade number or description, status) of every operation, in the order they were stored
def _statuses() -> list:
    statuses = []
    query = JalDB._exec("SELECT otype, id FROM operations ORDER BY id")
    while query.next():
        otype, oid = query.value(0), query.value(1)
        operation = LedgerTransaction.get_operation(otype, oid)
        key = operation.number() if otype == LedgerTransaction.Trade else operation.description()
        statuses.append((otype, key, operation.taxable()))
    return statuses


# The crypto scenario of the tax report tests: buys and the delisting are no event, every disposal and the reward are
def test_crypto_scenario_statuses(prepare_db_taxes):
    create_crypto_scenario()

    statuses = _statuses()
    trades = {x[1]: x[2] for x in statuses if x[0] == LedgerTransaction.Trade}
    assert trades == {"buy-ETH": NOT, "buy-UNI": NOT, "buy-STK": NOT, "buy-DLS": NOT,
                      "sell-ETH": TAX, "sell-WETH": TAX, "sell-SOL": TAX, "sell-STK": TAX}
    others = sorted((x[0], x[2]) for x in statuses if x[0] != LedgerTransaction.Trade)
    assert others == [(LedgerTransaction.CorporateAction, NOT),     # Delisting
                      (LedgerTransaction.Conversion, TAX),
                      (LedgerTransaction.Swap, TAX), (LedgerTransaction.Swap, TAX),   # both treatments
                      (LedgerTransaction.AssetIncome, TAX)]         # staking reward


# Stocks, payments, cash lines and the corporate actions decided by their results
def test_stock_account_statuses(prepare_db_taxes):
    JalAccountCreator(currency_id=2, number='U2', name='Second', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()                                   # 2
    create_assets([("AAA", "Parent", "US0000000301", 2, PredefinedAsset.Stock, 'us'),                       # 4
                   ("BBB", "Spun", "US0000000302", 2, PredefinedAsset.Stock, 'us'),                         # 5
                   ("SHT", "Shorted", "US0000000303", 2, PredefinedAsset.Stock, 'us'),                      # 6
                   ("BND", "Bond", "US0000000304", 2, PredefinedAsset.Bond, 'us'),                          # 7
                   ("CCC", "Merged into", "US0000000305", 2, PredefinedAsset.Stock, 'us'),                  # 8
                   ("DUST", "Dust coin", "", 2, PredefinedAsset.Crypto, 0)])                                # 9
    create_quotes(9, 2, [(d2t(240101), 0.01)])
    create_trades(1, [(d2t(240102), d2t(240104), 4, 100, 10, 1, "buy-AAA"),
                      (d2t(240102), d2t(240104), 6, -10, 20, 1, "short-SHT"),
                      (d2t(240301), d2t(240303), 6, 10, 15, 1, "cover-SHT"),
                      (d2t(240102), d2t(240104), 7, 2, 1000, 1, "buy-BND"),
                      (d2t(240102), d2t(240104), 8, 10, 30, 0, "buy-CCC")])
    create_coupons([(d2t(240102), 1, 7, -5.0, 0, "PURCHASE ACCRUED INT", "buy-BND"),
                    (d2t(240601), 1, 7, 25.0, 0, "BOND COUPON PAYMENT", "")])
    create_dividends([(d2t(240501), 1, 4, 10.0, 1.0, "AAA CASH DIVIDEND")])
    LedgerTransaction.create_new(LedgerTransaction.AssetPayment, {
        'timestamp': d2t(240502), 'type': AssetPayment.DepositaryFee, 'account_id': 1, 'symbol_id': symbol_id_for(4),
        'amount': '-1', 'tax': '0', 'note': 'AAA ADR Fee'})
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': d2t(240503), 'type': AssetIncome.DustAttack, 'account_id': 1, 'symbol_id': symbol_id_for(9),
        'amount': '0.001', 'tax': '0', 'note': 'dust'})
    create_actions([(d2t(240504), 1, 1, [(PredefinedCategory.Interest, 2.0, "CREDIT INT")]),
                    (d2t(240505), 1, 1, [(PredefinedCategory.Spending, -3.0, "Office")]),
                    (d2t(240506), 1, 1, [(PredefinedCategory.Spending, -3.0, "Office"),
                                         (PredefinedCategory.Fees, -1.0, "Monthly fee")])])
    create_corporate_actions(1, [(d2t(240601), CorporateAction.Split, 4, 100, "Split", [(4, 200, 1.0)]),
                                 (d2t(240701), CorporateAction.SpinOff, 4, 200, "Spin-off",
                                  [(4, 200, 0.8), (5, 20, 0.2)]),
                                 (d2t(240801), CorporateAction.Merger, 8, 10, "Merger with cash",
                                  [(8, 5, 1.0), (2, 25, 0.0)])])
    create_transfers([(d2t(240901), 1, 50, 2, 50, 4)])
    Ledger().rebuild(from_timestamp=0)

    statuses = _statuses()
    trades = {x[1]: x[2] for x in statuses if x[0] == LedgerTransaction.Trade}
    assert trades == {"buy-AAA": NOT, "short-SHT": NOT, "cover-SHT": TAX, "buy-BND": NOT, "buy-CCC": NOT}
    payments = sorted(x[2] for x in statuses if x[0] == LedgerTransaction.AssetPayment)
    assert payments == [TAX, TAX, BASE, BASE]         # coupon, dividend; accrued interest paid, depositary fee
    assert [x[2] for x in statuses if x[0] == LedgerTransaction.AssetIncome] == [NOT]   # dust
    assert [x[2] for x in statuses if x[0] == LedgerTransaction.IncomeSpending] == [TAX, NOT, TAX]   # interest; spending only; spending + fee
    actions = {x[1].split(":")[0]: x[2] for x in statuses if x[0] == LedgerTransaction.CorporateAction}
    assert actions == {"Split": NOT, "Spin-off": TAX, "Merger": TAX}   # new stock / cash end a lot
    assert [x[2] for x in statuses if x[0] == LedgerTransaction.Transfer] == [NOT]


# A subtype nobody mapped is refused rather than passed as no event
def test_unknown_subtype_raises(prepare_db_taxes):
    create_crypto_scenario()
    reward = LedgerTransaction.get_operation(LedgerTransaction.AssetIncome,
                                             JalDB._read("SELECT oid FROM asset_incomes"))
    reward._subtype = 99
    with pytest.raises(ValueError):
        reward.taxable()


# A lost position realizes nothing for tax: no rule lets that loss be claimed
@pytest.mark.parametrize("action", [CorporateAction.Delisting, CorporateAction.WriteOff])
def test_lost_position_is_no_event(prepare_db_taxes, action):
    create_assets([("STK", "Lost stock", "US0000000401", 2, PredefinedAsset.Stock, 'us')])   # ID 4
    create_trades(1, [(d2t(240102), d2t(240104), 4, 10, 10, 0, "buy-STK")])
    create_corporate_actions(1, [(d2t(240601), action, 4, 10, "Gone", [])])
    Ledger().rebuild(from_timestamp=0)

    assert [x[2] for x in _statuses() if x[0] == LedgerTransaction.CorporateAction] == [NOT]


# The account list of the tax report is the SQL twin of taxable(): investing accounts with an event of the year
def test_taxable_accounts_follow_taxable(prepare_db_taxes):
    JalAccountCreator(currency_id=2, number='B1', name='Bank', investing=0, organization=1,
                      account_type=PredefinedAccountType.Bank).commit()                                     # 2
    JalAccountCreator(currency_id=2, number='Q1', name='Quiet', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()                                   # 3
    JalAccountCreator(currency_id=2, number='S1', name='Spin', investing=1, organization=1,
                      account_type=PredefinedAccountType.Broker).commit()                                   # 4
    create_crypto_scenario()   # account 1, 2025; assets 4-9
    create_actions([(d2t(250301), 2, 1, [(PredefinedCategory.Interest, 2.0, "Savings interest")])])
    create_trades(3, [(d2t(250102), d2t(250104), 8, 5, 10, 0, "quiet-buy")])
    create_transfers([(d2t(250103), 3, 5, 1, 5, 8)])
    create_trades(4, [(d2t(241202), d2t(241204), 8, 10, 10, 0, "spin-buy")])
    create_corporate_actions(4, [(d2t(250401), CorporateAction.SpinOff, 8, 10, "Spin-off",
                                  [(8, 10, 0.9), (9, 2, 0.1)])])
    Ledger().rebuild(from_timestamp=0)

    expected = set()
    query = JalDB._exec("SELECT o.otype, o.id FROM operations AS o")
    while query.next():
        operation = LedgerTransaction.get_operation(query.value(0), query.value(1))
        investing = JalDB._read("SELECT investing FROM accounts WHERE id=:id", [(":id", operation.account().id())])
        if operation.taxable() != NOT and d2t(250101) <= operation.timestamp() < d2t(260101) and investing:
            expected.add(operation.account().id())
    assert expected == {1, 4}
    assert [x.id() for x in JalAccount.get_taxable_accounts(d2t(250101), d2t(260101))] == sorted(expected)
