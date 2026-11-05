from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from enum import Enum, auto
import jal.db.operations
from jal.constants import SwapTreatment


# ----------------------------------------------------------------------------------------------------------------------
# What a lot's cost does when an operation exchanges it: realized at a value or carried over
class Basis(Enum):
    DISPOSAL = auto()
    CARRY = auto()


# When the holding period of the lot that results starts: the original acquisition or the operation itself
class Clock(Enum):
    KEEP = auto()
    RESTART = auto()


# The answer for one exchange; 'share' is the part of the cost a corporate action result takes, 'value' the total a
# DISPOSAL is realized at in the account currency (None: the operation's own market value; required for a result)
@dataclass(frozen=True)
class Treatment:
    basis: Basis
    clock: Clock
    share: Decimal = Decimal('1')
    value: Optional[Decimal] = None


# ----------------------------------------------------------------------------------------------------------------------
# The questions LotEngine and the operations' lot halves ask instead of deciding: the rules a jurisdiction may set
class BasisPolicy:
    # How a Swap or a Conversion treats the lots it exchanges
    def treatment(self, operation) -> Treatment:
        raise NotImplementedError

    # How a CorporateAction treats the lots of one of its results (a dict of asset_action_results columns)
    def action_result(self, action, result: dict) -> Treatment:
        raise NotImplementedError

    # The cost per unit an AssetIncome opens its lot at
    def income_cost(self, income) -> Decimal:
        raise NotImplementedError

    # The open lots of a position in the order a disposal takes them
    def order(self, lots: list) -> list:
        raise NotImplementedError


# ----------------------------------------------------------------------------------------------------------------------
# JAL's own rules: a sale swap is a disposal, other exchanges carry the lot and its date, FIFO by acquisition date
class JalPolicy(BasisPolicy):
    def treatment(self, operation) -> Treatment:
        if isinstance(operation, jal.db.operations.Swap) and operation.treatment() == SwapTreatment.Sale:
            return Treatment(Basis.DISPOSAL, Clock.RESTART)
        return Treatment(Basis.CARRY, Clock.KEEP)

    def action_result(self, action, result: dict) -> Treatment:
        return Treatment(Basis.CARRY, Clock.KEEP if result['keep_date'] else Clock.RESTART,
                         Decimal(result['value_share']))

    def income_cost(self, income) -> Decimal:
        return income.price()

    # By acquisition date, then by the original operation; slice_id breaks the remaining ties, as slices get ids in
    # replay (chronological) order
    def order(self, lots: list) -> list:
        return sorted(lots, key=lambda x: (x.acquired(), x.open_operation().timestamp(), x.slice_id()))
