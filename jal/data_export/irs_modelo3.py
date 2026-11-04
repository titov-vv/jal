from datetime import datetime, timezone
from decimal import Decimal
from PySide6.QtWidgets import QApplication

from jal.data_export.tax_parameters import TaxParameters

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

    def __init__(self, year: int):
        self._tax_form = ""
        self._parameters = TaxParameters('pt', year)

    def tr(self, text):
        return QApplication.translate("IRS_Modelo3", text)

    # The Anexo J code of a report row, read from the parameters by the row's kind
    def _code(self, row) -> str:
        codes = self._parameters.code(row['kind'])
        if codes is None:
            raise ValueError(self.tr("No Anexo J code for this kind of income: ") + row['kind'])
        return codes[0]

    def update_taxes(self, tax_report, parameters):
        country = parameters['broker_iso_country']
        for section in self.SECURITIES:
            for row in [x for x in tax_report.get(section, []) if x['report_template'] == "trade"]:
                self._tax_form += self._sale_line(row, country) + "\n"
        for row in [x for x in tax_report.get(self.DERIVATIVES, []) if x['report_template'] == "trade"]:
            self._tax_form += AnexoJ_9_2B_template.format(cc=country, code=self._code(row),
                                                          income=round(row['profit_eur'], 2)) + "\n"

    # A short sale is realized by its opening sale and acquired by its closing purchase
    def _sale_line(self, row, country) -> str:
        if row['qty'] < Decimal('0'):
            c_date, c_amount, o_date, o_amount = row['o_date'], row['o_amount_eur'], row['c_date'], row['c_amount_eur']
        else:
            c_date, c_amount, o_date, o_amount = row['c_date'], row['c_amount_eur'], row['o_date'], row['o_amount_eur']
        c_date = datetime.fromtimestamp(c_date, tz=timezone.utc)
        o_date = datetime.fromtimestamp(o_date, tz=timezone.utc)
        return AnexoJ_catG_template.format(cc=country, code=self._code(row), stock='S',
                                           fee=round(row['o_fee_eur'] + row['c_fee_eur'], 2),
                                           c_y=c_date.year, c_m=c_date.month, c_d=c_date.day,
                                           o_y=o_date.year, o_m=o_date.month, o_d=o_date.day,
                                           c_amount=round(c_amount, 2), o_amount=round(o_amount, 2))

    # Save tax form in XML-file format to be inserted into IRS Modelo 3 <AnexoJq092AT01> XML section.
    def save(self, filename):
        with open(filename, "w", encoding='utf8') as taxes:
            taxes.write(self._tax_form)
