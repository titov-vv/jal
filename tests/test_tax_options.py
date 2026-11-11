import json
import pytest
from PySide6.QtCore import QT_TRANSLATE_NOOP
from PySide6.QtWidgets import QWidget, QMessageBox, QComboBox

from tests.fixtures import project_root, data_path, prepare_db, prepare_db_taxes
from tests.helpers import d2t, create_quotes
from tests.test_taxes_pt import create_pt_scenario
from jal.data_export.taxes import TaxReport
from jal.data_export.tax_options import TaxOption, OptionType
from jal.data_export.ru_ndfl3 import Ru_NDFL3, FOREIGN_SECTION
from jal.data_export.irs_modelo3 import IRS_Modelo3
from jal.data_export.tax_reports.russia import TaxesRussia
from jal.data_export.tax_reports.portugal import TaxesPortugal
from jal.widgets.icons import JalIcon
from jal.widgets.tax_widget import TaxWidget, REPORT, FORM


# The PT scenario with the rate a RU report of it needs
def _scenario():
    create_pt_scenario()
    create_quotes(2, 1, [(d2t(230101), 90.0)])     # USD/RUB


def _dialog(code: str, year: int = 2024):
    JalIcon()   # loads the icon cache the country flags come from
    parent = QWidget()
    widget = TaxWidget(parent)
    widget.ui.Year.setValue(year)
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData(code))
    return parent, widget


# The dialog builds an editor for each option a jurisdiction's report and form file declare, set to its default
@pytest.mark.parametrize("code, report, form", [
    ('ru', {'no_settlement': False}, {'only_dividends': False, 'broker_as_income': True, 'merge_lots': False}),
    ('pt', {'use_one_currency_rate': True}, {'merge_lots': False})
])
def test_dialog_builds_declared_options(prepare_db_taxes, code, report, form):
    parent, widget = _dialog(code)
    assert widget.option_values(REPORT) == report
    assert widget.option_values(FORM) == form
    assert list(report) == [x.key for x in TaxReport.report_class(code).options]
    assert list(form) == [x.key for x in TaxReport.form_class(code).options]
    for (country, group, key), editor in widget._editors.items():
        if country == code:
            editor.setChecked(not editor.isChecked())
    assert widget.option_values(REPORT) == {k: not v for k, v in report.items()}
    assert widget.option_values(FORM) == {k: not v for k, v in form.items()}
    assert not widget.ui.FormGroup.isHidden() and not widget.ui.FormGroup.isChecked()


# A choice is a list of its labels that gives the value of the chosen one, the default at first
def test_dialog_builds_a_choice(prepare_db_taxes, monkeypatch):
    level = TaxOption('level', QT_TRANSLATE_NOOP("TaxWidget", "Level"), type=OptionType.Choice, default='b',
                      choices=(('a', "First"), ('b', "Second"), ('c', "Third")))
    monkeypatch.setattr(TaxesPortugal, "options", TaxesPortugal.options + [level])
    parent, widget = _dialog('pt')
    editor = widget._editors[('pt', REPORT, 'level')]
    assert isinstance(editor, QComboBox)
    assert [editor.itemText(i) for i in range(editor.count())] == ["First", "Second", "Third"]
    assert widget.option_values(REPORT) == {'use_one_currency_rate': True, 'level': 'b'}
    editor.setCurrentIndex(2)
    assert widget.option_values(REPORT)['level'] == 'c'
    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
    assert editor.isHidden() and 'level' not in widget.option_values(REPORT)


# A report reads the options it declares: one given by its key, any other at its default, again at every run
def test_report_reads_declared_options(prepare_db_taxes):
    _scenario()
    taxes = TaxesPortugal()
    assert taxes.option == {'use_one_currency_rate': True}
    two_rates = taxes.prepare_tax_report(2024, 1, use_one_currency_rate=False)
    assert taxes.option == {'use_one_currency_rate': False}
    one_rate = taxes.prepare_tax_report(2024, 1)
    assert taxes.option == {'use_one_currency_rate': True}
    assert one_rate["Shares"] != two_rates["Shares"]
    taxes = TaxesRussia()
    taxes.prepare_tax_report(2024, 1)
    assert taxes.texts['rate_settlement'] in taxes.section_headers("Акции")
    taxes.prepare_tax_report(2024, 1, no_settlement=True)
    assert taxes.texts['rate_trade'] in taxes.section_headers("Акции")
    assert taxes.texts['rate_settlement'] not in taxes.section_headers("Акции")


# The dialog writes the form file of the selected jurisdiction with the options ticked in it
def test_dialog_saves_the_form_file(prepare_db_taxes, tmp_path, monkeypatch):
    _scenario()
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    create_form = Ru_NDFL3.__init__   # the only form template is the one of 2025
    monkeypatch.setattr(Ru_NDFL3, "__init__", lambda self, year, **kwargs: create_form(self, 2025, **kwargs))
    parent, widget = _dialog('pt')
    widget.ui.XlsFileName.setText(str(tmp_path / "pt.xlsx"))
    widget.ui.FormGroup.setChecked(True)
    widget.ui.FormFileName.setText(str(tmp_path / "pt.xml"))
    widget.SaveReport()
    taxes = TaxesPortugal()
    form = IRS_Modelo3(2024)
    form.update_taxes(taxes.prepare_tax_report(2024, 1), taxes.sheet_parameters())
    assert (tmp_path / "pt.xml").read_text(encoding='utf8') == form._tax_form != ""

    widget.ui.Country.setCurrentIndex(widget.ui.Country.findData('ru'))
    assert not widget.update_form and widget.form_filename == ''   # a form is asked for anew for each country
    widget.ui.XlsFileName.setText(str(tmp_path / "ru.xlsx"))
    widget.ui.FormGroup.setChecked(True)
    widget.ui.FormFileName.setText(str(tmp_path / "ru.de4"))
    widget._editors[('ru', FORM, 'broker_as_income')].setChecked(False)
    widget.SaveReport()
    taxes = TaxesRussia()
    form = Ru_NDFL3(2024, broker_as_income=False)   # unticked in the dialog, which ticks it at first
    form.update_taxes(taxes.prepare_tax_report(2024, 1), taxes.sheet_parameters())
    with open(tmp_path / "ru.de4", 'r', encoding='utf-8') as file:
        saved = json.load(file)
    assert saved[FOREIGN_SECTION] == json.loads(json.dumps(form._tax_form[FOREIGN_SECTION])) != []
    default = Ru_NDFL3(2024, broker_as_income=True)
    default.update_taxes(taxes.prepare_tax_report(2024, 1), taxes.sheet_parameters())
    assert saved[FOREIGN_SECTION] != json.loads(json.dumps(default._tax_form[FOREIGN_SECTION]))
