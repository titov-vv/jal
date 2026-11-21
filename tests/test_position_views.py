from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtCharts import QScatterSeries

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_fifo
from tests.helpers import d2t, create_stocks, create_trades, create_quotes, create_corporate_actions, create_assets, \
    create_swaps
from jal.constants import PredefinedAsset, SwapTreatment
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.country import JalCountry
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import CorporateAction
from jal.db.residence import JalResidence
from jal.data_export.tax_estimate import TaxEstimate
from jal.widgets.position_details import PositionDetails, LotsModel

USD, A, B = 2, 4, 5


# A position that a corporate action has been through: 20 A bought at 100 became 5 B, so the account holds 5 shares
# that cost 400 apiece - and neither of those two numbers is the one the opening trade was made at.
@pytest.fixture
def split_position(prepare_db_fifo):
    create_stocks([('A', 'A SHARE'), ('B', 'B SHARE')], currency_id=USD)
    create_trades(1, [(d2t(220101), d2t(220101), A, Decimal('20'), Decimal('100'), Decimal('0'))])
    create_corporate_actions(1, [(d2t(220201), CorporateAction.Split, A, Decimal('20'), 'Split 20 A -> 5 B',
                                  [(B, Decimal('5'), Decimal('1'))])])
    create_quotes(B, USD, [(d2t(220301), 500.0)])       # what a share of B is worth now
    create_quotes(USD, 1, [(d2t(211231), 100.0)])       # and what a USD is worth in the tax currency
    Ledger().rebuild(from_timestamp=0)
    yield


# The estimate is made of the position as it stands: 5 shares that cost 400, not the 20 at 100 that were bought.
def test_tax_estimate_uses_the_adjusted_position(split_position):
    lots = JalAccount(1).open_trades_list(JalAsset(B), d2t(220401))
    estimate = TaxEstimate('ru', JalAccount(1), JalAsset(B), d2t(220401))
    assert estimate.gain(lots[0]) == Decimal('50000')                # 5 * (500 - 400) at 100 RUB/USD on both ends
    assert estimate.totals(lots) == {'gain': Decimal('50000'), 'tax': Decimal('6500'), 'excluded': 0, 'short_held': 0}


# PT converts cost and value at the disposal's rate (CIRS a.23), so a USD/EUR move adds no gain
def test_pt_tax_estimate_converts_both_legs_at_the_disposal_rate(split_position):
    create_quotes(USD, 3, [(d2t(211231), 0.80), (d2t(220301), 0.90)])   # USD/EUR at the purchase and the disposal
    lots = JalAccount(1).open_trades_list(JalAsset(B), d2t(220401))
    totals = TaxEstimate('pt', JalAccount(1), JalAsset(B), d2t(220401)).totals(lots)
    assert totals['gain'] == Decimal('450.00')                       # 5 * (500 - 400) * 0.90
    assert totals['tax'] == Decimal('126.0000')                      # 28% of it
    assert totals['short_held'] == 1                                 # held 90 days: englobamento may apply


# The window lists the position as it stands, totals the checked lots and draws them on the chart
def test_position_details_follow_the_checked_and_selected_lots(split_position):
    create_trades(1, [(d2t(220215), d2t(220215), B, Decimal('5'), Decimal('450'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    parent = QWidget()
    window = PositionDetails(1, B, USD, d2t(220401), parent=parent)
    assert window.ready
    model = window.model
    assert [(x.open_qty(), x.open_price(adjusted=True)) for x in window.lots] == [(Decimal('5'), Decimal('400')),
                                                                                (Decimal('5'), Decimal('450'))]
    assert model.data(model.index(0, LotsModel.PL)) == Decimal('500')
    assert model.data(model.index(0, LotsModel.PL_PERCENT)) == Decimal('0.25')
    assert model.footerData(LotsModel.QTY) == "10"
    assert model.footerData(LotsModel.PRICE) == "425.00"
    assert window.chart.trade_series.count() == 2
    assert window.chart.average_series.count() == 2 and window.chart.average_series.at(0).y() == 425.0
    assert window.chart.selected_series.count() == 0                 # nothing selected, nothing highlighted

    model.setData(model.index(1, LotsModel.CHECK), Qt.Checked.value, Qt.CheckStateRole)
    model.setData(model.index(1, LotsModel.CHECK), Qt.Unchecked.value, Qt.CheckStateRole)
    assert model.footerData(LotsModel.QTY) == "5"
    assert model.footerData(LotsModel.DATE) == "1 of 2 lots"
    assert window.chart.trade_series.count() == 1
    assert window.chart.average_series.at(0).y() == 400.0

    window.chart.lotClicked.emit(0)                                  # a click on the marker selects its row
    assert [x.row() for x in window.ui.LotsView.selectionModel().selectedRows()] == [0]
    assert window.chart.selected_series.count() == 1
    assert window.chart.selected_series.at(0).y() == 400.0
    window.ui.LotsView.selectRow(1)                                  # an unchecked lot has no marker to highlight
    assert window.chart.selected_series.count() == 0

    window.ui.CountryCombo.setCurrentIndex(window.ui.CountryCombo.findData('ru'))
    model.toggle_all()                                               # all checked, then all unchecked
    assert model.checked_rows() == {0, 1}
    model.toggle_all()
    assert model.checked_rows() == set()
    assert window.chart.average_series.count() == 0
    assert window.ui.GainValue.text() == "0.00 RUB"


# The tax residence offered first is the one the residence table has on the window's date
def test_position_details_start_from_the_residence(split_position):
    pt = JalCountry(data={'code': 'pt'}, search=True).id()
    JalDB._exec("INSERT INTO residence (since_timestamp, currency_id, country_id, timezone) VALUES (:t, 3, :c, '')",
                [(":t", d2t(220101)), (":c", pt)])
    JalResidence.invalidate_cache()
    try:
        create_quotes(USD, 3, [(d2t(211231), 0.90)])
        parent = QWidget()
        window = PositionDetails(1, B, USD, d2t(220401), parent=parent)
        assert window.ui.CountryCombo.currentData() == 'pt'
        assert window.ui.TaxValue.text() == "~ 126.00 EUR"
        assert not window.ui.TaxValue.font().italic()
        window.ui.CountryCombo.setCurrentIndex(window.ui.CountryCombo.findData('ru'))
        assert window.ui.TaxValue.text() == "~ 6,500.00 RUB"
    finally:
        JalDB._exec("DELETE FROM residence")
        JalResidence.invalidate_cache()


# PT leaves out crypto held 365 days or more, the clock restarting at a crypto-for-crypto exchange
def test_pt_tax_estimate_excludes_long_held_crypto(prepare_db_fifo):
    create_assets([('ETH', 'Ether', '', USD, PredefinedAsset.Crypto, 0),
                   ('WETH', 'Wrapped Ether', '', USD, PredefinedAsset.Crypto, 0)])
    eth = JalAsset.find({'symbol': 'ETH', 'type_id': PredefinedAsset.Crypto}).id()
    weth = JalAsset.find({'symbol': 'WETH', 'type_id': PredefinedAsset.Crypto}).id()
    create_trades(1, [(d2t(200101), d2t(200101), eth, Decimal('2'), Decimal('100'), Decimal('0')),
                      (d2t(200101), d2t(200101), weth, Decimal('1'), Decimal('100'), Decimal('0'))])
    create_trades(1, [(d2t(211001), d2t(211001), eth, Decimal('1'), Decimal('300'), Decimal('0'))])
    create_swaps(1, [(d2t(211101), eth, Decimal('1'), weth, Decimal('1'))], treatment=SwapTreatment.Conversion)
    create_quotes(weth, USD, [(d2t(220301), 400.0)])
    create_quotes(USD, 3, [(d2t(191231), 1.0)])
    Ledger().rebuild(from_timestamp=0)

    lots = JalAccount(1).open_trades_list(JalAsset(weth), d2t(220401))
    assert sorted(x.acquired() for x in lots) == [d2t(200101), d2t(200101)]   # the ledger keeps the purchase date
    estimate = TaxEstimate('pt', JalAccount(1), JalAsset(weth), d2t(220401))
    assert sorted(estimate.held_days(x) for x in lots) == [151, 821]          # PT restarts at the 01/11/21 swap
    totals = estimate.totals(lots)
    assert totals['excluded'] == 1
    assert totals['short_held'] == 1
    assert totals['gain'] == Decimal('300')                                    # the swapped lot only: 400 - 100
    assert TaxEstimate('ru', JalAccount(1), JalAsset(weth), d2t(220401)).totals(lots)['excluded'] == 0


# The chart marks the position where it really sits: 5 shares at 400, on the price series of B.
def test_price_chart_marks_the_adjusted_position(split_position):
    parent = QWidget()
    window = PositionDetails(1, B, USD, d2t(220401), parent=parent)
    assert window.chart.trade_series.count() == 1
    assert (window.chart.trade_series.at(0).y()) == 400.0
    assert window.chart.trade_series.markerShape() == QScatterSeries.MarkerShape.MarkerShapeCircle


# The window comes back where and as large as it was left, with its splitter where it was left
def test_position_details_keep_their_layout(split_position):
    parent = QWidget()
    window = PositionDetails(1, B, USD, d2t(220401), parent=parent)
    window.setParent(None)
    window.resize(640, 420)
    window.show()
    window.ui.PositionDetailsSplitter.setSizes([320, 300])
    sizes, size = window.ui.PositionDetailsSplitter.sizes(), window.size()
    window.close()

    again = PositionDetails(1, B, USD, d2t(220401), parent=parent)
    again.setParent(None)
    again.resize(760, 560)                                          # what addWindow() does before show()
    again.show()
    assert again.size() == size
    assert again.ui.PositionDetailsSplitter.sizes() == sizes
    again.close()
    window.setParent(parent)
    again.setParent(parent)
