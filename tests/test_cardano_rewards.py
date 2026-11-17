from decimal import Decimal

import pytest
from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import QTreeView

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import create_quotes
from tests.test_cardano_classifier import OWN_STAKE, ada_wallet, fetch, transaction, utxo
from jal.constants import AccountData, AssetLocation, PredefinedAsset
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.holdings_model import AccountHoldingsModel
from jal.db.ledger import Ledger
from jal.db.receivable import JalReceivable
from jal.net import chain_balances
from jal.net.chain_balances import ChainBalanceReader

# Rewards withdrawn are StakingReward operations of the fetcher; what is read here is what the reward account still
# holds, stored as a receivable. Koios is replaced by its recorded answer shape.

USD = 2
EUR = 1
BEFORE = 1800000000
NOW = 1800086400
SOURCE = chain_balances._ADA_REWARD_SOURCE


# The wallet holds 250 ADA, imported from the chain the way a fetch does it; ADA is quoted at 0.5 USD
@pytest.fixture
def funded(ada_wallet):
    ada_wallet.set_data(AccountData.Precision, 6)
    fetcher, _ = fetch(ada_wallet, transaction(1, [utxo(900_000_000, 'byron')],
                                               [utxo(250_000_000), utxo(649_828_000, 'byron')], fee=172_000))
    fetcher.import_fetched()
    Ledger().rebuild(from_timestamp=0)
    ada = JalAsset.find({'symbol': 'ADA', 'type': PredefinedAsset.Crypto})
    create_quotes(ada.id(), USD, [(BEFORE - 86400, Decimal('0.5'))])
    create_quotes(USD, EUR, [(BEFORE - 86400, Decimal('1'))])
    yield ada_wallet, ada.id()


def _koios(monkeypatch, answer) -> list:
    asked = []

    def post(self, url, request):
        asked.append((url, request))
        return answer
    monkeypatch.setattr(ChainBalanceReader, "_post", post)
    return asked


def _info(lovelace) -> list:
    return [{"stake_address": OWN_STAKE, "status": "registered", "rewards_available": str(lovelace),
             "total_balance": "252000000", "utxo": "250000000", "deposit": "2000000"}]


def test_the_reward_account_is_a_claim_in_the_wallets_ada(funded, monkeypatch):
    wallet, ada = funded
    asked = _koios(monkeypatch, _info(3_456_789))
    assert ChainBalanceReader().read_receivables(NOW) == 1
    assert asked == [(chain_balances._KOIOS_ACCOUNT_INFO, {"_stake_addresses": [OWN_STAKE]})]
    [claim] = JalReceivable().claims(wallet.id(), NOW)
    assert (claim['asset_id'], claim['source'], claim['amount']) == (ada, SOURCE, Decimal('3.456789'))


def test_a_withdrawn_reward_is_written_down_as_zero(funded, monkeypatch):
    wallet, ada = funded
    _koios(monkeypatch, _info(3_000_000))
    ChainBalanceReader().read_receivables(BEFORE)
    _koios(monkeypatch, _info(0))
    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalReceivable().latest(wallet.id(), ada, SOURCE, NOW)['amount'] == Decimal('0')
    assert JalReceivable().claims(wallet.id(), NOW) == []


@pytest.mark.parametrize("answer", [None, [], [{"stake_address": OWN_STAKE}], [{"stake_address": "stake1other"}]])
def test_a_failed_reading_leaves_the_last_one_alone(funded, monkeypatch, answer):
    wallet, ada = funded
    _koios(monkeypatch, _info(3_000_000))
    ChainBalanceReader().read_receivables(BEFORE)
    _koios(monkeypatch, answer)
    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalReceivable().latest(wallet.id(), ada, SOURCE, NOW)['timestamp'] == BEFORE


def test_other_chains_do_not_ask_koios(funded, monkeypatch):
    asked = _koios(monkeypatch, _info(3_000_000))
    assert ChainBalanceReader().read_receivables(NOW, locations=[AssetLocation.ETH_BLOCKCHAIN]) == 0
    assert asked == []


# The A5 gate: the first wallet total equals balance(), and a report dated before the reading doesn't see it
def test_the_wallet_total_counts_the_claim_as_balance_does(funded, monkeypatch):
    wallet, _ = funded
    _koios(monkeypatch, _info(4_000_000))
    ChainBalanceReader().read_receivables(NOW)
    JalAccount(wallet.id()).invalidate_cache()
    model = AccountHoldingsModel(QTreeView())
    model.showAccount(wallet.id(), EUR, QDateTime.fromSecsSinceEpoch(NOW, QTimeZone.UTC).date())
    totals = [model._root.getChild(i).details() for i in range(model._root.childrenCount())]
    [total] = [x for x in totals if x.get('kind') == 'total']
    assert total['value'] == Decimal('127')                          # (250 + 4) ADA at 0.5
    assert JalAccount(wallet.id()).balance(NOW + 86399) == Decimal('127')
    assert JalAccount(wallet.id()).balance(BEFORE) == Decimal('125')  # before the reading: the ledger alone
