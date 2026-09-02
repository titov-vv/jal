from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_assets, create_trades, symbol_id_for
from constants import PredefinedAsset, PredefinedAccountType, AccountStatus, AssetLocation
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.common_models import AccountListModel
from jal.db.ledger import Ledger
from jal.db.operations import LedgerTransaction, Transfer
from jal.db.staking import JalStakingBox
from jal.db.transfer_settlement import TransferSettlement

LINK = 4                       # the asset created by the fixture below
WALLET = 1
USD = 2
POOL = '0xddc796a66e8b83d0bccd97df33a6ccfba8fd60ea'      # stake.link's PriorityPool, a registered custody contract
HASH_IN = '0x' + 'a' * 64
HASH_OUT = '0x' + 'b' * 64


# An Ethereum wallet that bought some LINK, so there is a real position with a cost basis to stake
@pytest.fixture
def wallet(prepare_db):
    JalAccountCreator(currency_id=USD, number='', name='ETH wallet', investing=1, organization=1, precision=18,
                      account_type=PredefinedAccountType.Wallet, address='0x' + '2' * 40,
                      chain=AssetLocation.ETH_BLOCKCHAIN).commit()
    create_assets([('LINK', 'ChainLink Token', '', USD, PredefinedAsset.Crypto, 0)])
    create_trades(WALLET, [(d2t(210101), d2t(210101), LINK, Decimal('100'), Decimal('10'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    yield


def _pending_leg(from_account, to_account, amount, timestamp, number, address=None, note='') -> int:
    return LedgerTransaction.create_new(LedgerTransaction.Transfer, {
        'withdrawal_timestamp': timestamp, 'withdrawal_account': from_account, 'withdrawal': str(amount),
        'deposit_timestamp': timestamp, 'deposit_account': to_account, 'deposit': '0',
        'number': number, 'note': note, 'counterparty_address': address, 'symbol_id': symbol_id_for(LINK)}).oid()


# What the LINK held by an account cost it at the given moment, i.e. the cost basis its open lots carry
def _basis(account_id, timestamp) -> Decimal:
    return sum([x['value'] for x in JalAccount(account_id).assets_list(timestamp)], Decimal('0'))


# ----------------------------------------------------------------------------------------------------------------------
# A staking box is an account of a hidden type: it exists, holds an asset and never shows up where accounts are picked
def test_staking_box_is_a_hidden_account(wallet):
    box = JalStakingBox.create(JalAccount(WALLET), "stake.link PriorityPool", protocol='stake.link PriorityPool',
                               chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)

    assert JalAccount(box.id()).account_type() == PredefinedAccountType.Staking
    assert box.protocol() == 'stake.link PriorityPool'
    assert box.chain() == AssetLocation.ETH_BLOCKCHAIN and box.address() == POOL

    assert box.id() not in [x.id() for x in JalAccount.get_all_accounts()]
    assert box.id() in [x.id() for x in JalAccount.get_all_accounts(include_hidden=True)]

    model = AccountListModel()
    assert box.id() not in [model.getId(model.index(row, 0)) for row in range(model.rowCount())]


# The precision of a box is the precision of the account it takes the asset from, and it is not a display detail:
# the ledger rounds every amount to the precision of the account it books it on, so a box left at the default of two
# decimals would book 60.123456789 staked coins as 60.12 and then refuse to give back what was really put in.
def test_a_box_is_as_precise_as_the_account_it_serves(wallet):
    box = JalStakingBox.create(JalAccount(WALLET), "stake.link", chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)
    assert JalAccount(box.id()).precision() == JalAccount(WALLET).precision() == 18

    _pending_leg(WALLET, None, Decimal('60.123456789012345678'), d2t(210201), HASH_OUT, address=POOL)
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)
    assert box.holdings(d2t(210301))[0]['amount'] == Decimal('60.123456789012345678')

    # ... and what came out of the wallet is exactly what went into the box, which is what lets it be taken back out
    _pending_leg(None, WALLET, Decimal('60.123456789012345678'), d2t(210301), HASH_IN, address=POOL)
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)          # raises if the box is short of a single unit of the last decimal
    assert JalAccount(WALLET).get_asset_amount(d2t(210401), LINK) == Decimal('100')


# The address is what a box is FOR: a pending leg naming it resolves to the box, which is what settles a stake
# without anybody being asked. A plain wallet resolves the same way - the two are the account types an address has.
def test_a_box_is_found_by_the_address_it_holds(wallet):
    assert JalAccount.at_address(AssetLocation.ETH_BLOCKCHAIN, POOL) is None
    box = JalStakingBox.create(JalAccount(WALLET), "stake.link", chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)

    found = JalAccount.at_address(AssetLocation.ETH_BLOCKCHAIN, POOL)
    assert found is not None and found.id() == box.id()
    # ... and only on its own chain: the same address on another one is a different account entirely
    assert JalAccount.at_address(AssetLocation.ARB_BLOCKCHAIN, POOL) is None


# The whole round trip, settled by the address alone: coins are staked into the container and come back out of it,
# and neither leg is ever assigned by hand. What matters is that nothing is disposed of - a stake is a transfer, so
# the position keeps its cost basis and no profit is realized by staking it.
def test_stake_and_unstake_settle_by_address(wallet):
    box = JalStakingBox.create(JalAccount(WALLET), "stake.link", protocol='stake.link PriorityPool',
                               chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)
    _pending_leg(WALLET, None, 60, d2t(210201), HASH_OUT, address=POOL)      # staked, far end unknown
    _pending_leg(None, WALLET, 60, d2t(210301), HASH_IN, address=POOL)       # ... and returned

    assert TransferSettlement().settle_all() == 2
    assert Transfer.pending_legs() == []

    Ledger().rebuild(from_timestamp=0)
    # Between the two dates the coins are in the box and out of the wallet, and afterwards they are back
    assert JalAccount(WALLET).get_asset_amount(d2t(210215), LINK) == Decimal('40')
    assert JalAccount(box.id()).get_asset_amount(d2t(210215), LINK) == Decimal('60')
    assert JalAccount(WALLET).get_asset_amount(d2t(210401), LINK) == Decimal('100')
    assert box.holdings(d2t(210401)) == []
    # Staking disposes of nothing: what the coins COST travels with them into the box and back, so the 100 LINK
    # bought at 10 are still 100 LINK that cost 1000 after a round trip through the container.
    assert _basis(WALLET, d2t(210215)) == Decimal('400') and _basis(box.id(), d2t(210215)) == Decimal('600')
    assert _basis(WALLET, d2t(210401)) == Decimal('1000')


# What the box reports about itself while it holds something, and how it stops being listed once it doesn't
def test_box_reports_what_it_holds_and_closes_when_empty(wallet):
    box = JalStakingBox.create(JalAccount(WALLET), "stake.link", chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)
    _pending_leg(WALLET, None, 60, d2t(210201), HASH_OUT, address=POOL)
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)

    assert box.opened_at() == d2t(210201)
    holdings = box.holdings(d2t(210301))
    assert len(holdings) == 1 and holdings[0]['amount'] == Decimal('60')
    assert [x.id() for x in JalStakingBox.get_boxes(d2t(210301))] == [box.id()]
    # Nothing was staked yet the day before it was, so the box is not listed as a position then
    assert JalStakingBox.get_boxes(d2t(210101)) == []

    details = box.details(d2t(210301))
    assert len(details) == 1 and details[0]['balance'] == Decimal('60')

    # An emptied box is closed by hand and drops out of every default view, while all it recorded stays
    _pending_leg(None, WALLET, 60, d2t(210301), HASH_IN, address=POOL)
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)
    assert JalStakingBox.get_boxes(d2t(210401)) == []
    box.close()
    assert not JalStakingBox(box.id()).is_active()
    assert [x.id() for x in JalStakingBox.all_boxes()] == [box.id()]   # ... and it is still there to be found


# A staked asset has left the wallet but not the portfolio: the box is a hidden account, and leaving hidden accounts
# out of the holdings would understate the portfolio by exactly what is staked.
def test_staked_asset_stays_in_the_portfolio(wallet):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QTreeView
    from jal.db.holdings_model import HoldingsModel

    box = JalStakingBox.create(JalAccount(WALLET), "stake.link", chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)
    _pending_leg(WALLET, None, 60, d2t(210201), HASH_OUT, address=POOL)
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)

    model = HoldingsModel(QTreeView())
    model.updateView(currency_id=USD, date=QDate(2021, 3, 1), grouping='', min_status=AccountStatus.Active)
    rows = [model._root.getChild(row).details() for row in range(model._root.childrenCount())]
    held = {(x['account_id'], x['asset_id']): x['qty'] for x in rows}
    # The staked 60 LINK are listed under the box, and the 40 left behind under the wallet: 100 in the portfolio,
    # which is what the wallet owns whichever container is holding them at the moment
    assert held[(box.id(), LINK)] == Decimal('60')
    assert held[(WALLET, LINK)] == Decimal('40')


# A staking box may not be picked as an ordinary account end, but it is exactly what the staking mode of the
# assignment dialog offers - and assigning to it is an ordinary assignment with an ordinary refusal.
def test_assignment_to_a_box_refuses_what_it_never_held(wallet):
    box = JalStakingBox.create(JalAccount(WALLET), "stake.link", chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)
    # An arrival whose source is unknown: the box is named as the sender, but nothing was ever staked into it
    oid = _pending_leg(None, WALLET, 60, d2t(210301), HASH_IN)
    Ledger().rebuild(from_timestamp=0)   # the refusal reads open lots, which stand down while any are uncalculated

    refusal = TransferSettlement().refusal_for_assignment(oid, box.id(), d2t(210301))
    assert 'hold' in refusal   # "the account didn't hold enough of the asset at that moment..."

    # ... and once the stake that filled it is settled, the same assignment is accepted
    _pending_leg(WALLET, None, 60, d2t(210201), HASH_OUT, address=POOL)
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)
    assert TransferSettlement().assign_end(oid, box.id(), d2t(210301), Decimal('0')) == ''
    Ledger().rebuild(from_timestamp=0)
    assert JalAccount(WALLET).get_asset_amount(d2t(210401), LINK) == Decimal('100')


# ----------------------------------------------------------------------------------------------------------------------
# The Staked positions window is discovered by the report loader, so it appears in the Reports menu - and it builds,
# finds the position and fills its details from a selection.
def test_staking_report_window_builds_and_selects(wallet):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from jal.reports.reports import Reports
    from jal.reports.staking import StakingReportWindow

    box = JalStakingBox.create(JalAccount(WALLET), "stake.link", protocol='stake.link PriorityPool',
                               chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)
    _pending_leg(WALLET, None, 60, d2t(210201), HASH_OUT, address=POOL)
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)

    reports = Reports(None, None)
    assert "StakingReportWindow" in [x['window_class'] for x in reports.items]

    window = StakingReportWindow(reports)
    window.updateReport()
    assert window.boxes_model.rowCount() == 1
    assert window.boxes_model.data_text(window.boxes_model._data[0], 1) == 'stake.link PriorityPool'
    assert window.boxes_model.data_text(window.boxes_model._data[0], 4) == Decimal('60')

    window.ui.ReportTableView.selectRow(0)
    assert window._selected().id() == box.id()
    assert window.details_model.rowCount() == 1


# The name a box carries is a guess: the dialog that creates one suggests the protocol the import recognized, and
# this report is the only place that guess is ever seen - so it is the place it is corrected. What opens is the
# account editor cut down to a name and an icon (AccountDialog.edit_name_only, tested in test_account_dialog.py):
# a box IS an account, and everything else about that account must not change.
def test_the_report_offers_to_rename_a_position(wallet):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QMenu
    from jal.reports.reports import Reports
    from jal.reports.staking import StakingReportWindow

    JalStakingBox.create(JalAccount(WALLET), "stake.link", protocol='stake.link PriorityPool',
                         chain=AssetLocation.ETH_BLOCKCHAIN, address=POOL)
    _pending_leg(WALLET, None, 60, d2t(210201), HASH_OUT, address=POOL)
    TransferSettlement().settle_all()
    Ledger().rebuild(from_timestamp=0)

    window = StakingReportWindow(Reports(None, None))
    window.show()
    window.updateReport()
    view = window.ui.ReportTableView
    window.onPositionContextMenu(view.visualRect(window.boxes_model.index(0, 0)).center())

    menu = view.findChild(QMenu)
    assert [x.text() for x in menu.actions()] == ['Show accrual chart', 'Rename position...']
    menu.close()
    window.deleteLater()
