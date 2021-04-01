import logging
import math
import re
import pandas
from datetime import datetime, timezone

from jal.constants import DividendSubtype
from jal.widgets.helpers import g_tr
from jal.db.update import JalDB


# -----------------------------------------------------------------------------------------------------------------------
# Strip white spaces from numbers imported form Quik html-report
def convert_amount(val):
    val = val.replace(' ', '')
    try:
        res = float(val)
    except ValueError:
        res = 0
    return res


# -----------------------------------------------------------------------------------------------------------------------
class Quik:
    ClientPattern = "^Код клиента: (.*)$"
    DateTime = 'Дата и время заключения сделки'
    TradeNumber = 'Номер сделки'
    Symbol = 'Код инструмента'
    Name = 'Краткое наименование инструмента'
    Type = 'Направление'
    Qty = 'Кол-во'
    Price = 'Цена'
    Amount = 'Объём'
    Coupon = 'НКД'
    SettleDate = 'Дата расчётов'
    Buy = 'Купля'
    Sell = 'Продажа'
    Fee = 'Комиссия Брокера'
    FeeEx = 'Суммарная комиссия ТС'    # This line is used in KIT Broker reports
    FeeEx1 = 'Комиссия за ИТС'         # Below 3 lines are used in Uralsib Borker reports
    FeeEx2 = 'Комиссия за организацию торговли'
    FeeEx3 = 'Клиринговая комиссия'
    Total = 'ИТОГО'

    def __init__(self, filename):
        self._filename = filename

    def load(self):
        try:
            data = pandas.read_html(self._filename, encoding='cp1251',
                                    converters={self.Qty: convert_amount, self.Amount: convert_amount,
                                                self.Price: convert_amount, self.Coupon: convert_amount})
        except:
            logging.error(g_tr('Quik', "Can't read statement file"))
            return False

        report_info = data[0]
        deals_info = data[1]
        parts = re.match(self.ClientPattern, report_info[0][2])
        if parts:
            account_id = JalDB().get_account_id(parts.group(1))
        else:
            logging.error(g_tr('Quik', "Can't get account number from the statement."))
            return False
        if account_id is None:
            logging.error(g_tr('Quik', "Account with number ") + f"{parts.group(1)}" +
                          g_tr('Quik', " not found. Import cancelled."))
            return False

        for index, row in deals_info.iterrows():
            if row[self.Type] == self.Buy:
                qty = int(row[self.Qty])
            elif row[self.Type] == self.Sell:
                qty = -int(row[self.Qty])
            elif row[self.Type][:len(self.Total)] == self.Total:
                break  # End of statement reached
            else:
                logging.warning(g_tr('Quik', "Unknown operation type ") + f"'{row[self.Type]}'")
                continue
            asset_id = JalDB().get_asset_id(row[self.Symbol])
            if asset_id is None:
                logging.warning(g_tr('Quik', "Unknown asset ") + f"'{row[self.Symbol]}'")
                continue
            timestamp = int(
                datetime.strptime(row[self.DateTime], "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            settlement = int(
                datetime.strptime(row[self.SettleDate], "%d.%m.%Y").replace(tzinfo=timezone.utc).timestamp())
            number = row[self.TradeNumber]
            price = row[self.Price]
            amount = row[self.Amount]
            lot_size = math.pow(10, round(math.log10(amount / (price * abs(qty)))))
            qty = qty * lot_size
            fee = float(row[self.Fee])
            if self.FeeEx in row:  # Broker dependent fee import
                fee = fee + float(row[self.FeeEx])
            else:
                fee = fee + float(row[self.FeeEx1]) + float(row[self.FeeEx2]) + float(row[self.FeeEx3])
            bond_interest = float(row[self.Coupon])
            JalDB().add_trade(account_id, asset_id, timestamp, settlement, number, qty, price, -fee)
            if bond_interest != 0:
                JalDB().add_dividend(DividendSubtype.BondInterest, timestamp, account_id, asset_id,
                                     bond_interest, "НКД", number)
        return True
