from decimal import Decimal
from jal.db.db import JalDB
import jal.db.operations
import jal.db.basis_policy
import jal.db.lots


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
