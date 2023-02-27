from decimal import Decimal
from jal.constants import BookAccount
from jal.db.db import JalDB
from jal.db.asset import JalAsset
from jal.db.operations import IncomeSpending


class JalCategory(JalDB):
    def __init__(self, id: int = 0):
        super().__init__()
        self._id = id
        self._data = self._read("SELECT pid, name FROM categories WHERE id=:category_id",
                                [(":category_id", self._id)], named=True)
        self._pid = self._data['pid'] if self._data is not None else 0
        self._name = self._data['name'] if self._data is not None else None

    def id(self) -> int:
        return self._id

    def parent_id(self) -> int:
        return self._pid

    def name(self) -> str:
        return self._name

    # Returns a list of JalCategory objects that represent child categories of the current category
    def get_child_categories(self) -> list:
        children = []
        query = self._exec("SELECT id FROM categories WHERE pid=:category_id", [(":category_id", self._id)])
        while query.next():
            children.append(JalCategory(self._read_record(query)))
        return children

    # Calculates overall turnover in ledger for the category between begin and end timestamps in given currency
    # (conversion rate is used for the day of operation)
    def get_turnover(self, begin: int, end: int, output_currency_id: int) -> Decimal:
        turnover = Decimal('0')
        query = self._exec("SELECT l.timestamp, l.amount, a.currency_id FROM ledger l "
                           "LEFT JOIN accounts AS a ON l.account_id=a.id "
                           "WHERE (l.book_account=:book_costs OR l.book_account=:book_incomes) "
                           "AND l.timestamp>=:begin AND l.timestamp<=:end AND l.category_id=:category_id",
                           [(":book_costs", BookAccount.Costs), (":book_incomes", BookAccount.Incomes),
                            (":begin", begin), (":end", end), (":category_id", self._id)])
        while query.next():
            timestamp, amount, currency_id = self._read_record(query, cast=[int, Decimal, int])
            if currency_id == output_currency_id:
                rate = Decimal('1')
            else:
                rate = JalAsset(currency_id).quote(timestamp, output_currency_id)[1]
            turnover += amount * rate
        return -turnover

    def add_or_update_mapped_name(self, name: str) -> None:
        _ = self._exec("INSERT OR REPLACE INTO map_category (value, mapped_to) "
                       "VALUES (:item_name, :category_id)",
                       [(":item_name", name), (":category_id", self._id)], commit=True)

    # Returns a list of all names that were mapped to some category in for of {"value", "mapped_to"}
    @classmethod
    def get_mapped_names(cls) -> list:
        mapped_list = []
        query = cls._exec("SELECT value, mapped_to FROM map_category")
        while query.next():
            mapped_list.append(cls._read_record(query, named=True))
        return mapped_list

    # Returns a list of operations that include this category
    def get_operations(self, begin: int, end: int) -> list:
        operations = []
        query = self._exec("SELECT DISTINCT a.id FROM actions a LEFT JOIN action_details d ON a.id=d.pid "
                           "WHERE d.category_id=:category AND a.timestamp>=:begin AND a.timestamp<:end",
                           [(":category", self._id), (":begin", begin), (":end", end)])
        while query.next():
            operations.append(IncomeSpending(self._read_record(query, cast=[int])))
        return operations

    def replace_with(self, new_id):
        self._exec("UPDATE action_details SET category_id=:new_id WHERE category_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("UPDATE map_category SET mapped_to=:new_id WHERE mapped_to=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("DELETE FROM categories WHERE id=:old_id", [(":old_id", self._id)], commit=True)
        self._id = 0
