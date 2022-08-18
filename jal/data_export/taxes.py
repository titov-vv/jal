import logging
from datetime import datetime, timezone
from decimal import Decimal

from PySide6.QtWidgets import QApplication
from jal.constants import PredefinedAsset, PredefinedCategory
from jal.db.helpers import executeSQL, readSQL
from jal.db.operations import LedgerTransaction, Dividend, CorporateAction
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.category import JalCategory
from jal.db.country import JalCountry
from jal.db.settings import JalSettings


# -----------------------------------------------------------------------------------------------------------------------
class TaxesRus:
    BOND_PRINCIPAL = Decimal('1000')  # TODO Principal should be used from 'asset_data' table

    CorpActionText = {
        CorporateAction.SymbolChange: "Смена символа {before} {old} -> {after} {new}",
        CorporateAction.Split: "Сплит {old} {before} в {after}",
        CorporateAction.SpinOff: "Выделение компании {new} из {old}; доля выделяемого актива {share:.2f}%",
        CorporateAction.Merger: "Реорганизация компании, конвертация {share:.2f}% стоимости {before} {old} в {after} {new}",
        CorporateAction.Delisting: "Делистинг"
    }

    def __init__(self):
        self.account = None
        self.year_begin = 0
        self.year_end = 0
        self.broker_name = ''
        self.broker_iso_cc = "000"
        self.use_settlement = True
        self._processed_trade_qty = {}  # It will handle {trade_id: qty} records to keep track of already processed qty
        self.reports = {
            "Дивиденды": self.prepare_dividends,
            "Акции": self.prepare_stocks_and_etf,
            "Облигации": self.prepare_bonds,
            "ПФИ": self.prepare_derivatives,
            "Криптовалюты": self.prepare_crypto,
            "Корп.события": self.prepare_corporate_actions,
            "Комиссии": self.prepare_broker_fees,
            "Проценты": self.prepare_broker_interest
        }

    def tr(self, text):
        return QApplication.translate("TaxesRus", text)

    # Removes all keys listed in extra_keys_list from operation_dict
    def drop_extra_fields(self, operation_dict, extra_keys_list):
        for key in extra_keys_list:
            if key in operation_dict:
                del operation_dict[key]

    def prepare_tax_report(self, year, account_id, **kwargs):
        tax_report = {}
        self.account = JalAccount(account_id)
        self.year_begin = int(datetime.strptime(f"{year}", "%Y").replace(tzinfo=timezone.utc).timestamp())
        self.year_end = int(datetime.strptime(f"{year + 1}", "%Y").replace(tzinfo=timezone.utc).timestamp())
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
                       "SELECT d.open_timestamp AS ref_id FROM trades_closed AS d WHERE d.account_id=:account_id "
                       "UNION "
                       "SELECT d.close_timestamp AS ref_id FROM trades_closed AS d WHERE d.account_id=:account_id "
                       "UNION "
                       "SELECT c.settlement AS ref_id FROM trades_closed AS d LEFT JOIN trades AS c ON "
                       "(c.id=d.open_op_id AND c.op_type=d.open_op_type) OR (c.id=d.close_op_id AND c.op_type=d.close_op_type) "
                       "WHERE d.account_id = :account_id) "
                       "LEFT JOIN accounts AS a ON a.id = :account_id "
                       "LEFT JOIN quotes AS q ON ref_id >= q.timestamp "
                       "AND a.currency_id=q.asset_id AND q.currency_id=:base_currency "
                       "WHERE ref_id IS NOT NULL "    
                       "GROUP BY ref_id", [(":account_id", self.account.id()),
                                           (":base_currency", JalSettings().getValue('BaseCurrency'))], commit=True)

    # ------------------------------------------------------------------------------------------------------------------
    # Create a totals row from provided list of dictionaries
    # it calculates sum for each field in fields and adds it to return dictionary
    def insert_totals(self, list_of_values, fields):
        if not list_of_values:
            return
        totals = {"report_template": "totals"}
        for field in fields:
            totals[field] = sum([float(x[field]) for x in list_of_values if field in x])   ######
        list_of_values.append(totals)

    def prepare_dividends(self):
        # TODO Include cash payments from corporate actions
        #    SELECT a.timestamp, r.qty, a.note
        #    FROM asset_actions AS a
        #    LEFT JOIN action_results AS r ON r.action_id=a.id
        #    LEFT JOIN assets AS c ON c.id=r.asset_id
        #    WHERE a.account_id=:account_id AND c.type_id=:currency
        currency = JalAsset(self.account.currency())
        dividends_report = []
        dividends = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockDividend)
        dividends += Dividend.get_list(self.account.id(), subtype=Dividend.StockVesting)
        dividends = [x for x in dividends if self.year_begin <= x.timestamp() <= self.year_end]  # Only in given range
        for dividend in dividends:
            amount = dividend.amount()
            rate = currency.quote(dividend.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            price = dividend.asset().quote(dividend.timestamp(), currency.id())[1]
            country = JalCountry(dividend.asset().country())
            tax_treaty = "Да" if country.has_tax_treaty() else "Нет"
            note = ''
            if dividend.subtype() == Dividend.StockDividend:
                if not price:
                    logging.error(self.tr("No price data for stock dividend: ") + f"{dividend}")
                    continue
                amount = amount * price
                note = "Дивиденд выплачен в натуральной форме (ценными бумагами)"
            if dividend.subtype() == Dividend.StockVesting:
                if not price:
                    logging.error(self.tr("No price data for stock vesting: ") + f"{dividend}")
                    continue
                amount = amount * price
                note = "Доход получен в натуральной форме (ценными бумагами)"
            amount_rub = amount * rate
            tax_rub = dividend.tax() * rate
            tax2pay = Decimal('0.13') * amount_rub
            if tax_treaty:
                if tax2pay > tax_rub:
                    tax2pay = tax2pay - tax_rub
                else:
                    tax2pay = Decimal('0.0')
            line = {
                'report_template': "dividend",
                'payment_date': dividend.timestamp(),
                'symbol': dividend.asset().symbol(currency.id()),
                'full_name': dividend.asset().name(),
                'isin': dividend.asset().isin(),
                'amount': amount,
                'tax': dividend.tax(),
                'rate': rate,
                'country': country.name(),
                'country_iso': country.iso_code(),
                'tax_treaty': tax_treaty,
                'amount_rub': round(amount_rub, 2),
                'tax_rub': round(tax_rub, 2),
                'tax2pay': round(tax2pay, 2),
                'note': note
            }
            dividends_report.append(line)
        self.insert_totals(dividends_report, ["amount", "amount_rub", "tax", "tax_rub", "tax2pay"])
        return dividends_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_stocks_and_etf(self):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        deals_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() in [PredefinedAsset.Stock, PredefinedAsset.ETF]]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade or (
                    x.open_operation().type() == LedgerTransaction.Dividend and (
                        x.open_operation().subtype() == Dividend.StockDividend or
                        x.open_operation().subtype() == Dividend.StockDividend))]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = currency.quote(trade.open_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            c_rate = currency.quote(trade.close_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                os_rate = currency.quote(trade.open_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
                cs_rate = currency.quote(trade.close_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            short_dividend = Decimal('0')
            if trade.qty() < Decimal('0'):  # Check were there any dividends during short position holding
                dividends = Dividend.get_list(self.account.id(), subtype=Dividend.Dividend)
                dividends = [x for x in dividends if
                             trade.open_operation().settlement() <= x.ex_date() <= trade.close_operation().settlement()]
                for dividend in dividends:
                    short_dividend += dividend.amount()
            note = f"Удержанный дивиденд: {float(short_dividend):.2f} RUB" if short_dividend > Decimal('0') else ''
            o_amount = round(trade.open_operation().price() * abs(trade.qty()), 2)
            o_amount_rub = round(o_amount * os_rate, 2)
            c_amount = round(trade.close_operation().price() * abs(trade.qty()), 2)
            c_amount_rub = round(c_amount * cs_rate, 2)
            o_fee = trade.open_operation().fee() * abs(trade.qty() / trade.open_operation().qty())
            c_fee = trade.close_operation().fee() * abs(trade.qty() / trade.close_operation().qty())
            income = c_amount if trade.qty() >=Decimal('0') else o_amount
            income_rub = c_amount_rub if trade.qty() >= Decimal('0') else o_amount_rub
            spending = o_amount if trade.qty() >=Decimal('0') else c_amount
            spending += o_fee + c_fee
            spending_rub = o_amount_rub if trade.qty() >= Decimal('0') else c_amount_rub
            spending_rub += round(o_fee * o_rate, 2) + round(c_fee * c_rate, 2) + short_dividend
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(currency.id()),
                'isin': trade.asset().isin(),
                'qty': trade.qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_operation().price(),
                'o_amount':  o_amount,
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * o_rate, 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': c_rate,
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': trade.close_operation().price(),
                'c_amount': c_amount,
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * c_rate, 2),
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub,
                's_dividend_note': note
            }
            deals_report.append(line)
        self.insert_totals(deals_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return deals_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_bonds(self):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        bonds_report = []
        accrued_interests_id = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Bond]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = currency.quote(trade.open_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            c_rate = currency.quote(trade.close_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                os_rate = currency.quote(trade.open_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
                cs_rate = currency.quote(trade.close_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            o_accrued_interest = trade.open_operation().get_accrued_interest()
            if o_accrued_interest:
                accrued_interests_id.append(o_accrued_interest.id())
                o_interest = -o_accrued_interest.amount()
            else:
                o_interest = Decimal('0')
            o_interest_rub = round(o_interest * o_rate, 2)
            c_accrued_interest = trade.close_operation().get_accrued_interest()
            if c_accrued_interest:
                accrued_interests_id.append(c_accrued_interest.id())
                c_interest = c_accrued_interest.amount()
            else:
                c_interest = Decimal('0')
            c_interest_rub = round(c_interest * c_rate, 2)
            o_amount = round(trade.open_operation().price() * abs(trade.qty()), 2)
            o_amount_rub = round(o_amount * os_rate, 2)
            c_amount = round(trade.close_operation().price() * abs(trade.qty()), 2)
            c_amount_rub = round(c_amount * cs_rate, 2)
            o_fee = trade.open_operation().fee() * abs(trade.qty() / trade.open_operation().qty())
            c_fee = trade.close_operation().fee() * abs(trade.qty() / trade.close_operation().qty())
            # FIXME accrued interest calculations for short deals is not clear - to be corrected
            income = c_amount + c_interest if trade.qty() >= Decimal('0') else o_amount
            income_rub = c_amount_rub + c_interest_rub if trade.qty() >= Decimal('0') else o_amount_rub
            spending = o_amount + o_interest if trade.qty() >= Decimal('0') else c_amount
            spending += o_fee + c_fee
            spending_rub = o_amount_rub + o_interest_rub if trade.qty() >= Decimal('0') else c_amount_rub
            spending_rub += round(o_fee * o_rate, 2) + round(c_fee * c_rate, 2)
            line = {
                'report_template': "bond_trade",
                'symbol': trade.asset().symbol(currency.id()),
                'isin': trade.asset().isin(),
                'qty': trade.qty(),
                'principal': self.BOND_PRINCIPAL,
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': Decimal('100') * trade.open_operation().price() / self.BOND_PRINCIPAL,
                'o_int': o_interest,
                'o_int_rub': o_interest_rub,
                'o_amount': o_amount,
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * o_rate, 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': c_rate,
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': Decimal('100') * trade.close_operation().price() / self.BOND_PRINCIPAL,
                'c_int': c_interest,
                'c_int_rub': c_interest_rub,
                'c_amount': c_amount,
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * c_rate, 2),
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub
            }
            bonds_report.append(line)
        # Second - take all bond interest payments not linked with buy/sell transactions
        currency = JalAsset(self.account.currency())
        interests = Dividend.get_list(self.account.id(), subtype=Dividend.BondInterest)
        interests = [x for x in interests if self.year_begin <= x.timestamp() <= self.year_end]  # Only in given range
        interests = [x for x in interests if x.id() not in accrued_interests_id]  # Skip already processed
        for interest in interests:
            amount = interest.amount()
            rate = currency.quote(interest.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            amount_rub = round(amount * rate, 2)
            country = JalCountry(interest.asset().country())
            line = {
                'report_template': "bond_interest",
                'type': "Купон",
                'empty': '',  # to keep cell borders drawn
                'o_date': interest.timestamp(),
                'symbol': interest.asset().symbol(currency.id()),
                'isin': interest.asset().isin(),
                'number': interest.number(),
                'interest': amount,
                'rate': rate,
                'interest_rub': amount_rub,
                'income_rub': amount_rub,
                'spending_rub': Decimal('0.0'),
                'profit': amount,
                'profit_rub': amount_rub,
                'country_iso': country.iso_code(),
            }
            bonds_report.append(line)
        self.insert_totals(bonds_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return bonds_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_derivatives(self):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        derivatives_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Derivative]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = currency.quote(trade.open_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            c_rate = currency.quote(trade.close_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                os_rate = currency.quote(trade.open_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
                cs_rate = currency.quote(trade.close_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            o_amount = round(trade.open_operation().price() * abs(trade.qty()), 2)
            o_amount_rub = round(o_amount * os_rate, 2)
            c_amount = round(trade.close_operation().price() * abs(trade.qty()), 2)
            c_amount_rub = round(c_amount * cs_rate, 2)
            o_fee = trade.open_operation().fee() * abs(trade.qty() / trade.open_operation().qty())
            c_fee = trade.close_operation().fee() * abs(trade.qty() / trade.close_operation().qty())
            income = c_amount if trade.qty() >= Decimal('0') else o_amount
            income_rub = c_amount_rub if trade.qty() >= Decimal('0') else o_amount_rub
            spending = o_amount if trade.qty() >= Decimal('0') else c_amount
            spending += o_fee + c_fee
            spending_rub = o_amount_rub if trade.qty() >= Decimal('0') else c_amount_rub
            spending_rub += round(o_fee * o_rate, 2) + round(c_fee * c_rate, 2)
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(currency.id()),
                'qty': trade.qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_operation().price(),
                'o_amount': o_amount,
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * o_rate, 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': c_rate,
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': trade.close_operation().price(),
                'c_amount': c_amount,
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * c_rate, 2),
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub
            }
            derivatives_report.append(line)
        self.insert_totals(derivatives_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return derivatives_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_crypto(self):
        currency = JalAsset(self.account.currency())
        country = JalCountry(self.account.country())
        crypto_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.asset().type() == PredefinedAsset.Crypto]
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if self.year_begin <= x.close_operation().settlement() <= self.year_end]
        for trade in trades:
            o_rate = currency.quote(trade.open_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            c_rate = currency.quote(trade.close_operation().timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                os_rate = currency.quote(trade.open_operation().settlement(), JalSettings().getValue('BaseCurrency'))[1]
                cs_rate = currency.quote(trade.close_operation().settlement(), JalSettings().getValue('BaseCurrency'))[
                    1]
            else:
                os_rate = o_rate
                cs_rate = c_rate
            o_amount = round(trade.open_operation().price() * abs(trade.qty()), 2)
            o_amount_rub = round(o_amount * os_rate, 2)
            c_amount = round(trade.close_operation().price() * abs(trade.qty()), 2)
            c_amount_rub = round(c_amount * cs_rate, 2)
            o_fee = trade.open_operation().fee() * abs(trade.qty() / trade.open_operation().qty())
            c_fee = trade.close_operation().fee() * abs(trade.qty() / trade.close_operation().qty())
            income = c_amount if trade.qty() >= Decimal('0') else o_amount
            income_rub = c_amount_rub if trade.qty() >= Decimal('0') else o_amount_rub
            spending = o_amount if trade.qty() >= Decimal('0') else c_amount
            spending += o_fee + c_fee
            spending_rub = o_amount_rub if trade.qty() >= Decimal('0') else c_amount_rub
            spending_rub += round(o_fee * o_rate, 2) + round(c_fee * c_rate, 2)
            line = {
                'report_template': "trade",
                'symbol': trade.asset().symbol(currency.id()),
                'qty': trade.qty(),
                'country_iso': country.iso_code(),
                'o_type': "Покупка" if trade.qty() >= Decimal('0') else "Продажа",
                'o_number': trade.open_operation().number(),
                'o_date': trade.open_operation().timestamp(),
                'o_rate': o_rate,
                'os_date': trade.open_operation().settlement(),
                'os_rate': os_rate,
                'o_price': trade.open_operation().price(),
                'o_amount': o_amount,
                'o_amount_rub': o_amount_rub,
                'o_fee': o_fee,
                'o_fee_rub': round(o_fee * o_rate, 2),
                'c_type': "Продажа" if trade.qty() >= Decimal('0') else "Покупка",
                'c_number': trade.close_operation().number(),
                'c_date': trade.close_operation().timestamp(),
                'c_rate': c_rate,
                'cs_date': trade.close_operation().settlement(),
                'cs_rate': cs_rate,
                'c_price': trade.close_operation().price(),
                'c_amount': c_amount,
                'c_amount_rub': c_amount_rub,
                'c_fee': c_fee,
                'c_fee_rub': round(c_fee * c_rate, 2),
                'income_rub': income_rub,
                'spending_rub': spending_rub,
                'profit': income - spending,
                'profit_rub': income_rub - spending_rub
            }
            crypto_report.append(line)
        self.insert_totals(crypto_report, ["income_rub", "spending_rub", "profit_rub", "profit"])
        return crypto_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_broker_fees(self):
        currency = JalAsset(self.account.currency())
        fees_report = []
        fee_operations = JalCategory(PredefinedCategory.Fees).get_operations(self.year_begin, self.year_end)
        for operation in fee_operations:
            rate = currency.quote(operation.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            fees = [x for x in operation.lines() if x['category_id'] == PredefinedCategory.Fees]
            for fee in fees:
                amount = -Decimal(fee['amount'])
                line = {
                    'report_template': "fee",
                    'payment_date': operation.timestamp(),
                    'rate': rate,
                    'amount': amount,
                    'amount_rub': round(amount * rate, 2),
                    'note': fee['note']
                }
                fees_report.append(line)
        self.insert_totals(fees_report, ["amount", "amount_rub"])
        return fees_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_broker_interest(self):
        currency = JalAsset(self.account.currency())
        interests_report = []
        interest_operations = JalCategory(PredefinedCategory.Interest).get_operations(self.year_begin, self.year_end)
        for operation in interest_operations:
            rate = currency.quote(operation.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            interests = [x for x in operation.lines() if x['category_id'] == PredefinedCategory.Interest]
            for interest in interests:
                amount = Decimal(interest['amount'])
                line = {
                    'report_template': "interest",
                    'payment_date': operation.timestamp(),
                    'rate': rate,
                    'amount': amount,
                    'amount_rub': round(amount * rate, 2),
                    'tax_rub': round(Decimal('0.13') * amount * rate, 2),
                    'note': interest['note']
                }
                interests_report.append(line)
        self.insert_totals(interests_report, ["amount", "amount_rub", "tax_rub"])
        return interests_report

    # -----------------------------------------------------------------------------------------------------------------------
    def prepare_corporate_actions(self):
        currency = JalAsset(self.account.currency())
        corporate_actions_report = []
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.Trade]
        trades = [x for x in trades if x.open_operation().type() == LedgerTransaction.CorporateAction]
        trades = [x for x in trades if x.close_operation().settlement() <= self.year_end]   # TODO Why not self.year_begin<=?
        trades = sorted(trades, key=lambda x: (x.asset().symbol(currency.id()), x.close_operation().timestamp()))
        group = 1
        share = Decimal('1.0')   # This will track share of processed asset, so it starts from 100.0%
        previous_symbol = ""
        for trade in trades:
            lines = []
            sale = trade.close_operation()
            t_rate = currency.quote(sale.timestamp(), JalSettings().getValue('BaseCurrency'))[1]
            if self.use_settlement:
                s_rate = currency.quote(sale.settlement(), JalSettings().getValue('BaseCurrency'))[1]
            else:
                s_rate = t_rate
            if previous_symbol != sale.asset().symbol(currency.id()):
                # Clean processed qty records if symbol have changed
                self._processed_trade_qty = {}
                if sale.settlement() >= self.year_begin:  # Don't put sub-header of operation is out of scope
                    corporate_actions_report.append({
                        'report_template': "symbol_header",
                        'report_group': 0,
                        'description': f"Сделки по бумаге: {sale.asset().symbol(currency.id())} - {sale.asset().name()}"
                    })
                    previous_symbol = sale.asset().symbol(currency.id())
            amount = round(sale.price() * trade.qty(), 2)
            amount_rub = round(amount * s_rate, 2)
            fee_rub = round(sale.fee() * t_rate, 2)
            if sale.timestamp() < self.year_begin:    # Don't show deal that is before report year (level = -1)
                self.proceed_corporate_action(lines, trade, trade.qty(), share, -1, group)
            else:
                lines.append({
                    'report_template': "trade",
                    'report_group': group,
                    'operation': "Продажа",
                    't_date': sale.timestamp(),
                    't_rate': t_rate,
                    's_date': sale.settlement(),
                    's_rate': s_rate,
                    'symbol': sale.asset().symbol(currency.id()),
                    'isin': sale.asset().isin(),
                    'trade_number': sale.number(),
                    'price': sale.price(),
                    'qty': trade.qty(),
                    'amount': amount,
                    'amount_rub': amount_rub,
                    'fee': sale.fee(),
                    'fee_rub': fee_rub,
                    'basis_ratio': Decimal('100') * share,
                    'income_rub': amount_rub,
                    'spending_rub': fee_rub
                })
                if sale.asset().type() == PredefinedAsset.Bond:
                    self.output_accrued_interest(lines, sale.number(), 1, 0)
                self.proceed_corporate_action(lines, trade, trade.qty(), share, 1, group)
            self.insert_totals(lines, ["income_rub", "spending_rub"])
            corporate_actions_report += lines
            group += 1
        return corporate_actions_report

    # actions - mutable list of tax records to output into json-report
    # trade - JalClosedTrade object, for which we need to proceed with opening corporate action
    # qty - amount of asset to process
    # share - value share that is being processed currently
    # level - how deep we are in a chain of events (is used for correct indents)
    # group - use for odd/even lines grouping in the report
    def proceed_corporate_action(self, actions, trade, qty, share, level, group):
        asset_id, qty, share = self.output_corp_action(actions, trade.open_operation().id(), trade.asset().id(), qty, share, level, group)
        next_level = -1 if level == -1 else (level + 1)
        self.next_corporate_action(actions, trade, qty, share, next_level, group)

    def next_corporate_action(self, actions, trade, qty, share, level, group):
        # get list of deals that were closed as result of current corporate action
        trades = self.account.closed_trades_list()
        trades = [x for x in trades if x.close_operation().type() == LedgerTransaction.CorporateAction]
        trades = [x for x in trades if x.close_operation().id() == trade.open_operation().id()]
        for item in trades:
            if item.open_operation().type() == LedgerTransaction.Trade:
                qty = self.output_purchase(actions, item.open_operation().id(), qty, share, level, group)
            elif item.open_operation().type() == LedgerTransaction.CorporateAction:
                self.proceed_corporate_action(actions, trade, qty, share, level, group)
            else:
                assert False, "Unexpected opening transaction"

    # oid - id of buy operation
    def output_purchase(self, actions, oid, proceed_qty, share, level, group):
        if proceed_qty <= 0:
            return proceed_qty
        purchase = readSQL("SELECT t.id AS trade_id, s.symbol, s.isin AS isin, s.type_id AS type_id, "
                           "d.qty AS qty, t.timestamp AS t_date, qt.quote AS t_rate, t.number AS trade_number, "
                           "t.settlement AS s_date, qts.quote AS s_rate, t.price AS price, t.fee AS fee "
                           "FROM trades AS t "
                           "JOIN trades_closed AS d ON t.id=d.open_op_id AND t.op_type=d.open_op_type "
                           "LEFT JOIN accounts AS a ON a.id = t.account_id "
                           "LEFT JOIN assets_ext AS s ON s.id = t.asset_id AND s.currency_id=a.currency_id "
                           "LEFT JOIN t_last_dates AS ldt ON t.timestamp=ldt.ref_id "
                           "LEFT JOIN quotes AS qt ON ldt.timestamp=qt.timestamp AND a.currency_id=qt.asset_id AND qt.currency_id=:base_currency "
                           "LEFT JOIN t_last_dates AS ldts ON t.settlement=ldts.ref_id "
                           "LEFT JOIN quotes AS qts ON ldts.timestamp=qts.timestamp AND a.currency_id=qts.asset_id AND qts.currency_id=:base_currency "
                           "WHERE t.id = :oid", [(":oid", oid),
                                                 (":base_currency", JalSettings().getValue('BaseCurrency'))],
                           named=True)
        if purchase['trade_id'] in self._processed_trade_qty:   # we have some qty processed already
            purchase['qty'] = float(purchase['qty']) - self._processed_trade_qty[purchase['trade_id']]
        else:
            purchase['qty'] = float(purchase['qty'])
        purchase['t_rate'] = float(purchase['t_rate'])
        purchase['s_rate'] = float(purchase['s_rate'])
        purchase['price'] = float(purchase['price'])
        purchase['fee'] = float(purchase['fee'])
        if purchase['qty'] <= 1e-9:   # FIXME All taxes module should be refactored to decimal usage also
            return proceed_qty  # This trade was fully mached before
        purchase['operation'] = ' ' * level * 3 + "Покупка"
        purchase['basis_ratio'] = 100.0 * float(share)    ######
        deal_qty = purchase['qty']
        purchase['qty'] = float(proceed_qty) if proceed_qty < deal_qty else deal_qty   ######
        purchase['amount'] = round(purchase['price'] * purchase['qty'], 2)
        purchase['amount_rub'] = round(purchase['amount'] * purchase['s_rate'], 2) if purchase['s_rate'] else 0
        purchase['fee'] = purchase['fee'] * purchase['qty'] / deal_qty
        purchase['fee_rub'] = round(purchase['fee'] * purchase['t_rate'], 2) if purchase['t_rate'] else 0
        purchase['income_rub'] = 0
        purchase['spending_rub'] = round(float(share)*(purchase['amount_rub'] + purchase['fee_rub']), 2)   ######
        # Update processed quantity for current purchase operation
        self._processed_trade_qty[purchase['trade_id']] = self._processed_trade_qty.get(purchase['trade_id'], 0) + purchase['qty']
        if level >= 0:  # Don't output if level==-1, i.e. corp action is out of report scope
            purchase['report_template'] = "trade"
            purchase['report_group'] = group
            actions.append(purchase)
        if purchase['type_id'] == PredefinedAsset.Bond:
            share = purchase['qty'] / deal_qty if purchase['qty'] < deal_qty else 1
            self.output_accrued_interest(actions, purchase['trade_number'], share, level)
        return float(proceed_qty) - purchase['qty']    #########

    def output_corp_action(self, actions, oid, asset_id, proceed_qty, share, level, group):
        if proceed_qty <= 0:
            return proceed_qty, share
        action = readSQL("SELECT c.timestamp AS action_date, c.number AS action_number, c.type, "
                         "c.asset_id, s1.symbol AS symbol, s1.isin AS isin, c.qty AS qty, "
                         "c.note AS note, r.qty AS qty2, r.value_share, s2.symbol AS symbol2, s2.isin AS isin2 "
                         "FROM asset_actions  c "
                         "LEFT JOIN accounts a ON c.account_id=a.id "
                         "LEFT JOIN action_results r ON c.id=r.action_id "
                         "LEFT JOIN assets_ext s1 ON c.asset_id=s1.id AND s1.currency_id=a.currency_id "
                         "LEFT JOIN assets_ext s2 ON r.asset_id=s2.id AND s2.currency_id=a.currency_id "
                         "WHERE c.id = :oid AND r.asset_id = :new_asset", [(":oid", oid), (":new_asset", asset_id)],
                         named=True)
        action['qty'] = float(action['qty'])
        action['qty2'] = float(action['qty2'])
        action['value_share'] = float(action['value_share'])
        action['operation'] = ' ' * level * 3 + "Корп. действие"
        share = float(share) * action['value_share']    #######
        qty_before = action['qty'] * float(proceed_qty) / action['qty2']    #######
        if action['type'] == CorporateAction.SpinOff:
            spinoff = readSQL("SELECT s1.symbol AS symbol, s1.isin AS isin, "
                              "r.value_share, s2.symbol AS symbol2, s2.isin AS isin2 "
                              "FROM asset_actions  c "
                              "LEFT JOIN accounts a ON c.account_id=a.id "
                              "LEFT JOIN action_results r ON c.id=r.action_id AND c.asset_id!=r.asset_id "
                              "LEFT JOIN assets_ext s1 ON c.asset_id=s1.id AND s1.currency_id=a.currency_id "
                              "LEFT JOIN assets_ext s2 ON r.asset_id=s2.id AND s2.currency_id=a.currency_id "
                              "WHERE c.id = :oid", [(":oid", oid)], named=True)
            spinoff['value_share'] = float(spinoff['value_share'])
            old_asset_name = f"{spinoff['symbol']} ({spinoff['isin']})"
            new_asset_name = f"{spinoff['symbol2']} ({spinoff['isin2']})"
            display_share = 100.0 * spinoff['value_share']
        else:
            old_asset_name = f"{action['symbol']} ({action['isin']})"
            new_asset_name = f"{action['symbol2']} ({action['isin2']})"
            display_share = 100.0 * action['value_share']
        action['description'] = self.CorpActionText[action['type']].format(old=old_asset_name, new=new_asset_name,
                                                                           before=qty_before, after=proceed_qty,
                                                                           share=display_share)
        if level >= 0:  # Don't output if level==-1, i.e. corp action is out of report scope
            action['report_template'] = "action"
            action['report_group'] = group
            self.drop_extra_fields(action, ['oid', 'isin2', 'qty2', 'symbol2', 'value_share'])
            actions.append(action)
        return action['asset_id'], Decimal(str(qty_before)), Decimal(str(share))   ####

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
                           [(":account_id", self.account.id()), (":interest", Dividend.BondInterest),
                            (":trade_number", trade_number),
                            (":base_currency", JalSettings().getValue('BaseCurrency'))], named=True)
        if interest is None:
            return
        interest['interest'] = float(interest['interest'])
        interest['rate'] = float(interest['rate'])
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
