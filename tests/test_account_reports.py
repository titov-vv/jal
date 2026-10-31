import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_dividends, create_trades
from tests.test_account_holdings import wallet, WALLET, LINK
from jal.db.ledger import Ledger
from jal.reports.account_balance import AccountBalanceHistoryReportWindow
from jal.reports.assets_payments import AssetsPaymentsReportWindow
from jal.reports.deals import DealsReportWindow
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
