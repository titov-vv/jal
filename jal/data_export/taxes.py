import logging
from datetime import datetime, timezone

from PySide6.QtWidgets import QApplication
from jal.constants import Setup, PredefinedAsset, PredefinedCategory
from jal.db.helpers import executeSQL, readSQLrecord, readSQL
from jal.db.operations import LedgerTransaction, Dividend, CorporateAction
from jal.db.settings import JalSettings


# -----------------------------------------------------------------------------------------------------------------------
class TaxesRus:
    BOND_PRINCIPAL = 1000  # TODO Principal should be used from 'asset_data' table

    CorpActionText = {
        CorporateAction.SymbolChange: "Смена символа {before} {old} -> {after} {new}",
        CorporateAction.Split: "Сплит {old} {before} в {after}",
        CorporateAction.SpinOff: "Выделение компании {after} {new} из {before:.6f} {old}; доля выделяемого актива {ratio:.2f}%",
        CorporateAction.Merger: "Слияние компании, конвертация {before} {old} в {after} {new}"
    }

    def __init__(self):
        self.account_id = 0
        self.year_begin = 0
        self.year_end = 0
        self.account_currency = ''
        self.account_number = ''
        self.broker_name = ''
        self.broker_iso_cc = "000"
        self.use_settlement = True
        self.reports = {
            "Дивиденды": self.prepare_dividends,
            "Акции": self.prepare_stocks_and_etf,
            "Облигации": self.prepare_bonds,
            "ПФИ": self.prepare_derivatives,
            "Корп.события": self.prepare_corporate_actions,
            "Комиссии": self.prepare_broker_fees,
            "Проценты": self.prepare_broker_interest
        }

    def tr(self, text):
        return QApplication.translate("TaxesRus", text)

    def prepare_tax_report(self, year, account_id, **kwargs):
        tax_report = {}
        self.account_id = account_id
        self.account_number, self.account_currency = \
            readSQL("SELECT a.number, c.symbol FROM accounts AS a "
                    "LEFT JOIN currencies c ON a.currency_id = c.id WHERE a.id=:account",
                    [(":account", account_id)])
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.broker_name, self.broker_iso_cc = readSQL("SELECT b.name AS broker_name, c.iso_code AS country_iso_code "
                                                       "FROM accounts AS a "
                                                       "LEFT JOIN agents AS b ON a.organization_id = b.id "
                                                       "LEFT JOIN countries AS c ON a.country_id = c.id "
                                                       "WHERE a.id=:account", [(":account", account_id)])
        if 'use_settlement' in kwargs:
            self.use_settlement = kwargs['use_settlement']

        self.prepare_exchange_rate_dates()
        for report in self.reports:
            tax_report[report] = self.reports[report]()

        return tax_report

    # Exchange rates are present in database not for every date (and not every possible timestamp)
    # As any action has exact timestamp it won't match rough timestamp of exchange rate most probably
    # Function fills 't_last_dates' table with correspondence between 'real' timestamp and nearest 'exchange' timestamp
    def prepare_exchange_rate_dates(self):
        _ = executeSQL("DELETE FROM t_last_dates")
        _ = executeSQL("INSERT INTO t_last_dates(ref_id, timestamp) "
                       "SELECT ref_id, coalesce(MAX(q.timestamp), 0) AS timestamp "
                       "FROM ("
                       "SELECT d.timestamp AS ref_id FROM dividends AS d WHERE d.account_id = :account_id "
                       "UNION "
                       "SELECT a.timestamp AS ref_id FROM actions AS a WHERE a.account_id = :account_id "
                       "UNION "
                       "SELECT d.open_timestamp AS ref_id FROM deals AS d WHERE d.account_id=:account_id "
                       "UNION "
                       "SELECT d.close_timestamp AS ref_id FROM deals AS d WHERE d.account_id=:account_id "
                       "UNION "
                       "SELECT c.settlement AS ref_id FROM deals AS d LEFT JOIN trades AS c ON "
                       "(c.id=d.open_op_id AND c.op_type=d.open_op_type) OR (c.id=d.close_op_id AND c.op_type=d.close_op_type) "
                       "WHERE d.account_id = :account_id) "
                       "LEFT JOIN accounts AS a ON a.id = :account_id "
                       "LEFT JOIN quotes AS q ON ref_id >= q.timestamp "
                       "AND a.currency_id=q.asset_id AND q.currency_id=:base_currency "
                       "WHERE ref_id IS NOT NULL "    
                       "GROUP BY ref_id", [(":account_id", self.account_id),
                                           (":base_currency", JalSettings().getValue('BaseCurrency'))], commit=True)

    # ------------------------------------------------------------------------------------------------------------------
    # Create a totals row from provided list of dictionaries
    # it calculates sum for each field in fields and adds it to return dictionary
    def insert_totals(self, list_of_values, fields):
        if not list_of_values:
            return
        totals = {"report_template": "totals"}
        for field in fields:
            totals[field] = sum([x[field] for x in list_of_values if field in x])
        list_of_values.append(totals)

    def prepare_dividends(self):
        dividends = []
        query = executeSQL("SELECT d.type, d.timestamp AS payment_date, s.symbol, s.full_name AS full_name, "
                           "s.isin AS isin, d.amount AS amount, d.tax AS tax, q.quote AS rate, p.quote AS price, "
                           "c.name AS country, c.iso_code AS country_iso, c.tax_treaty AS tax_treaty "
                           "FROM dividends AS d "
                           "LEFT JOIN accounts AS a ON d.account_id = a.id "
                           "LEFT JOIN assets_ext AS s ON s.id = d.asset_id AND s.currency_id=a.currency_id "
                           "LEFT JOIN countries AS c ON s.country_id = c.id "
                           "LEFT JOIN t_last_dates AS ld ON d.timestamp=ld.ref_id "
                           "LEFT JOIN quotes AS q ON ld.timestamp=q.timestamp AND a.currency_id=q.asset_id AND q.currency_id=:base_currency "
                           "LEFT JOIN quotes AS p ON d.timestamp=p.timestamp AND d.asset_id=p.asset_id AND p.currency_id=a.currency_id "                           
                           "WHERE d.timestamp>=:begin AND d.timestamp<:end AND d.account_id=:account_id "
                           " AND d.amount>0 AND (d.type=:type_dividend OR d.type=:type_stock_dividend) "
                           "ORDER BY d.timestamp",
                           [(":begin", self.year_begin), (":end", self.year_end), (":account_id", self.account_id),
                            (":base_currency", JalSettings().getValue('BaseCurrency')),
                            (":type_dividend", Dividend.Dividend), (":type_stock_dividend", Dividend.StockDividend)])
        while query.next():
            dividend = readSQLrecord(query, named=True)
            dividend["note"] = ''
            if dividend["type"] == Dividend.StockDividend:
                if not dividend["price"]:
                    logging.error(self.tr("No price data for stock dividend: ") + f"{dividend}")
                    continue
                dividend["amount"] = dividend["amount"] * dividend["price"]
                dividend["note"] = "Дивиденд выплачен в натуральной форме (ценными бумагами)"
            dividend["amount_rub"] = round(dividend["amount"] * dividend["rate"], 2) if dividend["rate"] else 0
            dividend["tax_rub"] = round(dividend["tax"] * dividend["rate"], 2) if dividend["rate"] else 0
            dividend["tax2pay"] = round(0.13 * dividend["amount_rub"], 2)
            if dividend["tax_treaty"]:
                if dividend["tax2pay"] > dividend["tax_rub"]:
                    dividend["tax2pay"] = dividend["tax2pay"] - dividend["tax_rub"]
                else:
                    dividend["tax2pay"] = 0
            dividend['tax_treaty'] = "Да" if dividend['tax_treaty'] else "Нет"
            dividend['report_template'] = "dividend"
            del dividend['type']
            del dividend['price']
            dividends.append(dividend)
        self.insert_totals(dividends, ["amount", "amount_rub", "tax", "tax_rub", "tax2pay"])
        return dividends

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_stocks_and_etf(self):
        deals = []
        # Take all actions without conversion
        query = executeSQL("SELECT s.symbol AS symbol, s.isin AS isin, d.qty AS qty, cc.iso_code AS country_iso, "
                           "o.timestamp AS o_date, qo.quote AS o_rate, o.settlement AS os_date, o.number AS o_number, "
                           "qos.quote AS os_rate, o.price AS o_price, o.qty AS o_qty, o.fee AS o_fee, "
                           "c.timestamp AS c_date, qc.quote AS c_rate, c.settlement AS cs_date, c.number AS c_number, "
                           "qcs.quote AS cs_rate, c.price AS c_price, c.qty AS c_qty, c.fee AS c_fee, "
                           "SUM(coalesce(-sd.amount*qsd.quote, 0)) AS s_dividend "  # Dividend paid for short position
                           "FROM deals AS d "
                           "JOIN trades AS o ON o.id=d.open_op_id AND o.op_type=d.open_op_type "
                           "JOIN trades AS c ON c.id=d.close_op_id AND c.op_type=d.close_op_type "
                           "LEFT JOIN accounts AS a ON a.id = :account_id "
                           "LEFT JOIN assets_ext AS s ON s.id = o.asset_id AND s.currency_id=a.currency_id "
                           "LEFT JOIN countries AS cc ON cc.id = a.country_id "
                           "LEFT JOIN t_last_dates AS ldo ON o.timestamp=ldo.ref_id "
                           "LEFT JOIN quotes AS qo ON ldo.timestamp=qo.timestamp AND a.currency_id=qo.asset_id AND qo.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldos ON o.settlement=ldos.ref_id "
                           "LEFT JOIN quotes AS qos ON ldos.timestamp=qos.timestamp AND a.currency_id=qos.asset_id AND qos.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldc ON c.timestamp=ldc.ref_id "
                           "LEFT JOIN quotes AS qc ON ldc.timestamp=qc.timestamp AND a.currency_id=qc.asset_id AND qc.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldcs ON c.settlement=ldcs.ref_id "
                           "LEFT JOIN quotes AS qcs ON ldcs.timestamp=qcs.timestamp AND a.currency_id=qcs.asset_id AND qcs.currency_id=:base_currency "
                           "LEFT JOIN dividends AS sd ON d.asset_id=sd.asset_id AND sd.amount<0 "  # Include dividends paid from short positions
                           "AND sd.ex_date>=o_date AND sd.ex_date<=c_date "
                           "LEFT JOIN t_last_dates AS ldsd ON sd.timestamp=ldsd.ref_id "
                           "LEFT JOIN quotes AS qsd ON ldsd.timestamp=qsd.timestamp AND a.currency_id=qsd.asset_id AND qsd.currency_id=:base_currency "
                           "WHERE c.settlement>=:begin AND c.settlement<:end AND d.account_id=:account_id "
                           "AND (s.type_id = :stock OR s.type_id = :fund) "
                           "GROUP BY d.rowid "  # to prevent collapse to 1 line if 'sd' values are NULL
                           "ORDER BY s.symbol, o.timestamp, c.timestamp",
                           [(":begin", self.year_begin), (":end", self.year_end), (":account_id", self.account_id),
                            (":base_currency", JalSettings().getValue('BaseCurrency')),
                            (":stock", PredefinedAsset.Stock), (":fund", PredefinedAsset.ETF)])
        while query.next():
            deal = readSQLrecord(query, named=True)
            if not deal['symbol']:   # there will be row of NULLs if no deals are present (due to SUM aggregation)
                continue
            if not self.use_settlement:
                deal['os_rate'] = deal['o_rate']
                deal['cs_rate'] = deal['c_rate']
            deal['o_type'] = "Покупка" if deal['qty'] >= 0 else "Продажа"
            deal['c_type'] = "Продажа" if deal['qty'] >= 0 else "Покупка"
            deal['o_amount'] = round(deal['o_price'] * abs(deal['qty']), 2)
            deal['o_amount_rub'] = round(deal['o_amount'] * deal['os_rate'], 2) if deal['os_rate'] else 0
            deal['c_amount'] = round(deal['c_price'] * abs(deal['qty']), 2)
            deal['c_amount_rub'] = round(deal['c_amount'] * deal['cs_rate'], 2) if deal['cs_rate'] else 0
            deal['o_fee'] = deal['o_fee'] * abs(deal['qty'] / deal['o_qty'])
            deal['c_fee'] = deal['c_fee'] * abs(deal['qty'] / deal['c_qty'])
            deal['o_fee_rub'] = round(deal['o_fee'] * deal['o_rate'], 2) if deal['o_rate'] else 0
            deal['c_fee_rub'] = round(deal['c_fee'] * deal['c_rate'], 2) if deal['c_rate'] else 0
            deal['income_rub'] = deal['c_amount_rub'] if deal['qty'] >= 0 else deal['o_amount_rub']
            deal['income'] = deal['c_amount'] if deal['qty'] >= 0 else deal['o_amount']
            deal['spending_rub'] = deal['o_amount_rub'] if deal['qty'] >= 0 else deal['c_amount_rub']
            deal['spending_rub'] = deal['spending_rub'] + deal['o_fee_rub'] + deal['c_fee_rub'] + deal['s_dividend']
            deal['spending'] = deal['o_amount'] if deal['qty'] >= 0 else deal['c_amount']
            deal['spending'] = deal['spending'] + deal['o_fee'] + deal['c_fee']
            deal['profit_rub'] = deal['income_rub'] - deal['spending_rub']
            deal['profit'] = deal['income'] - deal['spending']
            if deal['s_dividend'] > 0:  # Dividend was paid during short position
                deal['s_dividend_note'] = f"Удержанный дивиденд: {deal['s_dividend']:.2f} RUB"
            else:
                deal['s_dividend_note'] = ''
            deal['report_template'] = "trade"
            deals.append(deal)
        self.insert_totals(deals, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return deals

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_bonds(self):
        bonds = []
        # First put all closed deals with bonds
        query = executeSQL("SELECT s.symbol AS symbol, s.isin AS isin, d.qty AS qty, cc.iso_code AS country_iso, "
                           "o.timestamp AS o_date, qo.quote AS o_rate, o.settlement AS os_date, o.number AS o_number, "
                           "qos.quote AS os_rate, o.price AS o_price, o.qty AS o_qty, o.fee AS o_fee, -oi.amount AS o_int, "
                           "c.timestamp AS c_date, qc.quote AS c_rate, c.settlement AS cs_date, c.number AS c_number, "
                           "qcs.quote AS cs_rate, c.price AS c_price, c.qty AS c_qty, c.fee AS c_fee, ci.amount AS c_int "
                           "FROM deals AS d "
                           "JOIN trades AS o ON o.id=d.open_op_id AND o.op_type=d.open_op_type "
                           "LEFT JOIN dividends AS oi ON oi.account_id=:account_id AND oi.number=o.number AND oi.timestamp=o.timestamp AND oi.asset_id=o.asset_id "
                           "JOIN trades AS c ON c.id=d.close_op_id AND c.op_type=d.close_op_type "
                           "LEFT JOIN dividends AS ci ON ci.account_id=:account_id AND ci.number=c.number AND ci.timestamp=c.timestamp AND ci.asset_id=c.asset_id "
                           "LEFT JOIN accounts AS a ON a.id = :account_id "
                           "LEFT JOIN assets_ext AS s ON s.id = o.asset_id AND s.currency_id=a.currency_id "
                           "LEFT JOIN countries AS cc ON cc.id = a.country_id "
                           "LEFT JOIN t_last_dates AS ldo ON o.timestamp=ldo.ref_id "
                           "LEFT JOIN quotes AS qo ON ldo.timestamp=qo.timestamp AND a.currency_id=qo.asset_id AND qo.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldos ON o.settlement=ldos.ref_id "
                           "LEFT JOIN quotes AS qos ON ldos.timestamp=qos.timestamp AND a.currency_id=qos.asset_id AND qos.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldc ON c.timestamp=ldc.ref_id "
                           "LEFT JOIN quotes AS qc ON ldc.timestamp=qc.timestamp AND a.currency_id=qc.asset_id AND qc.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldcs ON c.settlement=ldcs.ref_id "
                           "LEFT JOIN quotes AS qcs ON ldcs.timestamp=qcs.timestamp AND a.currency_id=qcs.asset_id AND qcs.currency_id=:base_currency "
                           "WHERE c.settlement>=:begin AND c.settlement<:end AND d.account_id=:account_id "
                           "AND s.type_id = :bond "
                           "ORDER BY s.symbol, o.timestamp, c.timestamp",
                           [(":begin", self.year_begin), (":end", self.year_end), (":account_id", self.account_id),
                            (":base_currency", JalSettings().getValue('BaseCurrency')),
                            (":bond", PredefinedAsset.Bond)])
        while query.next():
            deal = readSQLrecord(query, named=True)
            deal['principal'] = self.BOND_PRINCIPAL
            if not self.use_settlement:
                deal['os_rate'] = deal['o_rate']
                deal['cs_rate'] = deal['c_rate']
            deal['o_type'] = "Покупка" if deal['qty'] >= 0 else "Продажа"
            deal['c_type'] = "Продажа" if deal['qty'] >= 0 else "Покупка"
            deal['o_amount'] = round(deal['o_price'] * abs(deal['qty']), 2)
            deal['o_amount_rub'] = round(deal['o_amount'] * deal['os_rate'], 2) if deal['os_rate'] else 0
            deal['c_amount'] = round(deal['c_price'] * abs(deal['qty']), 2)
            deal['c_amount_rub'] = round(deal['c_amount'] * deal['cs_rate'], 2) if deal['cs_rate'] else 0
            # Convert price from currency to % of principal
            deal['o_price'] = 100.0 * deal['o_price'] / deal['principal']
            deal['c_price'] = 100.0 * deal['c_price'] / deal['principal']

            deal['o_fee'] = deal['o_fee'] * abs(deal['qty'] / deal['o_qty'])
            deal['c_fee'] = deal['c_fee'] * abs(deal['qty'] / deal['c_qty'])
            deal['o_fee_rub'] = round(deal['o_fee'] * deal['o_rate'], 2) if deal['o_rate'] else 0
            deal['c_fee_rub'] = round(deal['c_fee'] * deal['c_rate'], 2) if deal['c_rate'] else 0
            deal['o_int_rub'] = round(deal['o_int'] * deal['o_rate'], 2) if deal['o_rate'] and deal['o_int'] else 0
            deal['c_int_rub'] = round(deal['c_int'] * deal['o_rate'], 2) if deal['o_rate'] and deal['c_int'] else 0
            # TODO accrued interest calculations for short deals is not clear - to be corrected
            deal['income_rub'] = deal['c_amount_rub'] + deal['c_int_rub'] if deal['qty'] >= 0 else deal['o_amount_rub']
            deal['income'] = deal['c_amount'] if deal['qty'] >= 0 else deal['o_amount']
            deal['spending_rub'] = deal['o_amount_rub'] if deal['qty'] >= 0 else deal['c_amount_rub']
            deal['spending_rub'] = deal['spending_rub'] + deal['o_fee_rub'] + deal['c_fee_rub'] + deal['o_int_rub']
            deal['spending'] = deal['o_amount'] if deal['qty'] >= 0 else deal['c_amount']
            deal['spending'] = deal['spending'] + deal['o_fee'] + deal['c_fee']
            deal['profit_rub'] = deal['income_rub'] - deal['spending_rub']
            deal['profit'] = deal['income'] - deal['spending']
            deal['report_template'] = "bond_trade"
            bonds.append(deal)

        # Second - take all bond interest payments not linked with buy/sell transactions
        query = executeSQL("SELECT b.symbol AS symbol, b.isin AS isin, i.timestamp AS o_date, i.number AS number, "
                           "i.amount AS interest, r.quote AS rate, cc.iso_code AS country_iso "
                           "FROM dividends AS i "
                           "LEFT JOIN trades AS t ON i.account_id=t.account_id AND i.number=t.number "
                           "AND i.timestamp=t.timestamp AND i.asset_id=t.asset_id "
                           "LEFT JOIN accounts AS a ON a.id = i.account_id "
                           "LEFT JOIN assets_ext AS b ON b.id = i.asset_id AND b.currency_id=a.currency_id "
                           "LEFT JOIN countries AS cc ON cc.id = a.country_id "
                           "LEFT JOIN t_last_dates AS ld ON i.timestamp=ld.ref_id "
                           "LEFT JOIN quotes AS r ON ld.timestamp=r.timestamp AND a.currency_id=r.asset_id AND r.currency_id=:base_currency "
                           "WHERE i.timestamp>=:begin AND i.timestamp<:end AND i.account_id=:account_id "
                           "AND i.type = :type_interest AND t.id IS NULL",
                           [(":begin", self.year_begin), (":end", self.year_end), (":account_id", self.account_id),
                            (":base_currency", JalSettings().getValue('BaseCurrency')),
                            (":type_interest", Dividend.BondInterest)])
        while query.next():
            interest = readSQLrecord(query, named=True)
            interest['type'] = "Купон"
            interest['empty'] = ''  # to keep cell borders drawn
            interest['interest_rub'] = round(interest['interest'] * interest['rate'], 2) if interest['rate'] else 0
            interest['income_rub'] = interest['profit_rub'] = interest['interest_rub']
            interest['spending_rub'] = 0.0
            interest['profit'] = interest['interest']
            interest['report_template'] = "bond_interest"
            bonds.append(interest)
        self.insert_totals(bonds, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return bonds

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_derivatives(self):
        derivatives = []
        # Take all actions without conversion
        query = executeSQL("SELECT s.symbol, d.qty AS qty, cc.iso_code AS country_iso, "
                           "o.timestamp AS o_date, qo.quote AS o_rate, o.settlement AS os_date, o.number AS o_number, "
                           "qos.quote AS os_rate, o.price AS o_price, o.qty AS o_qty, o.fee AS o_fee, "
                           "c.timestamp AS c_date, qc.quote AS c_rate, c.settlement AS cs_date, c.number AS c_number, "
                           "qcs.quote AS cs_rate, c.price AS c_price, c.qty AS c_qty, c.fee AS c_fee "
                           "FROM deals AS d "
                           "JOIN trades AS o ON o.id=d.open_op_id AND o.op_type=d.open_op_type "
                           "JOIN trades AS c ON c.id=d.close_op_id AND c.op_type=d.close_op_type "
                           "LEFT JOIN accounts AS a ON a.id = :account_id "
                           "LEFT JOIN assets_ext AS s ON s.id = o.asset_id AND s.currency_id=a.currency_id "
                           "LEFT JOIN countries AS cc ON cc.id = a.country_id "
                           "LEFT JOIN t_last_dates AS ldo ON o.timestamp=ldo.ref_id "
                           "LEFT JOIN quotes AS qo ON ldo.timestamp=qo.timestamp AND a.currency_id=qo.asset_id AND qo.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldos ON o.settlement=ldos.ref_id "
                           "LEFT JOIN quotes AS qos ON ldos.timestamp=qos.timestamp AND a.currency_id=qos.asset_id AND qos.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldc ON c.timestamp=ldc.ref_id "
                           "LEFT JOIN quotes AS qc ON ldc.timestamp=qc.timestamp AND a.currency_id=qc.asset_id AND qc.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldcs ON c.settlement=ldcs.ref_id "
                           "LEFT JOIN quotes AS qcs ON ldcs.timestamp=qcs.timestamp AND a.currency_id=qcs.asset_id AND qcs.currency_id=:base_currency "
                           "WHERE c.settlement>=:begin AND c.settlement<:end AND d.account_id=:account_id "
                           "AND s.type_id = :derivative "
                           "ORDER BY s.symbol, o.timestamp, c.timestamp",
                           [(":begin", self.year_begin), (":end", self.year_end), (":account_id", self.account_id),
                            (":base_currency", JalSettings().getValue('BaseCurrency')),
                            (":derivative", PredefinedAsset.Derivative)])
        while query.next():
            deal = readSQLrecord(query, named=True)
            if not self.use_settlement:
                deal['os_rate'] = deal['o_rate']
                deal['cs_rate'] = deal['c_rate']
            deal['o_type'] = "Покупка" if deal['qty'] >= 0 else "Продажа"
            deal['c_type'] = "Продажа" if deal['qty'] >= 0 else "Покупка"
            deal['o_amount'] = round(deal['o_price'] * abs(deal['qty']), 2)
            deal['o_amount_rub'] = round(deal['o_amount'] * deal['os_rate'], 2) if deal['os_rate'] else 0
            deal['c_amount'] = round(deal['c_price'] * abs(deal['qty']), 2)
            deal['c_amount_rub'] = round(deal['c_amount'] * deal['cs_rate'], 2) if deal['cs_rate'] else 0
            deal['o_fee'] = deal['o_fee'] * abs(deal['qty'] / deal['o_qty'])
            deal['c_fee'] = deal['c_fee'] * abs(deal['qty'] / deal['c_qty'])
            deal['o_fee_rub'] = round(deal['o_fee'] * deal['o_rate'], 2) if deal['o_rate'] else 0
            deal['c_fee_rub'] = round(deal['c_fee'] * deal['c_rate'], 2) if deal['c_rate'] else 0
            deal['income_rub'] = deal['c_amount_rub'] if deal['qty'] >= 0 else deal['o_amount_rub']
            deal['income'] = deal['c_amount'] if deal['qty'] >= 0 else deal['o_amount']
            deal['spending_rub'] = deal['o_amount_rub'] if deal['qty'] >= 0 else deal['c_amount_rub']
            deal['spending_rub'] = deal['spending_rub'] + deal['o_fee_rub'] + deal['c_fee_rub']
            deal['spending'] = deal['o_amount'] if deal['qty'] >= 0 else deal['c_amount']
            deal['spending'] = deal['spending'] + deal['o_fee'] + deal['c_fee']
            deal['profit_rub'] = deal['income_rub'] - deal['spending_rub']
            deal['profit'] = deal['income'] - deal['spending']
            deal['report_template'] = "trade"
            derivatives.append(deal)
        self.insert_totals(derivatives, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return derivatives

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_broker_fees(self):
        fees = []
        query = executeSQL("SELECT a.timestamp AS payment_date, d.amount AS amount, d.note AS note, q.quote AS rate "
                           "FROM actions AS a "
                           "LEFT JOIN action_details AS d ON d.pid=a.id "
                           "LEFT JOIN accounts AS c ON c.id = :account_id "
                           "LEFT JOIN t_last_dates AS ld ON a.timestamp=ld.ref_id "
                           "LEFT JOIN quotes AS q ON ld.timestamp=q.timestamp AND c.currency_id=q.asset_id AND q.currency_id=:base_currency "
                           "WHERE a.timestamp>=:begin AND a.timestamp<:end "
                           "AND a.account_id=:account_id AND d.category_id=:fee",
                           [(":begin", self.year_begin), (":end", self.year_end),
                            (":account_id", self.account_id), (":fee", PredefinedCategory.Fees),
                            (":base_currency", JalSettings().getValue('BaseCurrency'))])
        while query.next():
            fee = readSQLrecord(query, named=True)
            fee['amount'] = -fee['amount']
            fee['amount_rub'] = round(fee['amount'] * fee['rate'], 2) if fee['rate'] else 0
            fee['report_template'] = "fee"
            fees.append(fee)
        self.insert_totals(fees, ["amount", "amount_rub"])
        return fees

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_broker_interest(self):
        interests = []
        query = executeSQL("SELECT a.timestamp AS payment_date, d.amount AS amount, d.note AS note, q.quote AS rate "
                           "FROM actions AS a "
                           "LEFT JOIN action_details AS d ON d.pid=a.id "
                           "LEFT JOIN accounts AS c ON c.id = :account_id "
                           "LEFT JOIN t_last_dates AS ld ON a.timestamp=ld.ref_id "
                           "LEFT JOIN quotes AS q ON ld.timestamp=q.timestamp AND c.currency_id=q.asset_id AND q.currency_id=:base_currency "
                           "WHERE a.timestamp>=:begin AND a.timestamp<:end "
                           "AND a.account_id=:account_id AND d.category_id=:fee",
                           [(":begin", self.year_begin), (":end", self.year_end),
                            (":account_id", self.account_id), (":fee", PredefinedCategory.Interest),
                            (":base_currency", JalSettings().getValue('BaseCurrency'))])
        while query.next():
            interest = readSQLrecord(query, named=True)
            interest['amount'] = interest['amount']
            interest['amount_rub'] = round(interest['amount'] * interest['rate'], 2) if interest['rate'] else 0
            interest['tax_rub'] = round(0.13 * interest['amount_rub'], 2)
            interest['report_template'] = "interest"
            interests.append(interest)
        self.insert_totals(interests, ["amount", "amount_rub", "tax_rub"])
        return interests

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_corporate_actions(self):
        corp_actions = []
        # get list of all deals that were opened with corp.action and closed by normal trade
        query = executeSQL("SELECT d.open_op_id AS operation_id, s.symbol, d.qty AS qty, "
                           "t.number AS trade_number, t.timestamp AS t_date, qt.quote AS t_rate, "
                           "t.settlement AS s_date, qts.quote AS s_rate, t.price AS price, t.fee AS fee, "
                           "s.full_name AS full_name, s.isin AS isin, s.type_id AS type_id "
                           "FROM deals AS d "
                           "JOIN trades AS t ON t.id=d.close_op_id AND t.op_type=d.close_op_type "
                           "LEFT JOIN accounts AS a ON a.id = :account_id "
                           "LEFT JOIN assets_ext AS s ON s.id = t.asset_id AND s.currency_id=a.currency_id "
                           "LEFT JOIN t_last_dates AS ldt ON t.timestamp=ldt.ref_id "
                           "LEFT JOIN quotes AS qt ON ldt.timestamp=qt.timestamp AND a.currency_id=qt.asset_id AND qt.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldts ON t.settlement=ldts.ref_id "
                           "LEFT JOIN quotes AS qts ON ldts.timestamp=qts.timestamp AND a.currency_id=qts.asset_id AND qts.currency_id=:base_currency "
                           "WHERE t.settlement<:end AND d.account_id=:account_id AND d.open_op_type=:corp_action "
                           "ORDER BY s.symbol, t.timestamp",
                           [(":end", self.year_end), (":account_id", self.account_id),
                            (":corp_action", LedgerTransaction.CorporateAction),
                            (":base_currency", JalSettings().getValue('BaseCurrency'))])
        group = 1
        basis = 1
        previous_symbol = ""
        while query.next():
            actions = []
            sale = readSQLrecord(query, named=True)
            if previous_symbol != sale['symbol']:
                # Clean processed qty records if symbol have changed
                _ = executeSQL("DELETE FROM t_last_assets")
                if sale["s_date"] >= self.year_begin:  # Don't put sub-header of operation is out of scope
                    corp_actions.append({'report_template': "symbol_header",
                                    'report_group': 0,
                                    'description': f"Сделки по бумаге: {sale['symbol']} - {sale['full_name']}"})
                    previous_symbol = sale['symbol']
            sale['operation'] = "Продажа"
            sale['basis_ratio'] = 100.0 * basis
            sale['amount'] = round(sale['price'] * sale['qty'], 2)
            if sale['s_rate']:
                sale['amount_rub'] = round(sale['amount'] * sale['s_rate'], 2)
            else:
                sale['amount_rub'] = 0
            if sale['t_rate']:
                sale['fee_rub'] = round(sale['fee'] * sale['t_rate'], 2)
            else:
                sale['fee_rub'] = 0
            sale['income_rub'] = sale['amount_rub']
            sale['spending_rub'] = sale['fee_rub']

            if sale["t_date"] < self.year_begin:    # Don't show deal that is before report year (level = -1)
                self.proceed_corporate_action(actions, sale['operation_id'], sale['symbol'], sale['qty'], basis, -1, group)
            else:
                sale['report_template'] = "trade"
                sale['report_group'] = group
                actions.append(sale)
                if sale['type_id'] == PredefinedAsset.Bond:
                    self.output_accrued_interest(actions, sale['trade_number'], 1, 0)
                self.proceed_corporate_action(actions, sale['operation_id'], sale['symbol'], sale['qty'], basis, 1, group)

            self.insert_totals(actions, ["income_rub", "spending_rub"])
            corp_actions += actions
            group += 1
        return corp_actions

    def proceed_corporate_action(self, actions, operation_id, symbol, qty, basis, level, group):
        qty, symbol, basis = self.output_corp_action(actions, operation_id, symbol, qty, basis, level, group)
        next_level = -1 if level == -1 else (level + 1)
        self.next_corporate_action(actions, operation_id, symbol, qty, basis, next_level, group)

    # operation_id - id of corporate action
    def next_corporate_action(self, actions, operation_id, symbol, qty, basis, level, group):
        # get list of deals that were closed as result of current corporate action
        open_query = executeSQL("SELECT open_op_id AS open_op_id, open_op_type AS op_type "
                                "FROM deals "
                                "WHERE close_op_id=:close_op_id AND close_op_type=:corp_action "
                                "ORDER BY id",
                                [(":close_op_id", operation_id), (":corp_action", LedgerTransaction.CorporateAction)])
        while open_query.next():
            open_id, open_type = readSQLrecord(open_query)

            if open_type == LedgerTransaction.Trade:
                qty = self.output_purchase(actions, open_id, qty, basis, level, group)
            elif open_type == LedgerTransaction.CorporateAction:
                self.proceed_corporate_action(actions, open_id, symbol, qty, basis, level, group)
            else:
                assert False

    # operation_id - id of buy operation
    def output_purchase(self, actions, operation_id, proceed_qty, basis, level, group):
        if proceed_qty <= 0:
            return proceed_qty

        purchase = readSQL("SELECT t.id AS trade_id, s.symbol, s.isin AS isin, s.type_id AS type_id, "
                           "coalesce(d.qty-SUM(lq.total_value), d.qty) AS qty, "
                           "t.timestamp AS t_date, qt.quote AS t_rate, t.number AS trade_number, "
                           "t.settlement AS s_date, qts.quote AS s_rate, t.price AS price, t.fee AS fee "
                           "FROM trades AS t "
                           "JOIN deals AS d ON t.id=d.open_op_id AND t.op_type=d.open_op_type "
                           "LEFT JOIN accounts AS a ON a.id = t.account_id "
                           "LEFT JOIN assets_ext AS s ON s.id = t.asset_id AND s.currency_id=a.currency_id "
                           "LEFT JOIN t_last_dates AS ldt ON t.timestamp=ldt.ref_id "
                           "LEFT JOIN quotes AS qt ON ldt.timestamp=qt.timestamp AND a.currency_id=qt.asset_id AND qt.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldts ON t.settlement=ldts.ref_id "
                           "LEFT JOIN quotes AS qts ON ldts.timestamp=qts.timestamp AND a.currency_id=qts.asset_id AND qts.currency_id=:base_currency "
                           "LEFT JOIN t_last_assets AS lq ON lq.id = t.id "
                           "WHERE t.id = :operation_id", [(":operation_id", operation_id),
                                                          (":base_currency", JalSettings().getValue('BaseCurrency'))],
                           named=True)
        if purchase['qty'] <= (2 * Setup.CALC_TOLERANCE):
            return proceed_qty  # This trade was fully mached before

        purchase['operation'] = ' ' * level * 3 + "Покупка"
        purchase['basis_ratio'] = 100.0 * basis
        deal_qty = purchase['qty']
        purchase['qty'] = proceed_qty if proceed_qty < deal_qty else deal_qty
        purchase['amount'] = round(purchase['price'] * purchase['qty'], 2)
        purchase['amount_rub'] = round(purchase['amount'] * purchase['s_rate'], 2) if purchase['s_rate'] else 0
        purchase['fee'] = purchase['fee'] * purchase['qty'] / deal_qty
        purchase['fee_rub'] = round(purchase['fee'] * purchase['t_rate'], 2) if purchase['t_rate'] else 0
        purchase['income_rub'] = 0
        purchase['spending_rub'] = round(basis*(purchase['amount_rub'] + purchase['fee_rub']), 2)

        _ = executeSQL("INSERT INTO t_last_assets (id, total_value) VALUES (:trade_id, :qty)",
                       [(":trade_id", purchase['trade_id']), (":qty", purchase['qty'])])
        if level >= 0:  # Don't output if level==-1, i.e. corp action is out of report scope
            purchase['report_template'] = "trade"
            purchase['report_group'] = group
            actions.append(purchase)
        if purchase['type_id'] == PredefinedAsset.Bond:
            share = purchase['qty'] / deal_qty if purchase['qty'] < deal_qty else 1
            self.output_accrued_interest(actions, purchase['trade_number'], share, level)
        return proceed_qty - purchase['qty']

    def output_corp_action(self, actions, operation_id, symbol, proceed_qty, basis, level, group):
        if proceed_qty <= 0:
            return proceed_qty

        action = readSQL("SELECT c.timestamp AS action_date, c.number AS action_number, c.type, "
                         "s1.symbol AS symbol, s1.isin AS isin, c.qty AS qty, "
                         "s2.symbol AS symbol_new, s2.isin AS isin_new, c.qty_new AS qty_new, "
                         "c.note AS note, c.basis_ratio "
                         "FROM corp_actions  c "
                         "LEFT JOIN accounts a ON c.account_id=a.id "
                         "LEFT JOIN assets_ext  s1 ON c.asset_id=s1.id AND s1.currency_id=a.currency_id "
                         "LEFT JOIN assets_ext  s2 ON c.asset_id_new=s2.id AND s1.currency_id=a.currency_id "
                         "WHERE c.id = :operation_id ",
                         [(":operation_id", operation_id)], named=True)
        action['operation'] = ' ' * level * 3 + "Корп. действие"
        old_asset = f"{action['symbol']} ({action['isin']})"
        new_asset = f"{action['symbol_new']} ({action['isin_new']})"
        if action['type'] == CorporateAction.SpinOff:
            action['description'] = self.CorpActionText[action['type']].format(old=old_asset, new=new_asset,
                                                                               before=action['qty'],
                                                                               after=action['qty_new'],
                                                                               ratio=100.0 * action['basis_ratio'])
            if symbol == action['symbol_new']:
                basis = basis * action['basis_ratio']
                qty_before = action['qty'] * proceed_qty / action['qty_new']
            else:
                basis = basis * (1 - action['basis_ratio'])
                qty_before = action['qty']
        else:
            qty_before = action['qty'] * proceed_qty / action['qty_new']
            qty_after = proceed_qty
            action['description'] = self.CorpActionText[action['type']].format(old=old_asset, new=new_asset,
                                                                               before=qty_before, after=qty_after)
        if level >= 0:  # Don't output if level==-1, i.e. corp action is out of report scope
            action['report_template'] = "action"
            action['report_group'] = group
            actions.append(action)
        return qty_before, action['symbol'], basis

    def output_accrued_interest(self, actions, trade_number, share, level):
        interest = readSQL("SELECT b.symbol AS symbol, b.isin AS isin, i.timestamp AS o_date, i.number AS number, "
                           "i.amount AS interest, r.quote AS rate, cc.iso_code AS country_iso "
                           "FROM dividends AS i "
                           "LEFT JOIN accounts AS a ON a.id = i.account_id "
                           "LEFT JOIN assets_ext AS b ON b.id = i.asset_id AND b.currency_id=a.currency_id "
                           "LEFT JOIN countries AS cc ON cc.id = a.country_id "
                           "LEFT JOIN t_last_dates AS ld ON i.timestamp=ld.ref_id "
                           "LEFT JOIN quotes AS r ON ld.timestamp=r.timestamp AND a.currency_id=r.asset_id AND r.currency_id=:base_currency "
                           "WHERE i.account_id=:account_id AND i.type=:interest AND i.number=:trade_number",
                           [(":account_id", self.account_id), (":interest", Dividend.BondInterest),
                            (":trade_number", trade_number),
                            (":base_currency", JalSettings().getValue('BaseCurrency'))], named=True)
        if interest is None:
            return
        interest['empty'] = ''
        interest['interest'] = interest['interest'] if share == 1 else share * interest['interest']
        interest['interest_rub'] = abs(round(interest['interest'] * interest['rate'], 2)) if interest['rate'] else 0
        if interest['interest'] < 0:  # Accrued interest paid for purchase
            interest['interest'] = -interest['interest']
            interest['operation'] = ' ' * level * 3 + "НКД уплачен"
            interest['spending_rub'] = interest['interest_rub']
            interest['income_rub'] = 0.0
        else:                         # Accrued interest received for sale
            interest['operation'] = ' ' * level * 3 + "НКД получен"
            interest['income_rub'] = interest['interest_rub']
            interest['spending_rub'] = 0.0
        interest['report_template'] = "bond_interest"
        actions.append(interest)
