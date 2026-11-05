from decimal import Decimal

import pytest
from PySide6.QtWidgets import QWidget, QMessageBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_assets, create_quotes, create_trades, create_swaps, create_conversions, \
    create_corporate_actions, symbol_id_for, operation_id
from tests.test_taxes_shorts import _shorts
from jal.widgets.icons import JalIcon
from jal.widgets.tax_widget import TaxWidget
from jal.widgets.main_window import MainWindow
from jal.constants import PredefinedAsset, SwapTreatment, AssetData
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.lots import LedgerLotStore, ScratchLotStore
from jal.db.basis_policy import JalPolicy
from jal.db.operations import LedgerTransaction, LedgerError, AssetIncome, CorporateAction
from jal.data_export.taxes import TaxReportStop, TaxReportCancelled
from jal.db.tax_override import JalTaxOverride, TaxOverride
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal

RUB, USD, EUR = 1, 2, 3
DEAL_FIELDS = ('symbol', 'qty', 'o_number', 'o_date', 'o_amount', 'c_number', 'c_date', 'c_amount', 'profit')


def deal_rows(section: list) -> list:
    return [x for x in section if x['report_template'] == "trade"]


def pick(row: dict, fields) -> dict:
    return {k: row[k] for k in fields}


# ----------------------------------------------------------------------------------------------------------------------
# RU, 2025, USD account 1: UNI 4, AVAX 5, ETH 6, WETH 7, SOL 8, LINK 9; no fees
#   UNI 100 @ 10 -> conversion swap into 40 AVAX (UNI quoted 12) -> AVAX sold @ 35
#   ETH 1 @ 3000 -> wrapped into 1 WETH (ETH quoted 3200) -> WETH sold @ 3500
#   SOL 2 staking reward (quoted 200) -> sale swap into 25 LINK (SOL quoted 220) -> LINK sold @ 20
RU_RATES = {250110: 100, 250115: 101, 250201: 102, 250301: 103, 250310: 104, 250320: 105, 250401: 106, 250410: 107,
            250501: 108}


def create_ru_scenario():
    create_assets([("UNI", "Uniswap", "", USD, PredefinedAsset.Crypto, 0),
                   ("AVAX", "Avalanche", "", USD, PredefinedAsset.Crypto, 0),
                   ("ETH", "Ether", "", USD, PredefinedAsset.Crypto, 0),
                   ("WETH", "Wrapped Ether", "", USD, PredefinedAsset.Crypto, 0),
                   ("SOL", "Solana", "", USD, PredefinedAsset.Crypto, 0),
                   ("LINK", "Chainlink", "", USD, PredefinedAsset.Crypto, 0)])
    create_quotes(USD, RUB, [(d2t(x), y) for x, y in RU_RATES.items()])
    create_quotes(4, USD, [(d2t(250301), 12)])
    create_quotes(5, USD, [(d2t(250301), 30)])
    create_quotes(6, USD, [(d2t(250310), 3200)])
    create_quotes(7, USD, [(d2t(250310), 3200)])
    create_quotes(8, USD, [(d2t(250201), 200), (d2t(250320), 220)])
    create_quotes(9, USD, [(d2t(250320), 17.6)])
    create_trades(1, [(d2t(250110), d2t(250110), 6, 1, 3000, 0, "buy-ETH"),
                      (d2t(250115), d2t(250115), 4, 100, 10, 0, "buy-UNI")])
    LedgerTransaction.create_new(LedgerTransaction.AssetIncome, {
        'timestamp': d2t(250201), 'type': AssetIncome.StakingReward, 'account_id': 1, 'symbol_id': symbol_id_for(8),
        'amount': '2', 'tax': '0', 'number': 'reward-SOL', 'note': 'SOL staking reward'})
    create_swaps(1, [(d2t(250301), 4, 100, 5, 40)], treatment=SwapTreatment.Conversion)
    create_conversions(1, [(d2t(250310), 6, 1, 7, 1)])
    create_swaps(1, [(d2t(250320), 8, 2, 9, 25)], treatment=SwapTreatment.Sale)
    create_trades(1, [(d2t(250401), d2t(250401), 5, -40, 35, 0, "sell-AVAX"),
                      (d2t(250410), d2t(250410), 7, -1, 3500, 0, "sell-WETH"),
                      (d2t(250501), d2t(250501), 9, -25, 20, 0, "sell-LINK")])
    Ledger().rebuild(from_timestamp=0)


# Every swap and wrapping is a disposal at market and the asset it buys opens there; the reward lot opens at its quote.
# The RUB total is today's, as each exchange is converted at its own day's rate on both of its sides.
def test_ru_crypto(prepare_db_taxes):
    create_ru_scenario()

    report = TaxesRussia().prepare_tax_report(2025, 1)
    assert [pick(x, DEAL_FIELDS + ('o_amount_rub', 'c_amount_rub', 'profit_rub')) | {'pending': 'pending_replay' in x}
            for x in deal_rows(report["Криптовалюты"])] == [
        {'symbol': "UNI", 'qty': Decimal('100'), 'o_number': "buy-UNI", 'o_date': d2t(250115),   # 100 x 12
         'o_amount': Decimal('1000.00'), 'c_number': '', 'c_date': d2t(250301), 'c_amount': Decimal('1200.00'),
         'profit': Decimal('200.00'), 'o_amount_rub': Decimal('101000.00'), 'c_amount_rub': Decimal('123600.00'),
         'profit_rub': Decimal('22600.00'), 'pending': False},
        {'symbol': "ETH", 'qty': Decimal('1'), 'o_number': "buy-ETH", 'o_date': d2t(250110),
         'o_amount': Decimal('3000.00'), 'c_number': '', 'c_date': d2t(250310), 'c_amount': Decimal('3200.00'),
         'profit': Decimal('200.00'), 'o_amount_rub': Decimal('300000.00'), 'c_amount_rub': Decimal('332800.00'),
         'profit_rub': Decimal('32800.00'), 'pending': False},
        {'symbol': "SOL", 'qty': Decimal('2'), 'o_number': "reward-SOL", 'o_date': d2t(250201),   # 2 x 200
         'o_amount': Decimal('400.00'), 'c_number': '', 'c_date': d2t(250320), 'c_amount': Decimal('440.00'),
         'profit': Decimal('40.00'), 'o_amount_rub': Decimal('40800.00'), 'c_amount_rub': Decimal('46200.00'),
         'profit_rub': Decimal('5400.00'), 'pending': False},
        {'symbol': "AVAX", 'qty': Decimal('40'), 'o_number': '', 'o_date': d2t(250301),   # opened at the swap's 1 200
         'o_amount': Decimal('1200.00'), 'c_number': "sell-AVAX", 'c_date': d2t(250401), 'c_amount': Decimal('1400.00'),
         'profit': Decimal('200.00'), 'o_amount_rub': Decimal('123600.00'), 'c_amount_rub': Decimal('148400.00'),
         'profit_rub': Decimal('24800.00'), 'pending': False},
        {'symbol': "WETH", 'qty': Decimal('1'), 'o_number': '', 'o_date': d2t(250310),    # opened at the wrapping's 3 200
         'o_amount': Decimal('3200.00'), 'c_number': "sell-WETH", 'c_date': d2t(250410), 'c_amount': Decimal('3500.00'),
         'profit': Decimal('300.00'), 'o_amount_rub': Decimal('332800.00'), 'c_amount_rub': Decimal('374500.00'),
         'profit_rub': Decimal('41700.00'), 'pending': False},
        {'symbol': "LINK", 'qty': Decimal('25'), 'o_number': '', 'o_date': d2t(250320),   # opened at the swap's 440
         'o_amount': Decimal('440.00'), 'c_number': "sell-LINK", 'c_date': d2t(250501), 'c_amount': Decimal('500.00'),
         'profit': Decimal('60.00'), 'o_amount_rub': Decimal('46200.00'), 'c_amount_rub': Decimal('54000.00'),
         'profit_rub': Decimal('7800.00'), 'pending': False}]
    totals, = [x for x in report["Криптовалюты"] if x['report_template'] == "totals"]
    assert totals['profit_rub'] == Decimal('135100.00')
    income, = [x for x in report["Криптодоход"] if x['report_template'] == "income"]
    assert (income['value'], income['value_rub']) == (Decimal('400.00'), Decimal('40800.00'))


# ----------------------------------------------------------------------------------------------------------------------
# PT, 2024-2025, USD account 1: ETH 4, UNI 5, SOL 6, AVAX 7, USDC 8, aUSDC 9 (lending receipt), OLD 10 (NL), NEW 11 (RU)
#   ETH 2 @ 1500 (2023) -> sale swap into 400 UNI (ETH quoted 3500) -> 200 UNI sold @ 20 275 days on, 200 @ 25 396 days on
#   SOL 10 @ 20 (2023) -> conversion swap into 20 AVAX -> AVAX sold @ 30 275 days on
#   USDC 1000 @ 1 (2023) -> supplied for aUSDC -> withdrawn -> sold @ 1.001
#   OLD 100 @ 30 (2023) -> merger into OLD (0.2) + 50 NEW (0.8), both keep the date -> NEW sold @ 70
PT_RATES = {230110: 0.93, 230301: 0.94, 230601: 0.92, 240301: 0.92, 240601: 0.93, 240828: 0.90, 240829: 0.90,
            241101: 0.92, 241201: 0.95, 250101: 0.96, 250201: 0.97, 250401: 0.91}


def create_pt_scenario(new_country='ru'):
    create_assets([("ETH", "Ether", "", USD, PredefinedAsset.Crypto, 0),
                   ("UNI", "Uniswap", "", USD, PredefinedAsset.Crypto, 0),
                   ("SOL", "Solana", "", USD, PredefinedAsset.Crypto, 0),
                   ("AVAX", "Avalanche", "", USD, PredefinedAsset.Crypto, 0),
                   ("USDC", "USD Coin", "", USD, PredefinedAsset.Crypto, 0),
                   ("aUSDC", "Aave USDC", "", USD, PredefinedAsset.Crypto, 0),
                   ("OLD", "Old Holding N.V.", "NL0000000101", USD, PredefinedAsset.Stock, 'nl'),
                   ("NEW", "New Holding PJSC", "RU0000000102", USD, PredefinedAsset.Stock, new_country)])
    for datatype, value in ((AssetData.Rebasing, '1'), (AssetData.Protocol, 'Aave v3')):
        JalDB._exec("INSERT INTO asset_data(asset_id, datatype, value) VALUES(9, :dt, :v)",
                    [(":dt", datatype), (":v", value)], commit=True)
    create_quotes(USD, EUR, [(d2t(x), y) for x, y in PT_RATES.items()])
    create_quotes(4, USD, [(d2t(240301), 3500)])
    create_quotes(5, USD, [(d2t(240301), 17.5)])
    create_quotes(6, USD, [(d2t(240301), 25)])
    create_quotes(10, USD, [(d2t(240828), 32)])
    create_quotes(11, USD, [(d2t(240830), 50)])
    create_quotes(8, USD, [(d2t(240601), 1), (d2t(250101), 1)])
    create_trades(1, [(d2t(230110), d2t(230110), 4, 2, 1500, 0, "buy-ETH"),
                      (d2t(230110), d2t(230110), 6, 10, 20, 0, "buy-SOL"),
                      (d2t(230301), d2t(230301), 10, 100, 30, 0, "buy-OLD"),
                      (d2t(230601), d2t(230601), 8, 1000, 1, 0, "buy-USDC")])
    create_swaps(1, [(d2t(240301), 4, 2, 5, 400)], treatment=SwapTreatment.Sale)
    create_swaps(1, [(d2t(240301), 6, 10, 7, 20)], treatment=SwapTreatment.Conversion)
    create_conversions(1, [(d2t(240601), 8, 1000, 9, 1000)])
    create_corporate_actions(1, [(d2t(240829), CorporateAction.Merger, 10, 100, "Merger OLD -> OLD + NEW",
                                  [(10, 100, 0.2), (11, 50, 0.8, True)])])
    create_trades(1, [(d2t(241101), d2t(241101), 11, -50, 70, 0, "sell-NEW"),
                      (d2t(241201), d2t(241201), 5, -200, 20, 0, "sell-UNI-1"),
                      (d2t(241201), d2t(241201), 7, -20, 30, 0, "sell-AVAX")])
    create_conversions(1, [(d2t(250101), 9, 1000, 8, 1000)])
    create_trades(1, [(d2t(250201), d2t(250201), 8, -1000, 1.001, 0, "sell-USDC"),
                      (d2t(250401), d2t(250401), 5, -200, 25, 0, "sell-UNI-2")])
    Ledger().rebuild(from_timestamp=0)


PT_FIELDS = DEAL_FIELDS + ('o_amount_eur', 'c_amount_eur', 'profit_eur', 'days')


# Each exchange carried the purchase's cost and restarted the holding period, so AVAX moves under 365 days; the merger
# into a non-EU issuer is a disposal on Shares at 51.2 per NEW share (32 x 0.8 / 0.5, above its first quote of 50)
def test_pt_2024(prepare_db_taxes):
    create_pt_scenario()

    taxes = TaxesPortugal()
    report = taxes.prepare_tax_report(2024, 1)
    assert [pick(x, PT_FIELDS) for x in deal_rows(report["Crypto < 365 days"])] == [
        {'symbol': "UNI", 'qty': Decimal('200'), 'o_number': "buy-ETH", 'o_date': d2t(240301),
         'o_amount': Decimal('1500.00'), 'c_number': "sell-UNI-1", 'c_date': d2t(241201), 'c_amount': Decimal('4000.00'),
         'profit': Decimal('2500.00'), 'o_amount_eur': Decimal('1425.00'), 'c_amount_eur': Decimal('3800.00'),
         'profit_eur': Decimal('2375.00'), 'days': 275},
        {'symbol': "AVAX", 'qty': Decimal('20'), 'o_number': "buy-SOL", 'o_date': d2t(240301),
         'o_amount': Decimal('200.00'), 'c_number': "sell-AVAX", 'c_date': d2t(241201), 'c_amount': Decimal('600.00'),
         'profit': Decimal('400.00'), 'o_amount_eur': Decimal('190.00'), 'c_amount_eur': Decimal('570.00'),
         'profit_eur': Decimal('380.00'), 'days': 275}]
    assert deal_rows(report["Crypto ≥ 365 days"]) == []
    assert taxes.texts['crypto_carried'] in taxes.section_headers("Crypto < 365 days")
    shares = deal_rows(report["Shares"])
    assert [pick(x, DEAL_FIELDS + ('o_amount_eur', 'c_amount_eur', 'profit_eur', 'c_type', 'code')) for x in shares] == [
        {'symbol': "NEW", 'qty': Decimal('50'), 'o_number': '', 'o_date': d2t(240829),
         'o_amount': Decimal('2560.00'), 'c_number': "sell-NEW", 'c_date': d2t(241101), 'c_amount': Decimal('3500.00'),
         'profit': Decimal('940.00'), 'o_amount_eur': Decimal('2355.20'), 'c_amount_eur': Decimal('3220.00'),
         'profit_eur': Decimal('864.80'), 'c_type': "Venda", 'code': "G01"},
        {'symbol': "OLD", 'qty': Decimal('100'), 'o_number': "buy-OLD", 'o_date': d2t(230301),   # 0.8 of 3 000
         'o_amount': Decimal('2400.00'), 'c_number': '', 'c_date': d2t(240829), 'c_amount': Decimal('2560.00'),
         'profit': Decimal('160.00'), 'o_amount_eur': Decimal('2160.00'), 'c_amount_eur': Decimal('2304.00'),
         'profit_eur': Decimal('144.00'), 'c_type': "Permuta", 'code': "G01"}]
    assert shares[1]['note'].startswith(taxes.texts['exchange'])


# The withdrawal restarted the clock of the USDC lot; UNI keeps the ETH cost through its sale swap
def test_pt_2025(prepare_db_taxes):
    create_pt_scenario()

    report = TaxesPortugal().prepare_tax_report(2025, 1)
    assert [pick(x, PT_FIELDS) for x in deal_rows(report["Crypto < 365 days"])] == [
        {'symbol': "USDC", 'qty': Decimal('1000'), 'o_number': "buy-USDC", 'o_date': d2t(250101),
         'o_amount': Decimal('1000.00'), 'c_number': "sell-USDC", 'c_date': d2t(250201), 'c_amount': Decimal('1001.00'),
         'profit': Decimal('1.00'), 'o_amount_eur': Decimal('970.00'), 'c_amount_eur': Decimal('970.97'),
         'profit_eur': Decimal('0.97'), 'days': 31}]
    assert [pick(x, PT_FIELDS) for x in deal_rows(report["Crypto ≥ 365 days"])] == [
        {'symbol': "UNI", 'qty': Decimal('200'), 'o_number': "buy-ETH", 'o_date': d2t(240301),
         'o_amount': Decimal('1500.00'), 'c_number': "sell-UNI-2", 'c_date': d2t(250401), 'c_amount': Decimal('5000.00'),
         'profit': Decimal('3500.00'), 'o_amount_eur': Decimal('1365.00'), 'c_amount_eur': Decimal('4550.00'),
         'profit_eur': Decimal('3185.00'), 'days': 396}]


# A merger into an EU issuer is carried as JAL books it; a new asset without a country stops the report
def test_pt_merger_into_an_eu_issuer(prepare_db_taxes):
    create_pt_scenario(new_country='de')

    report = TaxesPortugal().prepare_tax_report(2024, 1)
    fields = ('symbol', 'o_number', 'o_date', 'o_amount', 'c_number', 'profit')
    assert [pick(x, fields) for x in deal_rows(report["Shares"])] == [
        {'symbol': "NEW", 'o_number': "buy-OLD", 'o_date': d2t(230301), 'o_amount': Decimal('2400.00'),
         'c_number': "sell-NEW", 'profit': Decimal('1100.00')}]


def test_pt_merger_into_an_asset_without_country(prepare_db_taxes):
    create_pt_scenario(new_country=0)

    with pytest.raises(TaxReportStop) as stop:
        TaxesPortugal().prepare_tax_report(2024, 1)
    assert stop.value.no_country == ["NEW (New Holding PJSC)"]


# ----------------------------------------------------------------------------------------------------------------------
def create_pt_scenario_in_rub():
    create_pt_scenario()
    create_quotes(USD, RUB, [(d2t(230101), 90)])


# A report replays the lots of the whole history and reads every deal and lot from there, never from the main tables
@pytest.mark.parametrize("scenario, report_class, year", [(create_ru_scenario, TaxesRussia, 2025),
                                                          (create_pt_scenario, TaxesPortugal, 2024),
                                                          (create_pt_scenario, TaxesPortugal, 2025),
                                                          (_shorts, TaxesRussia, 2024), (_shorts, TaxesRussia, 2025),
                                                          (_shorts, TaxesPortugal, 2025),
                                                          (create_pt_scenario_in_rub, TaxesRussia, 2024)])
def test_report_reads_its_lot_store(prepare_db_taxes, scenario, report_class, year):
    scenario()
    expected = report_class().prepare_tax_report(year, 1)
    JalDB._exec("DELETE FROM main.trades_closed")
    JalDB._exec("DELETE FROM main.trades_opened", commit=True)
    assert report_class().prepare_tax_report(year, 1) == expected


# A stop of the replay stops the report, and the replay's store is let go after a stop as after a report
def test_replay_stop_and_store_release(prepare_db_taxes):
    class StoppingPolicy(JalPolicy):
        def treatment(self, operation):
            raise LedgerError("no quote for the swap")

    create_ru_scenario()
    report = TaxesRussia()
    report.basis_policy = StoppingPolicy
    with pytest.raises(TaxReportStop) as stop:
        report.prepare_tax_report(2025, 1)
    assert (stop.value.missing, stop.value.replay) == ([], "no quote for the swap")
    assert isinstance(report.lots, LedgerLotStore) and not isinstance(report.lots, ScratchLotStore)
    assert [x for x in JalDB._read_to_list("PRAGMA database_list") if 'lots_replay' in x] == []
    del report.basis_policy
    assert report.prepare_tax_report(2025, 1)["Криптовалюты"]
    assert [x for x in JalDB._read_to_list("PRAGMA database_list") if 'lots_replay' in x] == []


# Progress: the replay up to 90 % under its own text, then one step per section under the section's name
def test_report_progress(prepare_db_taxes):
    create_pt_scenario()
    steps = []
    TaxesPortugal().prepare_tax_report(2024, 1, progress=lambda percent, text: steps.append((percent, text)))
    replayed = [x for x in steps if x[1] == "Tax replay (PT): %p%"]
    assert [x[0] for x in replayed] == sorted(set(x[0] for x in replayed)) and replayed[-1][0] == 90
    assert [x[1] for x in steps[len(replayed):]] == [f"{x}: %p%" for x in TaxesPortugal().reports]
    assert [x[0] for x in steps] == sorted(x[0] for x in steps) and steps[-1][0] < 100


# The tax window shows the report's progress and stays disabled and open while the report runs
def test_tax_window_while_a_report_runs(prepare_db_taxes, tmp_path, monkeypatch):
    create_ru_scenario()
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    JalIcon()
    parent = QWidget()
    widget = TaxWidget(parent)
    widget.ui.Year.setValue(2025)
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
    widget.ui.XlsFileName.setText(str(tmp_path / "report.xlsx"))
    shown, texts, during = [], [], []
    widget.show_progress.connect(shown.append)
    widget.update_progress_text.connect(texts.append)
    widget.update_progress.connect(lambda _x: during.append((widget.isEnabled(), widget.close())))
    widget.SaveReport()
    assert shown == [True, False]
    assert texts[0] == "Tax replay (RU): %p%" and texts[-1] == "Комиссии: %p%"
    assert set(during) == {(False, False)}
    assert widget.isEnabled() and (tmp_path / "report.xlsx").exists()


# A stop asked for during the replay ends the report at the next progress step and lets its store go
def test_report_cancel(prepare_db_taxes):
    create_ru_scenario()
    report = TaxesRussia()
    steps = []
    with pytest.raises(TaxReportCancelled):
        report.prepare_tax_report(2025, 1, progress=lambda percent, text: steps.append(percent) or report.cancel())
    assert len(steps) == 1 and steps[0] < TaxesRussia.REPLAY_SHARE   # stopped inside the replay
    assert [x for x in JalDB._read_to_list("PRAGMA database_list") if 'lots_replay' in x] == []
    assert report.prepare_tax_report(2025, 1)["Криптовалюты"]   # the next report runs to its end


# The window's stop ends its report: nothing saved, no message, the window enabled again
def test_tax_window_stop(prepare_db_taxes, tmp_path, monkeypatch):
    create_ru_scenario()
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: messages.append(args) or QMessageBox.Ok)
    JalIcon()
    parent = QWidget()
    widget = TaxWidget(parent)
    widget.ui.Year.setValue(2025)
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
    widget.ui.XlsFileName.setText(str(tmp_path / "report.xlsx"))
    shown = []
    widget.show_progress.connect(shown.append)
    widget.update_progress.connect(lambda _x: widget.on_cancel())
    widget.SaveReport()
    assert shown == [True, False] and messages == []
    assert widget.isEnabled() and not (tmp_path / "report.xlsx").exists()


# The main window shows a tax report's progress, and its Stop button ends the report
def test_main_window_stops_a_tax_report(prepare_db_taxes, tmp_path, monkeypatch):
    create_ru_scenario()
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    JalIcon()
    main_window = MainWindow(None)
    try:
        main_window.ui.PrepareTaxForms.trigger()
        widget, = [x for x in main_window.ui.windowArea.windows() if isinstance(x, TaxWidget)]
        widget.ui.Year.setValue(2025)
        widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
        widget.ui.XlsFileName.setText(str(tmp_path / "report.xlsx"))
        seen = []

        def press_stop(_percent):
            seen.append((not main_window.ProgressBar.isHidden(), main_window.ProgressBar.format()))
            main_window.CancelButton.click()

        widget.update_progress.connect(press_stop)
        widget.SaveReport()
        assert seen == [(True, "Tax replay (RU): %p%")]
        assert main_window.ProgressBar.isHidden() and not (tmp_path / "report.xlsx").exists()
    finally:
        main_window.close()
        main_window.deleteLater()


# ----------------------------------------------------------------------------------------------------------------------
# The user's decisions steer the replay, and the Summary lists each one the replay applied
def _decisions(report: dict, summary: str) -> list:
    return [x['decision'] for x in report[summary] if x['report_template'] == "decision"]


# PT: a tax event on the sale swap disposes of the ETH at its 7 000 market value; the UNI then costs that
def test_pt_swap_decided_a_tax_event(prepare_db_taxes):
    create_pt_scenario()
    JalTaxOverride.set('pt', operation_id(LedgerTransaction.Swap, 1), TaxOverride.TaxEvent, '', "Ruling")

    report = TaxesPortugal().prepare_tax_report(2024, 1)
    assert [pick(x, PT_FIELDS) for x in deal_rows(report["Crypto ≥ 365 days"])] == [
        {'symbol': "ETH", 'qty': Decimal('2'), 'o_number': "buy-ETH", 'o_date': d2t(230110),
         'o_amount': Decimal('3000.00'), 'c_number': '', 'c_date': d2t(240301), 'c_amount': Decimal('7000.00'),
         'profit': Decimal('4000.00'), 'o_amount_eur': Decimal('2760.00'), 'c_amount_eur': Decimal('6440.00'),
         'profit_eur': Decimal('3680.00'), 'days': 416}]
    uni = next(x for x in deal_rows(report["Crypto < 365 days"]) if x['symbol'] == "UNI")
    assert (uni['o_amount'], uni['profit'], uni['days']) == (Decimal('3500.00'), Decimal('500.00'), 275)
    assert _decisions(report, "Summary") == ["A tax event: Ruling"]


# PT: not a tax event on the merger carries it as JAL books it; a price per received share realizes it at that price
def test_pt_merger_decided_not_a_tax_event(prepare_db_taxes):
    create_pt_scenario()
    JalTaxOverride.set('pt', operation_id(LedgerTransaction.CorporateAction, 1), TaxOverride.NotTaxEvent, '', "Ruling")

    report = TaxesPortugal().prepare_tax_report(2024, 1)
    assert [pick(x, ('symbol', 'o_date', 'o_amount', 'profit')) for x in deal_rows(report["Shares"])] == [
        {'symbol': "NEW", 'o_date': d2t(230301), 'o_amount': Decimal('2400.00'), 'profit': Decimal('1100.00')}]
    assert _decisions(report, "Summary") == ["Not a tax event: Ruling"]


def test_pt_merger_at_the_price_set(prepare_db_taxes):
    create_pt_scenario()
    JalTaxOverride.set('pt', operation_id(LedgerTransaction.CorporateAction, 1), TaxOverride.PricePerShare, '60',
                       "Exchange ratio")

    report = TaxesPortugal().prepare_tax_report(2024, 1)
    shares = deal_rows(report["Shares"])
    assert [pick(x, ('symbol', 'o_amount', 'c_amount', 'profit', 'c_type')) for x in shares] == [
        {'symbol': "NEW", 'o_amount': Decimal('3000.00'), 'c_amount': Decimal('3500.00'), 'profit': Decimal('500.00'),
         'c_type': "Venda"},
        {'symbol': "OLD", 'o_amount': Decimal('2400.00'), 'c_amount': Decimal('3000.00'), 'profit': Decimal('600.00'),
         'c_type': "Permuta"}]
    assert shares[1]['note'].startswith(TaxesPortugal.texts['exchange_price'])
    assert _decisions(report, "Summary") == ["A tax event at 60 per received share: Exchange ratio"]


# RU: not a tax event on the conversion swap carries UNI's cost and date into AVAX; the swap is listed as excluded
def test_ru_swap_decided_not_a_tax_event(prepare_db_taxes):
    create_ru_scenario()
    JalTaxOverride.set('ru', operation_id(LedgerTransaction.Swap, 1), TaxOverride.NotTaxEvent, '', "Ruling")

    report = TaxesRussia().prepare_tax_report(2025, 1)
    rows = deal_rows(report["Криптовалюты"])
    assert "UNI" not in [x['symbol'] for x in rows]
    avax = next(x for x in rows if x['symbol'] == "AVAX")
    assert (avax['o_number'], avax['o_date'], avax['o_amount'], avax['profit_rub']) == \
           ("buy-UNI", d2t(250115), Decimal('1000.00'), Decimal('47400.00'))
    assert [x['number'] for x in report["Не отражено"] if x['report_template'] == "operation"] == ['']
    assert _decisions(report, "Сводка") == ["Не налоговое событие: Ruling"]


# RU: a tax event on the merger realizes OLD at the estimate, 2 560 (51.2 x 50); NEW opens there
def test_ru_merger_decided_a_tax_event(prepare_db_taxes):
    create_pt_scenario_in_rub()
    JalTaxOverride.set('ru', operation_id(LedgerTransaction.CorporateAction, 1), TaxOverride.TaxEvent, '', "Ruling")

    report = TaxesRussia().prepare_tax_report(2024, 1)
    rows = [x for x in report["Акции"] if x['report_template'] in ("trade", "corporate_action")]
    assert [(x['c_symbol'], x['c_type'], x['cost_basis'], x['spending_rub'], x['c_amount_rub'], x['profit_rub'])
            for x in rows] == [   # the purchase prints whole, the cost share beside it
        ("NEW", "Продажа", Decimal('100'), Decimal('230400.00'), Decimal('315000.00'), Decimal('84600.00')),
        ("OLD", "Мена", Decimal('80.0'), Decimal('216000.00'), Decimal('230400.00'), Decimal('14400.00'))]
    assert rows[1]['note'].startswith(TaxesRussia.texts['exchange_decided'])
    assert _decisions(report, "Сводка") == ["Налоговое событие: Ruling"]
