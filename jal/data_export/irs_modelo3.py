import logging
from datetime import datetime, timezone
from PySide6.QtWidgets import QApplication

# ----------------------------------------------------------------------------------------------------------------------
# Basic template for AnexoJq092AT01-Linha that represents one sale of foreign asset taxable as Category G
# Replacements:
# {cc} - 3-digit country code
# {c_y}, {c_m}, {c_d} - date of realization (sale) in YYYY, M, D format
# {o_y}, {o_m}, {o_d} - date of acquisition (purchase) in YYYY, M, D format
# {c_amount} - amount of realization (sale) in EUR
# {o_amount} - amount of acquisition (purchase) in EUR
# {fee} - expenses in EUR related to these operations
AnexoJ_catG_template = "<AnexoJq092AT01-Linha><CodPais>{cc}</CodPais><Codigo>G01</Codigo><AnoRealizacao>{c_y}</AnoRealizacao><MesRealizacao>{c_m}</MesRealizacao><DiaRealizacao>{c_d}</DiaRealizacao><ValorRealizacao>{c_amount}</ValorRealizacao><AnoAquisicao>{o_y}</AnoAquisicao><MesAquisicao>{o_m}</MesAquisicao><DiaAquisicao>{o_d}</DiaAquisicao><ValorAquisicao>{o_amount}</ValorAquisicao><DespesasEncargos>{fee}</DespesasEncargos></AnexoJq092AT01-Linha>"

# ----------------------------------------------------------------------------------------------------------------------
class IRS_Modelo3:
    def __init__(self):
        self._tax_form = ""

    def tr(self, text):
        return QApplication.translate("IRS_Modelo3", text)

    def update_taxes(self, tax_report, parameters):
        country = parameters['broker_iso_country']
        for report_line in [x for x in tax_report['Shares'] if x['report_template'] == "trade"]:
            c_date = datetime.fromtimestamp(report_line['c_date'], tz=timezone.utc)
            o_date = datetime.fromtimestamp(report_line['o_date'], tz=timezone.utc)
            tax_line = AnexoJ_catG_template.format(cc=country, fee=round(report_line['o_fee_eur'] + report_line['c_fee_eur'], 2),
                                                   c_y=c_date.year, c_m=c_date.month, c_d=c_date.day,
                                                   o_y=o_date.year, o_m=o_date.month, o_d=o_date.day,
                                                   c_amount=round(report_line['c_amount_eur'], 2), o_amount=round(report_line['o_amount_eur'], 2))
            self._tax_form += tax_line + "\n"

    # Save tax form in XML-file format to be inserted into IRS Modelo 3 <AnexoJq092AT01> XML section.
    def save(self, filename):
        with open(filename, "w", encoding='utf8') as taxes:
            taxes.write(self._tax_form)
