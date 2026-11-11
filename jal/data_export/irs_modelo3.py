from datetime import datetime, timezone
from decimal import Decimal
from PySide6.QtCore import QT_TRANSLATE_NOOP
from PySide6.QtWidgets import QApplication

from jal.data_export.tax_parameters import TaxParameters
from jal.data_export.tax_options import TaxOption
from jal.data_export.tax_grouping import Grouping, merge_deals
from jal.data_export.tax_reports.portugal import TaxesPortugal

# ----------------------------------------------------------------------------------------------------------------------
# Basic template for AnexoJq092AT01-Linha that represents one sale of foreign asset taxable as Category G
# Replacements:
# {cc} - 3-digit country code
# {code} - Anexo J code of the kind of asset (G01 shares, G20 fund units, G10 bonds)
# {c_y}, {c_m}, {c_d} - date of realization (sale) in YYYY, M, D format
# {o_y}, {o_m}, {o_d} - date of acquisition (purchase) in YYYY, M, D format
# {c_amount} - amount of realization (sale) in EUR
# {o_amount} - amount of acquisition (purchase) in EUR
# {fee} - expenses in EUR related to these operations
# {stock} - can have value S (Sim) or N (Nao) to indicate if this line is for stock/ETF or not
AnexoJ_catG_template = "<AnexoJq092AT01-Linha><CodPais>{cc}</CodPais><Codigo>{code}</Codigo><AnoRealizacao>{c_y}</AnoRealizacao><MesRealizacao>{c_m}</MesRealizacao><DiaRealizacao>{c_d}</DiaRealizacao><ValorRealizacao>{c_amount}</ValorRealizacao><AnoAquisicao>{o_y}</AnoAquisicao><MesAquisicao>{o_m}</MesAquisicao><DiaAquisicao>{o_d}</DiaAquisicao><ValorAquisicao>{o_amount}</ValorAquisicao><DespesasEncargos>{fee}</DespesasEncargos><RespeitaValoresMobiliarios>{stock}</RespeitaValoresMobiliarios></AnexoJq092AT01-Linha>"

# Stub of a quadro 9.2B line (derivatives, one net income per line): element and field names not yet checked against
# the AT's schema
AnexoJ_9_2B_template = "<AnexoJq092BT01-Linha><CodPais>{cc}</CodPais><Codigo>{code}</Codigo><Rendimento>{income}</Rendimento></AnexoJq092BT01-Linha>"


# ----------------------------------------------------------------------------------------------------------------------
class IRS_Modelo3:
    SECURITIES = ("Shares", "Bonds")   # report sections written as quadro 9.2A lines
    DERIVATIVES = "Derivatives"        # report section written as quadro 9.2B lines
    # What the tax dialog shows for the file; the options are the keyword arguments of the class
    title = QT_TRANSLATE_NOOP("TaxWidget", "Create XML records to introduce in Modelo-3 form")
    file_prompt = QT_TRANSLATE_NOOP("TaxWidget", "Save IRS Modelo 3 tax data to:")
    needs_broker = False
    options = [
        TaxOption('merge_lots', QT_TRANSLATE_NOOP("TaxWidget",
                                                  "Merge lots of one security bought on one day and sold on one day"))
    ]

    # The (filter, extension) of the file of a year
    @staticmethod
    def file_type(year: int) -> tuple:
        return QT_TRANSLATE_NOOP("TaxWidget", "XML files (*.xml)"), ".xml"

    def __init__(self, year: int, merge_lots=False):
        self._tax_form = ""
        self._merge_lots = merge_lots
        self._parameters = TaxParameters('pt', year)

    def tr(self, text):
        return QApplication.translate("IRS_Modelo3", text)

    # The Anexo J code of a report row, read from the parameters by the row's kind
    def _code(self, row) -> str:
        codes = self._parameters.code(row['kind'])
        if codes is None:
            raise ValueError(self.tr("No Anexo J code for this kind of income: ") + row['kind'])
        return codes[0]

    # 'parameters' are those of the report's account; with several accounts each account's header row carries its own
    def update_taxes(self, tax_report, parameters):
        for section in self.SECURITIES:
            rows = tax_report.get(section, [])
            if self._merge_lots:   # a line has one date of acquisition and one of realization
                rows = merge_deals(rows, TaxesPortugal.deal_fields, Grouping.Days)
            for row, country in self._trades(rows, parameters):
                self._tax_form += self._sale_line(row, country) + "\n"
        for row, country in self._trades(tax_report.get(self.DERIVATIVES, []), parameters):
            self._tax_form += AnexoJ_9_2B_template.format(cc=country, code=self._code(row),
                                                          income=round(row['profit_eur'], 2)) + "\n"

    # The trade rows of a section, each with the broker country of its account
    @staticmethod
    def _trades(rows: list, parameters: dict) -> list:
        country, trades = parameters['broker_iso_country'], []
        for row in rows:
            if row['report_template'] == "account":
                country = row['broker_iso_country']
            elif row['report_template'] == "trade":
                trades.append((row, country))
        return trades

    # A short sale is realized by its opening sale and acquired by its closing purchase; the expenses are rounded
    # for each deal, as its cost on the sheet is
    def _sale_line(self, row, country) -> str:
        fee = sum(round(x['o_fee_eur'] + x['c_fee_eur'], 2) for x in row.get('merged', [row]))
        if row['qty'] < Decimal('0'):
            c_date, c_amount, o_date, o_amount = row['o_date'], row['o_amount_eur'], row['c_date'], row['c_amount_eur']
        else:
            c_date, c_amount, o_date, o_amount = row['c_date'], row['c_amount_eur'], row['o_date'], row['o_amount_eur']
        c_date = datetime.fromtimestamp(c_date, tz=timezone.utc)
        o_date = datetime.fromtimestamp(o_date, tz=timezone.utc)
        return AnexoJ_catG_template.format(cc=country, code=self._code(row), stock='S', fee=fee,
                                           c_y=c_date.year, c_m=c_date.month, c_d=c_date.day,
                                           o_y=o_date.year, o_m=o_date.month, o_d=o_date.day,
                                           c_amount=round(c_amount, 2), o_amount=round(o_amount, 2))

    # Save tax form in XML-file format to be inserted into IRS Modelo 3 <AnexoJq092AT01> XML section.
    def save(self, filename):
        with open(filename, "w", encoding='utf8') as taxes:
            taxes.write(self._tax_form)
