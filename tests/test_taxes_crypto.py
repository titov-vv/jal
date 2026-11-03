import json
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_quotes, create_trades, create_transfers, create_swaps, \
    create_conversions, create_corporate_actions, symbol_id_for, json_decimal2float
from jal.constants import PredefinedAsset, PredefinedCategory, PredefinedAccountType, SwapTreatment
from jal.db.ledger import Ledger
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset
from jal.db.operations import LedgerTransaction, AssetIncome, CorporateAction
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal

RUB, USD, EUR = 1, 2, 3


# ----------------------------------------------------------------------------------------------------------------------
# One USDT purchase carried RUB broker -> USD exchange -> EUR exchange and sold there. Accounts 2-4, asset 4.
# Purchase 100 @ 83.59 RUB + 10 RUB fee; restated to 100 USD, then to 92 EUR; 80 sold @ 0.95 EUR + 0.4 EUR fee.
def create_two_hop_lot():
    JalAccountCreator(currency_id=RUB, number='R1', name='RUB broker', investing=1, organization=1).commit()   # 2
    JalAccountCreator(currency_id=USD, number='U1', name='USD exchange', investing=1, organization=1,
                      account_type=PredefinedAccountType.CEX).commit()                                         # 3
    JalAccountCreator(currency_id=EUR, number='E1', name='EUR exchange', investing=1, organization=1,
                      account_type=PredefinedAccountType.CEX).commit()                                         # 4
    create_assets([("USDT", "Tether USD", "", USD, PredefinedAsset.Crypto, 0)])                               # 4
    t_buy, t_hop1, t_hop2, t_sell = d2t(250430), d2t(250505), d2t(250510), d2t(250530)
    create_quotes(USD, RUB, [(x, 81.0) for x in (t_buy, t_hop1, t_hop2, t_sell)])
    create_quotes(EUR, RUB, [(x, 92.0) for x in (t_buy, t_hop1, t_hop2, t_sell)])
    create_quotes(USD, EUR, [(x, 0.88) for x in (t_buy, t_hop1, t_hop2, t_sell)])
    create_quotes(4, USD, [(x, 1.0) for x in (t_buy, t_hop1, t_hop2, t_sell)])
    create_trades(2, [(t_buy, t_buy, 4, 100, 83.59, 10, "buy-USDT")])
    create_transfers([(t_hop1, 2, 100, 3, 100, 4), (t_hop2, 3, 100, 4, 92, 4)])
    create_trades(4, [(t_sell, t_sell, 4, -80, 0.95, 0.4, "sell-USDT")])
    Ledger().rebuild(from_timestamp=0)


# JAL's own view of a lot carried across currencies: cost restated by each transfer's stated value
def test_two_hop_lot_in_jal_view(prepare_db_taxes):
    create_two_hop_lot()

    deal, = JalAccount(4).closed_trades_list()
    assert deal.open_operation().number() == "buy-USDT"
    assert deal.open_price() == Decimal('83.59')
    assert deal.cost_basis() == Decimal('92') / Decimal('8359')
    assert round(deal.open_amount(), 6) == Decimal('73.600000')            # 80 of 92 EUR
    assert round(deal.open_fee(), 6) == Decimal('0.088049')                # 80% of 10 RUB x 92 / 8359, read as EUR
    assert deal.close_amount() == Decimal('76.00')
    assert round(deal.profit(), 6) == Decimal('1.911951')
    # the ledger books income negative, and the fee of the RUB purchase stayed on the RUB account
    assert JalAccount(4).get_category_turnover(PredefinedCategory.Profit, 0, d2t(251231)) == Decimal('-2.4')

    lot, = JalAccount(4).open_trades_list(JalAsset(4))
    assert lot.open_qty() == Decimal('20')
    assert round(lot.open_price(adjusted=True) * lot.open_qty(), 6) == Decimal('18.400000')   # 20 of 92 EUR


# Today's reports of that lot: RU crypto reads the RUB price as EUR, PT has no crypto section and lists the sale
def test_two_hop_lot_in_tax_reports(prepare_db_taxes):
    create_two_hop_lot()

    deal, totals = TaxesRussia().prepare_tax_report(2025, 4)["Криптовалюты"]
    assert {k: deal[k] for k in ('o_number', 'o_price', 'o_amount', 'o_amount_rub', 'o_fee', 'o_fee_rub',
                                 'c_amount_rub', 'spending_rub', 'profit_rub')} == \
           {'o_number': "buy-USDT", 'o_price': Decimal('83.59'), 'o_amount': Decimal('6687.20'),
            'o_amount_rub': Decimal('615222.40'), 'o_fee': Decimal('8'), 'o_fee_rub': Decimal('736.00'),
            'c_amount_rub': Decimal('6992.00'), 'spending_rub': Decimal('615995.20'),
            'profit_rub': Decimal('-609003.20')}
    pt = TaxesPortugal().prepare_tax_report(2025, 4)
    assert [k for k, v in pt.items() if v] == ["Summary", "Not covered"]
    assert [x['number'] for x in pt["Not covered"]] == ["sell-USDT"]


# ----------------------------------------------------------------------------------------------------------------------
# A USD account (1) with every kind of 2025 disposal the reports do not yet place:
# ETH 4, WETH 5, UNI 6, SOL 7 (crypto), STK 8, DLS 9 (stocks)
#   ETH: buy 2, wrap 1 -> WETH, gain 0.2 by a conversion swap of 50 UNI, sell 1.2
#   WETH: 1 from the wrapping, 0.25 by a sale swap of 50 UNI (worth 650), sell 1.25
#   SOL: 0.5 staking reward (zero cost), sell 0.5
#   STK: sold with settlement 0; DLS: delisted
def create_crypto_scenario():
    create_assets([("ETH", "Ether", "", USD, PredefinedAsset.Crypto, 0),
                   ("WETH", "Wrapped Ether", "", USD, PredefinedAsset.Crypto, 0),
                   ("UNI", "Uniswap", "", USD, PredefinedAsset.Crypto, 0),
                   ("SOL", "Solana", "", USD, PredefinedAsset.Crypto, 0),
                   ("STK", "Stock Corp", "US0000000201", USD, PredefinedAsset.Stock, 'us'),
                   ("DLS", "Delisted Corp", "US0000000202", USD, PredefinedAsset.Stock, 'us')])
    days = [241201, 241203, 250110, 250115, 250201, 250301, 250310, 250320, 250401, 250410, 250501, 250601, 250602,
            250901]
    create_quotes(USD, RUB, [(d2t(x), 90.0 + i) for i, x in enumerate(days)])
    create_quotes(USD, EUR, [(d2t(x), 0.90 + i / 100) for i, x in enumerate(days)])
    create_quotes(6, USD, [(d2t(250310), 12.0), (d2t(250320), 13.0)])
    create_quotes(7, USD, [(d2t(250201), 220.0)])
    create_trades(1, [(d2t(250110), d2t(250110), 4, 2, 3000, 2, "buy-ETH"),
                      (d2t(250115), d2t(250115), 6, 100, 10, 1, "buy-UNI"),
                      (d2t(241201), d2t(241203), 8, 10, 50, 1, "buy-STK"),
                      (d2t(250602), d2t(250602), 9, 5, 20, 0, "buy-DLS")])
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': d2t(250201), 'type': AssetIncome.StakingReward, 'account_id': 1, 'symbol_id': symbol_id_for(7),
        'amount': '0.5', 'tax': '0', 'number': 'reward', 'note': 'SOL staking reward'})
    create_conversions(1, [(d2t(250301), 4, 1, 5, 1)])
    create_swaps(1, [(d2t(250310), 6, 50, 4, 0.2)], treatment=SwapTreatment.Conversion)
    create_swaps(1, [(d2t(250320), 6, 50, 5, 0.25)], treatment=SwapTreatment.Sale)
    create_trades(1, [(d2t(250401), d2t(250401), 4, -1.2, 3500, 1, "sell-ETH"),
                      (d2t(250410), d2t(250410), 5, -1.25, 3600, 1, "sell-WETH"),
                      (d2t(250501), d2t(250501), 7, -0.5, 250, 0, "sell-SOL"),
                      (d2t(250601), 0, 8, -10, 60, 1, "sell-STK")])
    create_corporate_actions(1, [(d2t(250901), CorporateAction.Delisting, 9, 5, "Delisting of DLS", [])])
    Ledger().rebuild(from_timestamp=0)


# Today's deals behind the reports, by closing operation
def test_crypto_scenario_deals(prepare_db_taxes):
    create_crypto_scenario()

    otypes = (LedgerTransaction.Trade, LedgerTransaction.Swap, LedgerTransaction.Conversion,
              LedgerTransaction.CorporateAction)
    deals = sorted([(x.close_operation().type(), x.asset().symbol(USD), x.qty(), round(x.profit(), 4))
                    for x in JalAccount(1).closed_trades_list(close_otypes=otypes)], key=lambda x: (x[0], x[1], x[2]))
    assert deals == [   # profit is net of the opening and closing fee shares
        (LedgerTransaction.Trade, "ETH", Decimal('0.2'), Decimal('199.3333')),    # carried by the conversion swap
        (LedgerTransaction.Trade, "ETH", Decimal('1'), Decimal('498.1667')),
        (LedgerTransaction.Trade, "SOL", Decimal('0.5'), Decimal('125.0000')),    # zero-cost reward lot
        (LedgerTransaction.Trade, "STK", Decimal('10'), Decimal('98.0000')),      # settlement 0
        (LedgerTransaction.Trade, "WETH", Decimal('0.25'), Decimal('249.8000')),  # opened by the sale swap at 650
        (LedgerTransaction.Trade, "WETH", Decimal('1'), Decimal('598.2000')),     # carried by the wrapping
        (LedgerTransaction.CorporateAction, "DLS", Decimal('5'), Decimal('0.0000')),   # the loss is in Losses
        (LedgerTransaction.Conversion, "ETH", Decimal('1'), Decimal('-1.0000')),  # zero result less the fee share
        (LedgerTransaction.Swap, "UNI", Decimal('50'), Decimal('-0.5000')),       # conversion swap
        (LedgerTransaction.Swap, "UNI", Decimal('50'), Decimal('149.5000'))]      # sale swap: 650 - 500 - 0.5


# Today's reports of that account: frozen whole, so each later change shows as a fixture diff.
# Known wrong in RU crypto: the ETH lot the conversion swap carried costs 2 (UNI's price x ETH qty), not 500;
# PT has no crypto section; the STK sale with settlement 0 is in neither report.
def test_crypto_scenario_tax_reports(data_path, prepare_db_taxes):
    with open(data_path + 'taxes_crypto.json', 'r', encoding='utf-8') as json_file:
        expected = json.load(json_file)
    create_crypto_scenario()

    ru = TaxesRussia().prepare_tax_report(2025, 1)
    json_decimal2float(ru)
    assert ru == expected['ru']
    pt = TaxesPortugal().prepare_tax_report(2025, 1)
    json_decimal2float(pt)
    assert pt == expected['pt']


# An account whose only disposal is a swap is offered for a tax report
def test_swap_only_account_is_taxable(prepare_db_taxes):
    JalAccountCreator(currency_id=USD, number='S1', name='Swap exchange', investing=1, organization=1,
                      account_type=PredefinedAccountType.CEX).commit()                                         # 2
    create_crypto_scenario()
    create_trades(2, [(d2t(241201), d2t(241201), 6, 10, 10, 0, "buy-UNI-2")])
    create_swaps(2, [(d2t(250320), 6, 10, 4, 0.05)], treatment=SwapTreatment.Sale)
    Ledger().rebuild(from_timestamp=0)

    assert [x.id() for x in JalAccount.get_taxable_accounts(2025)] == [1, 2]
