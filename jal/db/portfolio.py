from decimal import Decimal
from jal.db.db import JalDB
import jal.db.operations
import jal.db.basis_policy
import jal.db.lots
import jal.db.account
import jal.db.asset
import jal.db.closed_trade


# ----------------------------------------------------------------------------------------------------------------------
# Access to 'operation_portfolios': the portfolio (a tag) of the lots an operation opens. Report input only, the
# ledger never reads it. An instance is a snapshot that answers for lots and operations without a query each.
class JalPortfolio(JalDB):
    Unassigned = 0

    def __init__(self):
        super().__init__()
        self._assigned = self.assignments()

    # Every assignment, as {operation_id: tag_id}
    @classmethod
    def assignments(cls) -> dict:
        query = cls._exec("SELECT operation_id, tag_id FROM operation_portfolios")
        assigned = {}
        while query.next():
            operation_id, tag_id = cls._read_record(query, cast=[int, int])
            assigned[operation_id] = tag_id
        return assigned

    # Assigns the operation to the portfolio 'tag_id'; Unassigned drops the assignment
    @classmethod
    def assign(cls, operation_id: int, tag_id: int) -> None:
        if tag_id == cls.Unassigned:
            cls._exec("DELETE FROM operation_portfolios WHERE operation_id=:oid", [(":oid", operation_id)], commit=True)
        else:
            cls._exec("INSERT INTO operation_portfolios (operation_id, tag_id) VALUES (:oid, :tag) "
                      "ON CONFLICT (operation_id) DO UPDATE SET tag_id=excluded.tag_id",
                      [(":oid", operation_id), (":tag", tag_id)], commit=True)

    # The portfolio the operation acts in
    def of_operation(self, operation) -> int:
        return self._assigned.get(operation.id(), self.Unassigned)

    # True for a short lot: one opened by a sale
    @staticmethod
    def is_short(lot) -> bool:
        operation = lot.open_operation()
        return operation.type() == jal.db.operations.LedgerTransaction.Trade and operation.qty() < Decimal('0')

    # The portfolio of a lot: that of the operation that opened it; a short lot belongs to none
    def of_lot(self, lot) -> int:
        return self.Unassigned if self.is_short(lot) else self.of_operation(lot.open_operation())


# ----------------------------------------------------------------------------------------------------------------------
# A policy that takes the lots of the disposing operation's own portfolio first, then the rest, each part in the
# wrapped policy's order; the other questions go to the wrapped policy unchanged. For a portfolio replay only.
class PortfolioPolicy(jal.db.basis_policy.BasisPolicy):
    def __init__(self, policy, portfolio: JalPortfolio):
        self._policy = policy
        self._portfolio = portfolio

    def treatment(self, operation):
        return self._policy.treatment(operation)

    def action_result(self, action, result: dict):
        return self._policy.action_result(action, result)

    def income_cost(self, income) -> Decimal:
        return self._policy.income_cost(income)

    def order(self, lots: list, operation=None) -> list:
        ordered = self._policy.order(lots, operation)
        tag_id = JalPortfolio.Unassigned if operation is None else self._portfolio.of_operation(operation)
        if tag_id == JalPortfolio.Unassigned:
            return ordered
        own = [x for x in ordered if self._portfolio.of_lot(x) == tag_id]
        return own + [x for x in ordered if self._portfolio.of_lot(x) != tag_id]


# ----------------------------------------------------------------------------------------------------------------------
# The open lots of a position with the portfolio of each, for the reports. When every assigned operation only opens
# lots the live lots are the answer; otherwise a portfolio replay, kept for the session until the ledger is rebuilt
# or an assignment changes.
class PortfolioLots:
    _store = None
    _assigned = None   # the assignments the replay in '_store' was made with

    # True if the assignments need a replay that hasn't run yet
    @classmethod
    def needs_replay(cls) -> bool:
        assigned = JalPortfolio.assignments()
        return cls._disposes(assigned) and (cls._store is None or cls._assigned != assigned)

    # Runs the replay if needed; 'progress(done, total)' is called after each operation
    @classmethod
    def prepare(cls, progress=None) -> None:
        if not cls.needs_replay():
            return
        cls.forget()
        assigned = JalPortfolio.assignments()
        store = jal.db.lots.ScratchLotStore('portfolio_lots')
        try:
            jal.db.lots.replay(store, PortfolioPolicy(jal.db.basis_policy.JalPolicy(), JalPortfolio()),
                               progress=progress)
        except Exception:
            store.detach()
            raise
        cls._store, cls._assigned = store, assigned

    # [(portfolio, lot)] of the position at 'timestamp'
    @classmethod
    def lots(cls, account, asset, timestamp: int) -> list:
        cls.prepare()
        portfolio = JalPortfolio()
        return [(portfolio.of_lot(x), x) for x in account.open_trades_list(asset, timestamp, store=cls._store)]

    # [(portfolio, deal)] of the account, from the replay when one is needed
    @classmethod
    def deals(cls, account, close_otypes=None) -> list:
        cls.prepare()
        portfolio = JalPortfolio()
        return [(portfolio.of_lot(x), x) for x in account.closed_trades_list(close_otypes=close_otypes, store=cls._store)]

    # {portfolio: (amount, tax)} of an asset payment or income, shared out by what each portfolio held before the
    # ex-date (or at payment time without one); an income opens a lot, so it goes whole to its own portfolio
    @classmethod
    def payment_parts(cls, payment) -> dict:
        if isinstance(payment, jal.db.operations.AssetIncome):
            return {JalPortfolio().of_operation(payment): (payment.amount(), payment.tax())}
        timestamp = payment.ex_date() - 1 if payment.ex_date() else payment.timestamp()
        held = {}
        for tag_id, lot in cls.lots(payment.account(), payment.asset(), timestamp):
            held[tag_id] = held.get(tag_id, Decimal('0')) + lot.open_qty()
        amounts = cls.share_out(payment.amount(), held)
        taxes = cls.share_out(payment.tax(), held)
        return {x: (amounts[x], taxes[x]) for x in amounts}

    # {portfolio: part} of 'value' in proportion to 'held' {portfolio: qty}; the last part takes the remainder, and
    # with nothing held the whole value is Unassigned
    @staticmethod
    def share_out(value: Decimal, held: dict) -> dict:
        total = sum(held.values(), Decimal('0'))
        if not total:
            return {JalPortfolio.Unassigned: value}
        parts, left = {}, value
        for i, tag_id in enumerate(sorted(held)):
            parts[tag_id] = left if i == len(held) - 1 else value * held[tag_id] / total
            left -= parts[tag_id]
        return parts

    # Drops the replay: the ledger it was made of is being rebuilt
    @classmethod
    def forget(cls) -> None:
        if cls._store is not None:
            cls._store.detach()
        cls._store = cls._assigned = None

    # True if an assigned operation disposes of lots, so that its portfolio may change which lots it takes
    @staticmethod
    def _disposes(assigned: dict) -> bool:
        for operation_id in assigned:
            otype = JalDB._read("SELECT otype FROM operations WHERE id=:id", [(":id", operation_id)])
            if otype == jal.db.operations.LedgerTransaction.AssetIncome:
                continue
            if otype == jal.db.operations.LedgerTransaction.Trade and \
                    jal.db.operations.Trade(operation_id).qty() > Decimal('0'):
                continue
            return True
        return False


# ----------------------------------------------------------------------------------------------------------------------
# Assignments to review: a portfolio's disposal that took lots of other portfolios (its own ran out), and unassigned
# lots of a position that holds assigned ones too
class PortfolioReview:
    Spill = 1
    Unassigned = 2

    # [{'issue', 'operation', 'account', 'asset', 'qty', 'portfolio', 'others'}], oldest operation first: 'portfolio'
    # is the operation's own, 'others' the portfolios of the lots it took (Spill) or held beside it (Unassigned)
    @classmethod
    def items(cls) -> list:
        PortfolioLots.prepare()
        portfolio = JalPortfolio()
        items = cls._spills(portfolio) + cls._unassigned(portfolio)
        return sorted(items, key=lambda x: (x['operation'].timestamp(), x['operation'].id(), x['issue']))

    @staticmethod
    def _spills(portfolio) -> list:
        if PortfolioLots._store is None:   # no assigned disposals, nothing can spill
            return []
        store = PortfolioLots._store
        items = {}
        for deal_id in store.deals_closed_by_any(list(portfolio._assigned)):
            deal = jal.db.closed_trade.JalClosedTrade(deal_id, store=store)
            own, taken = portfolio.of_operation(deal.close_operation()), portfolio.of_lot(deal)
            if taken == own or portfolio.is_short(deal):   # covering a short takes nobody's lots
                continue
            key = (deal.close_operation().id(), deal.account().id(), deal.asset().id())
            item = items.setdefault(key, {'issue': PortfolioReview.Spill, 'operation': deal.close_operation(),
                                          'account': deal.account(), 'asset': deal.asset(), 'qty': Decimal('0'),
                                          'portfolio': own, 'others': set()})
            item['qty'] += deal.qty()
            item['others'].add(taken)
        return list(items.values())

    @staticmethod
    def _unassigned(portfolio) -> list:
        store = jal.db.lots.LedgerLotStore() if PortfolioLots._store is None else PortfolioLots._store
        positions = {(account_id, asset_id) for account_id, asset_id, qty in store.slices() if qty}
        items = []
        for account_id, asset_id in sorted(positions):
            account, asset = jal.db.account.JalAccount(account_id), jal.db.asset.JalAsset(asset_id)
            lots = [x for x in account.open_trades_list(asset, store=PortfolioLots._store) if not portfolio.is_short(x)]
            assigned = {portfolio.of_lot(x) for x in lots} - {JalPortfolio.Unassigned}
            if not assigned:
                continue
            openers = {}
            for lot in lots:
                if portfolio.of_lot(lot) == JalPortfolio.Unassigned:
                    item = openers.setdefault(lot.open_operation().id(), {
                        'issue': PortfolioReview.Unassigned, 'operation': lot.open_operation(), 'account': account,
                        'asset': asset, 'qty': Decimal('0'), 'portfolio': JalPortfolio.Unassigned, 'others': assigned})
                    item['qty'] += lot.open_qty()
            items += list(openers.values())
        return items
