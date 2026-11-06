import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_dividends, create_trades, create_transfers, symbol_id_for
from tests.test_account_holdings import wallet, WALLET, LINK, USD
from jal.constants import PredefinedAccountType, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, AssetIncome
from jal.reports.account_balance import AccountBalanceHistoryReportWindow
from jal.reports.assets_payments import AssetsPaymentsReportWindow
from jal.reports.deals import DealsReportWindow
from jal.reports.profit_loss import ProfitLossReportWindow
from jal.reports.reports import Reports

BEGIN = d2t(210101)
END = d2t(210301)


def test_deals_follow_the_chosen_account(wallet):
    # 40 of the 100 LINK bought at 10 are sold at 15: 40 x 5 = 200
    create_trades(WALLET, [(d2t(210201), d2t(210201), LINK, Decimal('-40'), Decimal('15'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    window = DealsReportWindow(Reports(None, None))
    window.ui.ReportRange.setRange(BEGIN, END)
    assert window.trades_model._trades == []
    window.ui.ReportAccountEdit.selection_done(WALLET)
    assert window.ui.ReportAccountEdit.name.text() == 'ETH wallet'
    assert [x.profit() for x in window.trades_model._trades] == [Decimal('200')]
    window.ui.ReportAccountEdit.on_clean_button_clicked()
    assert window.trades_model._trades == []


def test_payments_follow_the_chosen_account(wallet):
    create_dividends([(d2t(210210), WALLET, LINK, Decimal('7'), Decimal('1'), 'reward')])
    window = AssetsPaymentsReportWindow(Reports(None, None))
    window.ui.ReportRange.setRange(BEGIN, END)
    assert window.payments_model.rowCount() == 0
    window.ui.ReportAccountEdit.selection_done(WALLET)
    assert window.payments_model.rowCount() == 1
    assert window.payments_model._total == Decimal('7')
    assert window.payments_model._total_tax == Decimal('1')


def test_payments_total_leaves_out_assets_received(wallet):
    create_dividends([(d2t(210210), WALLET, LINK, Decimal('7'), Decimal('1'), 'dividend')])
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': d2t(210211), 'type': AssetIncome.StakingReward, 'account_id': WALLET,
        'symbol_id': symbol_id_for(LINK), 'amount': '3', 'tax': '0', 'number': '', 'note': 'reward'})
    window = AssetsPaymentsReportWindow(Reports(None, None))
    window.ui.ReportRange.setRange(BEGIN, END)
    window.ui.ReportAccountEdit.selection_done(WALLET)
    model = window.payments_model
    assert model.rowCount() == 2
    assert model._total == Decimal('7')         # 3 LINK are not 3 dollars
    assert model._total_tax == Decimal('1')
    assert model.footerData(3) == "Total of payments in USD:"


def test_balance_history_opens_on_the_account_it_was_asked_for(wallet):
    window = AccountBalanceHistoryReportWindow(Reports(None, None),
                                               {'begin_ts': BEGIN, 'end_ts': END, 'account_id': WALLET})
    assert window.ui.ReportAccountEdit.selected_id == WALLET
    assert window.ui.ReportAccountEdit.name.text() == 'ETH wallet'
    assert window.chart.balances_series.count() > 0
    # 100 LINK at 12 less the 1,000 paid for them
    assert window.chart.balances_series.at(window.chart.balances_series.count() - 1).y() == 200


def test_balance_history_chart_is_emptied_with_the_account(wallet):
    window = AccountBalanceHistoryReportWindow(Reports(None, None),
                                               {'begin_ts': BEGIN, 'end_ts': END, 'account_id': WALLET})
    chart = window.chart.chartView.chart()
    assert len(chart.series()) == 1
    window.ui.ReportAccountEdit.on_clean_button_clicked()
    assert chart.series() == []
    assert chart.axes() == []
    window.ui.ReportRange.setRange(BEGIN, END + 86400)    # still nothing to draw
    assert chart.series() == []
    window.ui.ReportAccountEdit.selection_done(WALLET)    # and it draws again
    assert len(chart.series()) == 1
    assert len(chart.axes()) == 2


def test_pl_in_out_counts_money_not_coins_moved(wallet):
    other = JalAccountCreator(currency_id=USD, number='', name='Other wallet', investing=1, organization=1, precision=18,
                              account_type=PredefinedAccountType.Wallet, address='0x' + '3' * 40,
                              chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_transfers([(d2t(210201), WALLET, Decimal('500'), other.id(), Decimal('500'), None),
                      (d2t(210202), WALLET, Decimal('40'), other.id(), Decimal('0'), LINK)])
    Ledger().rebuild(from_timestamp=0)
    window = ProfitLossReportWindow(Reports(None, None))
    model = window.pl_model
    in_out = model.data4period(d2t(210201), d2t(210228), JalAccount(WALLET))['transfers']
    assert in_out == Decimal('-500')            # the 40 LINK sent are not 40 dollars
