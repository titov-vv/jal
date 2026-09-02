from decimal import Decimal

import pytest
import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, create_quotes, create_trades
from constants import PredefinedAsset, PredefinedAccountType, AssetLocation, SymbolId
from jal.db.account import JalAccount, JalAccountCreator
from jal.db.asset import JalAsset, JalAssetCreator
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.receivable import JalReceivable
from jal.db.settings import JalSettings
from jal.db.symbol import JalSymbol
from jal.net import aave, merkl
from jal.net.chain_balances import ChainBalanceReader

# ----------------------------------------------------------------------------------------------------------------------
# What a distributor OWES a wallet: value denominated in an asset the ledger holds none of, which is why it needs a
# table of its own and why none of it may reach the tax or profit/loss paths.
#
# Nothing here touches the network. The Merkl API answer, Aave's two views and every eth_call around them are
# replaced, and the proof walk is stubbed out with them - jal/net/merkl.py is where the real proof is verified,
# against a real published root, in tests/test_merkl.py, and jal/net/aave.py is decoded in tests/test_aave.py.

USD = 2
WALLET_ADDRESS = '0x' + 'd' * 40
GHO_CONTRACT = '0x40d16fc0246ad3160ccc09b8d0d3a2cd28ae6c2f'
ARB_CONTRACT = '0x912ce59144191c1204e64559fe8253a0e49e6548'
OTHER_DISTRIBUTOR = '0x7060fe0dd3e31be01efac6b28c8d38018fd163b0'   # a FluidMerkleDistributor, paying the same token
AAVE_CONTRACT = '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9'          # what both Aave Safety modules pay
NOW = d2t(260805)
LATER = d2t(260806)
ROOT = '0x' + 'ab' * 32
ERC20_NAME = '0x06fdde03'
ERC20_SYMBOL = '0x95d89b41'
ERC20_DECIMALS = '0x313ce567'

# What a Safety module answers when a test says nothing about it: it pays AAVE and owes nothing. Every reading asks
# every source, so without this a Merkl test would be reading a module that refuses to answer at all.
NO_REWARD = {aave.STAKED_AAVE: (AAVE_CONTRACT, 0), aave.STAKED_GHO: (AAVE_CONTRACT, 0)}

WALLET = 0
GHO = 0
AAVE = 0


# One Ethereum wallet that already holds a token JAL knows, so the "known asset" and "new asset" paths can be told apart
@pytest.fixture
def eth_wallet(prepare_db):
    global WALLET, GHO
    JalSettings().setValue("ApiKey_Etherscan", "test-key")
    WALLET = JalAccountCreator(currency_id=USD, number='', name='ETH wallet', investing=1, organization=1,
                              precision=18, account_type=PredefinedAccountType.Wallet,
                              address=WALLET_ADDRESS, chain=AssetLocation.ETH_BLOCKCHAIN).commit().id()
    creator = JalAssetCreator(PredefinedAsset.Crypto, "Gho Token")
    symbol_id = creator.add_symbol('GHO', USD, AssetLocation.ETH_BLOCKCHAIN)
    creator.add_identifier(symbol_id, SymbolId.ETH_ADDRESS, GHO_CONTRACT)
    GHO = creator.commit().id()
    create_quotes(GHO, USD, [(NOW, Decimal('1'))])
    yield


def _reward(address, symbol='GHO', decimals=18, amount='1000000000000000000', pending='0'):
    return {'root': ROOT, 'amount': amount, 'claimed': '0', 'pending': pending, 'proofs': ['0x' + '11' * 32],
            'token': {'address': address, 'symbol': symbol, 'decimals': decimals}}


# Replaces everything that leaves the machine, for BOTH sources at once: they share one _eth_call and one reading
# asks them both, so a stub for either has to answer for the other as well.
#
# Merkl's side is the API answer, getMerkleRoot() and claimed() - 'claimed' is keyed by token address so a partly
# claimed stream can be set up, and the proof walk is stubbed to accept, because what it does with a REAL proof is
# tested in tests/test_merkl.py and cannot be reproduced with invented vectors here. Aave's side is 'modules',
# {contract: (reward token, what it owes in raw units)}, defaulting to both modules owing nothing.
def _fake_chain(monkeypatch, rewards=None, claimed=None, root=ROOT, answer=None, chain_id=1, name=None,
                modules=None, ticker='', decimals=18):
    rewards, claimed = rewards or [], claimed or {}
    modules = NO_REWARD if modules is None else modules
    asked = {'api': [], 'calls': []}

    def fake_get(self, url, params):
        if 'merkl' in url:
            asked['api'].append((url, params))
            if answer is not None:
                return answer
            return [{'chain': {'id': chain_id}, 'rewards': rewards}]
        return None

    def _string(text):
        body = text.encode()
        return '0x' + format(32, '064x') + format(len(body), '064x') + body.hex().ljust(64, '0')

    def fake_eth_call(self, chain, contract, data, api_key):
        asked['calls'].append((contract, data))
        if data == merkl.SELECTOR_MERKLE_ROOT:
            return root
        if data == aave.SELECTOR_REWARD_TOKEN:
            token = modules.get(contract, ('', 0))[0]
            return '0x' + '00' * 12 + token.removeprefix('0x') if token else ''
        if data.startswith(aave.SELECTOR_TOTAL_REWARDS):
            return '0x' + format(modules.get(contract, ('', 0))[1], '064x')
        if data == ERC20_DECIMALS:        # asked when a token JAL knows carries no scale of its own yet
            return '0x' + format(decimals, '064x')
        if data == ERC20_SYMBOL:          # asked only where the source itself reports no ticker
            return _string(ticker) if ticker else ''
        if data == ERC20_NAME:            # asked only when an asset has to be created for an unknown token
            return _string(name) if name is not None else ''
        token = '0x' + data[-40:]
        paid = claimed.get(token.lower(), 0)
        return '0x' + format(paid, '064x') + format(0, '064x') + '00' * 32

    monkeypatch.setattr(ChainBalanceReader, "_get", fake_get)
    monkeypatch.setattr(ChainBalanceReader, "_eth_call", fake_eth_call)
    monkeypatch.setattr(merkl, "verified_amount", lambda account, token, amount, proofs, expected: amount)
    return asked


# ----------------------------------------------------------------------------------------------------------------------
# READING

def test_what_is_owed_is_the_tree_amount_less_what_the_chain_says_was_claimed(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='5000000000000000000')],
                claimed={GHO_CONTRACT: 2000000000000000000})

    assert ChainBalanceReader().read_receivables(NOW) == 1
    owed = JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)
    assert owed['amount'] == Decimal('3')


# A claim that lands between the API's snapshot and the eth_call leaves 'claimed' ahead of the tree, and a negative
# receivable would be shown as a debt the account owes rather than as nothing being owed to it.
def test_a_stream_claimed_past_the_tree_is_nothing_owed_and_never_a_debt(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='1000000000000000000')],
                claimed={GHO_CONTRACT: 3000000000000000000})

    ChainBalanceReader().read_receivables(NOW)
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)['amount'] == Decimal('0')
    assert JalReceivable().claims(WALLET, NOW) == []


def test_a_fully_claimed_stream_is_recorded_as_zero_and_not_listed(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='4000000000000000000')],
                claimed={GHO_CONTRACT: 4000000000000000000})

    ChainBalanceReader().read_receivables(NOW)
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)['amount'] == Decimal('0')
    assert JalReceivable().claims(WALLET, NOW) == []


# 'pending' is accruing inside an epoch that has published no root, so no proof backs it. It is recorded because a
# column costs nothing, and never valued because it cannot be claimed today.
def test_pending_is_recorded_beside_the_claimable_amount_and_not_valued(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='1000000000000000000',
                                      pending='500000000000000000')])

    ChainBalanceReader().read_receivables(NOW)
    owed = JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)
    assert owed['amount'] == Decimal('1')
    assert owed['pending'] == Decimal('0.5')
    assert JalReceivable().value(WALLET, NOW, USD) == Decimal('1')     # the pending half is NOT in the value


# The trap the 'source' column exists for: two distributors paying one token to one wallet must be two rows, not one
# overwriting the other.
def test_two_distributors_paying_the_same_token_do_not_collide(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='1000000000000000000')])
    ChainBalanceReader().read_receivables(NOW)
    JalReceivable().store(NOW, WALLET, GHO, OTHER_DISTRIBUTOR, Decimal('7'))

    claims = sorted(JalReceivable().claims(WALLET, NOW), key=lambda x: x['amount'])
    assert [x['amount'] for x in claims] == [Decimal('1'), Decimal('7')]
    assert {x['source'] for x in claims} == {merkl.DISTRIBUTOR, OTHER_DISTRIBUTOR}


# An amount whose proof doesn't reach the published root is a number the distributor would not honour, so it is
# refused outright rather than logged and displayed.
def test_a_reward_that_fails_verification_is_not_stored(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT)])
    monkeypatch.setattr(merkl, "verified_amount", lambda account, token, amount, proofs, expected: None)

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW) is None


def test_a_root_the_contract_will_not_give_stops_the_whole_chain(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT)], root='')

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalReceivable().claims(WALLET, NOW) == []


def test_no_api_key_reads_nothing(eth_wallet, monkeypatch):
    JalSettings().setValue("ApiKey_Etherscan", "")
    asked = _fake_chain(monkeypatch, [_reward(GHO_CONTRACT)])

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert asked['calls'] == []           # not a single eth_call was made
    assert JalReceivable().claims(WALLET, NOW) == []


def test_a_wallet_with_no_campaign_records_nothing(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [], answer=[])

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalReceivable().claims(WALLET, NOW) == []


def test_an_unreadable_answer_records_nothing(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [], answer=None)

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalReceivable().claims(WALLET, NOW) == []


# The chain filter of the quote-update dialog, which is the only control this feature has
def test_locations_filter_selects_which_chains_are_asked(eth_wallet, monkeypatch):
    asked = _fake_chain(monkeypatch, [_reward(GHO_CONTRACT)])

    assert ChainBalanceReader().read_receivables(NOW, locations=[AssetLocation.ARB_BLOCKCHAIN]) == 0
    assert asked['api'] == []
    assert ChainBalanceReader().read_receivables(NOW, locations=[AssetLocation.ETH_BLOCKCHAIN]) == 1


# One request per WALLET, not per account: the same address is held on several chains and Merkl answers about all of
# them at once.
def test_one_address_on_two_chains_is_one_request(eth_wallet, monkeypatch):
    JalAccountCreator(currency_id=USD, number='', name='ARB wallet', investing=1, organization=1, precision=18,
                      account_type=PredefinedAccountType.Wallet, address=WALLET_ADDRESS,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    asked = _fake_chain(monkeypatch, [_reward(GHO_CONTRACT)])

    ChainBalanceReader().read_receivables(NOW)
    assert len(asked['api']) == 1
    assert sorted(asked['api'][0][1]['chainId'].split(',')) == ['1', '42161']


# A stream that stops being reported must be written down as zero: the display reads the latest row, so a claim that
# quietly disappeared would otherwise be shown as owed for good.
def test_a_stream_that_disappears_is_written_down_as_zero(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT)])
    ChainBalanceReader().read_receivables(NOW)
    assert JalReceivable().claims(WALLET, NOW)

    _fake_chain(monkeypatch, [])
    ChainBalanceReader().read_receivables(LATER)
    assert JalReceivable().claims(WALLET, LATER) == []
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, LATER)['amount'] == Decimal('0')
    # ...but the earlier reading is untouched, because it is what was true then
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)['amount'] == Decimal('1')


# A reward is paid in a coin the account holds none of, so refusing an unknown token would silence the feature for
# exactly the case it exists to catch.
def test_a_reward_in_an_unknown_token_creates_the_asset(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(ARB_CONTRACT, symbol='ARB', decimals=18, amount='2500000000000000000')])

    assert ChainBalanceReader().read_receivables(NOW) == 1
    symbol = JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, ARB_CONTRACT)
    assert symbol.id()
    asset = symbol.asset()
    assert asset.symbol(currency=USD, location=AssetLocation.ETH_BLOCKCHAIN) == 'ARB'
    assert asset.decimals() == 18
    assert JalReceivable().latest(WALLET, asset.id(), merkl.DISTRIBUTOR, NOW)['amount'] == Decimal('2.5')


def test_a_second_reading_reuses_the_asset_it_created(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(ARB_CONTRACT, symbol='ARB')])
    ChainBalanceReader().read_receivables(NOW)
    created = JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, ARB_CONTRACT).asset().id()

    _fake_chain(monkeypatch, [_reward(ARB_CONTRACT, symbol='ARB')])
    ChainBalanceReader().read_receivables(LATER)
    assert JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, ARB_CONTRACT).asset().id() == created


# An answer of, say, 200 decimals is not a token with 200 decimal places - it is an answer that means something else,
# and using it would divide the reward into nothing. Nothing is created for it either.
def test_an_implausible_decimals_creates_nothing_and_stores_nothing(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(ARB_CONTRACT, symbol='ARB', decimals=200)])

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, ARB_CONTRACT).id() == 0


def test_amounts_keep_every_decimal(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='91868751770182036697')])

    ChainBalanceReader().read_receivables(NOW)
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)['amount'] \
        == Decimal('91.868751770182036697')


# ----------------------------------------------------------------------------------------------------------------------
# AAVE'S SAFETY MODULE, the second source and the one with no distribution behind it at all: two view calls say which
# token a module pays and how much of it is owed right now.
#
# The shape is what makes it a receivable rather than an accrual - the module pays AAVE while the position is held in
# stkAAVE, a different asset, so nothing the account holds grows and 'chain_balances' could not express it.

# The reward token of both modules, already in the ledger - which is the ordinary case, and what makes a module's
# answer reach the Balances tree the moment it is read.
@pytest.fixture
def aave_staker(eth_wallet):
    global AAVE
    creator = JalAssetCreator(PredefinedAsset.Crypto, "Aave Token")
    symbol_id = creator.add_symbol('AAVE', USD, AssetLocation.ETH_BLOCKCHAIN)
    creator.add_identifier(symbol_id, SymbolId.ETH_ADDRESS, AAVE_CONTRACT)
    AAVE = creator.commit().id()
    create_quotes(AAVE, USD, [(NOW, Decimal('250'))])
    yield


# The live figure of 2026-08-31, which matched the dApp's to the last digit
def test_what_a_module_owes_is_read_and_scaled(aave_staker, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 6901428237272013)})

    assert ChainBalanceReader().read_receivables(NOW) == 1
    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_AAVE, NOW)['amount'] \
        == Decimal('0.006901428237272013')


# The whole point of the source: rewards accrue against an index that only settles when the staker interacts with the
# contract, so the stored mapping holds a fraction of the truth and only the view can be believed.
def test_the_view_is_asked_and_never_the_stored_mapping(aave_staker, monkeypatch):
    asked = _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 1)})
    ChainBalanceReader().read_receivables(NOW)

    calls = [data for contract, data in asked['calls'] if contract == aave.STAKED_AAVE]
    assert aave.SELECTOR_TOTAL_REWARDS + '0' * 24 + WALLET_ADDRESS[2:] in calls
    assert not [x for x in calls if x.startswith('0x7e90d7ef')]     # stakerRewardsToClaim(), the settled remainder


# A module that changed the token it pays would otherwise be read as still paying the old one, and a reward booked
# against the wrong asset is wrong in the one way nobody would ever notice.
def test_the_asset_is_the_token_the_module_names(aave_staker, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (GHO_CONTRACT, 2000000000000000000)})

    ChainBalanceReader().read_receivables(NOW)
    assert JalReceivable().latest(WALLET, GHO, aave.STAKED_AAVE, NOW)['amount'] == Decimal('2')
    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_AAVE, NOW) is None


# Both modules pay AAVE, which is exactly the collision the 'source' column exists for: two rows, not one overwriting
# the other, and two rows the report can tell apart.
def test_both_modules_paying_one_token_are_two_claims(aave_staker, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 1000000000000000000),
                                      aave.STAKED_GHO: (AAVE_CONTRACT, 3000000000000000000)})

    assert ChainBalanceReader().read_receivables(NOW) == 2
    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_AAVE, NOW)['amount'] == Decimal('1')
    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_GHO, NOW)['amount'] == Decimal('3')
    assert JalAccount(WALLET).balance(NOW) == Decimal('1000')      # 4 AAVE quoted at 250


# A wallet that holds none of the staked token is owed nothing forever, and every reading asks both modules about
# every Ethereum wallet - so a zero must not leave an asset behind.
def test_a_module_owing_nothing_records_nothing_and_creates_nothing(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 0)})

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, AAVE_CONTRACT).id() == 0
    assert JalReceivable().claims(WALLET, NOW) == []


# ...but a claim JAL already recorded gets its zero written down, because that zero is what stops a reward that has
# been claimed from being shown as still owed.
def test_a_module_that_stops_paying_is_written_down_as_zero(aave_staker, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 5000000000000000000)})
    ChainBalanceReader().read_receivables(NOW)

    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 0)})
    ChainBalanceReader().read_receivables(LATER)

    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_AAVE, LATER)['amount'] == Decimal('0')
    assert JalReceivable().claims(WALLET, LATER) == []
    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_AAVE, NOW)['amount'] == Decimal('5')


# A module that won't answer is not a module that owes nothing. Erasing a real receivable because a node was having a
# bad afternoon would lose money on screen.
def test_a_module_that_cannot_be_read_leaves_the_last_reading_alone(aave_staker, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 5000000000000000000)})
    ChainBalanceReader().read_receivables(NOW)

    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: ('', 0)})   # REWARD_TOKEN() answers with nothing
    assert ChainBalanceReader().read_receivables(LATER) == 0

    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_AAVE, LATER)['amount'] == Decimal('5')


# Each source zeroes its OWN rows and nothing else: another distributor paying the same token to the same wallet is a
# different claim, and one source going quiet says nothing whatever about the other.
def test_a_module_going_quiet_does_not_erase_what_merkl_owes(aave_staker, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='7000000000000000000')],
                modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 5000000000000000000)})
    assert ChainBalanceReader().read_receivables(NOW) == 2

    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='7000000000000000000')],
                modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 0)})
    ChainBalanceReader().read_receivables(LATER)

    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, LATER)['amount'] == Decimal('7')
    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_AAVE, LATER)['amount'] == Decimal('0')


# The reward is paid in a coin the account may hold none of and may never have seen, so the token is created from
# what the contract itself says - the ticker included, which no view of the module reports.
def test_a_reward_in_an_unknown_token_is_created_from_the_contract(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 2500000000000000000)},
                ticker='AAVE', name='Aave Token', decimals=18)

    assert ChainBalanceReader().read_receivables(NOW) == 1
    asset = JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, AAVE_CONTRACT).asset()
    assert asset.name() == 'Aave Token'
    assert asset.symbol(currency=USD, location=AssetLocation.ETH_BLOCKCHAIN) == 'AAVE'
    assert asset.decimals() == 18
    assert JalReceivable().latest(WALLET, asset.id(), aave.STAKED_AAVE, NOW)['amount'] == Decimal('2.5')


# A token nobody can even name is not written down under an invented ticker - an asset that cannot be told from
# another is worse than no asset at all.
def test_a_token_that_will_not_say_its_ticker_creates_nothing(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 2500000000000000000)}, ticker='')

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, AAVE_CONTRACT).id() == 0


# The scale of the reward is the token's own, and a known token that carries none yet is asked for it once
def test_the_scale_comes_from_the_token_when_it_is_not_known_yet(aave_staker, monkeypatch):
    _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 1500000)}, decimals=6)

    ChainBalanceReader().read_receivables(NOW)
    assert JalAsset(AAVE).decimals() == 6
    assert JalReceivable().latest(WALLET, AAVE, aave.STAKED_AAVE, NOW)['amount'] == Decimal('1.5')


# The modules live on Ethereum and nowhere else, so a wallet held on another chain must not be asked about them
def test_the_modules_are_asked_on_ethereum_only(aave_staker, monkeypatch):
    JalAccountCreator(currency_id=USD, number='', name='ARB wallet', investing=1, organization=1, precision=18,
                      account_type=PredefinedAccountType.Wallet, address=WALLET_ADDRESS,
                      chain=AssetLocation.ARB_BLOCKCHAIN).commit()
    asked = _fake_chain(monkeypatch, modules={aave.STAKED_AAVE: (AAVE_CONTRACT, 1000000000000000000)})

    assert ChainBalanceReader().read_receivables(NOW, locations=[AssetLocation.ARB_BLOCKCHAIN]) == 0
    assert [x for x in asked['calls'] if x[0] in aave.SAFETY_MODULES] == []
    assert ChainBalanceReader().read_receivables(NOW, locations=[AssetLocation.ETH_BLOCKCHAIN]) == 1


# The report names a source from the protocol registry, and both modules are registered there already - so a claim of
# theirs is named without a line of display code being touched.
def test_a_module_claim_is_named_by_the_protocol_registry(aave_staker):
    JalReceivable().store(NOW, WALLET, AAVE, aave.STAKED_AAVE, Decimal('0.5'))
    JalAccount(WALLET).invalidate_cache()
    model = _staking_rows()

    assert model.data_text(model._data[0], 1) == 'Staked Aave (stkAAVE)'
    assert model.data_text(model._data[0], 8) == aave.STAKED_AAVE
    assert model._data[0]['accrued'] == Decimal('0.5')
    assert model._data[0]['value'] == Decimal('125')


# ----------------------------------------------------------------------------------------------------------------------
# STORAGE

# A claim is a "now" value, and letting today's reading into a report dated last January would show a reward that did
# not exist then. This is the one rule that carries over from JalChainBalance.accrual().
def test_a_reading_is_invisible_to_a_report_dated_before_it(eth_wallet):
    JalReceivable().store(NOW, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('5'))

    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, d2t(260801)) is None
    assert JalReceivable().claims(WALLET, d2t(260801)) == []
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)['amount'] == Decimal('5')


def test_the_series_is_kept_as_a_history(eth_wallet):
    JalReceivable().store(NOW, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('1'))
    JalReceivable().store(LATER, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('3'))

    history = JalReceivable().claim_history(WALLET, GHO, merkl.DISTRIBUTOR)
    assert [x['accrued'] for x in history] == [Decimal('1'), Decimal('3')]
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, LATER)['amount'] == Decimal('3')


def test_a_repeated_reading_of_one_second_replaces_it(eth_wallet):
    JalReceivable().store(NOW, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('1'))
    JalReceivable().store(NOW, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('2'))

    assert len(JalReceivable().claim_history(WALLET, GHO, merkl.DISTRIBUTOR)) == 1
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)['amount'] == Decimal('2')


def test_forgetting_a_claim_removes_its_whole_series(eth_wallet):
    JalReceivable().store(NOW, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('1'))
    JalReceivable().store(LATER, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('3'))
    JalReceivable().forget(WALLET, GHO, merkl.DISTRIBUTOR)

    assert JalReceivable().claim_history(WALLET, GHO, merkl.DISTRIBUTOR) == []
    assert JalReceivable().known_claims(WALLET) == []


# ----------------------------------------------------------------------------------------------------------------------
# DISPLAY. Where a receivable may be seen, and - just as much the point - where it may not.

def _claim(amount='12.5', source=None, asset=None, timestamp=None):
    JalReceivable().store(timestamp or NOW, WALLET, asset or GHO, source or merkl.DISTRIBUTOR, Decimal(amount))
    JalAccount(WALLET).invalidate_cache()


# The prepared rows of a report tree live in the tree rather than in a list, so the leaves are collected back out
def _leaves(root) -> list:
    rows = []

    def collect(item):
        if not item.childrenCount():
            rows.append(item.details())
        for i in range(item.childrenCount()):
            collect(item.getChild(i))
    collect(root)
    return rows


def _staking_rows():
    from PySide6.QtWidgets import QTableView
    from jal.reports.staking import StakingListModel
    model = StakingListModel(QTableView())
    model.updateView(timestamp=NOW, currency_id=USD, show_closed=False)
    return model


# The 'Accrued' column already means "earned and not yet received", which is exactly what a receivable is - the only
# difference being that it waits at a distributor instead of inside a container.
def test_the_staking_report_lists_a_claim_in_the_accrued_column(eth_wallet):
    _claim('12.5')
    model = _staking_rows()

    assert len(model._data) == 1
    row = model._data[0]
    assert row['box'] is None
    assert row['accrued'] == Decimal('12.5')
    assert row['amount'] == Decimal('0')          # no staked principal - a reward was never deposited anywhere
    assert row['value'] == Decimal('12.5')        # GHO is quoted at 1
    assert model._value_total == Decimal('12.5')


def test_a_claim_row_names_the_wallet_and_the_distributor(eth_wallet):
    _claim()
    model = _staking_rows()
    row = model._data[0]

    assert model.data_text(row, 0) == 'ETH wallet'
    assert model.data_text(row, 1) == 'Merkl Distributor'      # from the protocol registry, not stored
    assert model.data_text(row, 3) == 'GHO'
    assert model.data_text(row, 7) == 0                        # no 'staked since' - it was never staked
    assert model.data_text(row, 8) == merkl.DISTRIBUTOR


# An unregistered distributor still has to say who owes the money, and an address is something one can look up.
def test_an_unregistered_distributor_is_shown_by_its_address(eth_wallet):
    _claim(source='0x' + 'f' * 40)
    assert _staking_rows().data_text(_staking_rows()._data[0], 1) == '0x' + 'f' * 40


def test_a_claim_that_has_been_paid_is_not_listed(eth_wallet):
    _claim('0')
    assert _staking_rows()._data == []


# Selecting a claim must not offer to close it: a claim is not a position that can be closed, it ends when it is paid
def test_a_claim_row_points_at_no_box(eth_wallet):
    from PySide6.QtCore import QModelIndex
    _claim()
    model = _staking_rows()
    index = model.index(0, 0, QModelIndex())

    assert model.box(index) is None
    assert model.account(index) == WALLET


def test_the_balances_tree_counts_what_is_owed(eth_wallet):
    before = JalAccount(WALLET).balance(NOW)
    _claim('12.5')

    assert JalAccount(WALLET).balance(NOW) - before == Decimal('12.5')


def test_the_balances_tree_ignores_a_claim_dated_after_the_report(eth_wallet):
    _claim('12.5', timestamp=LATER)
    assert JalAccount(WALLET).balance(NOW) == Decimal('0')
    assert JalAccount(WALLET).balance(LATER) == Decimal('12.5')


# A wallet whose only content is a receivable has to appear in the tree at all - the model drops accounts valued at
# zero, so this is what makes an otherwise empty wallet visible.
def test_a_wallet_holding_only_a_claim_appears_in_the_tree(eth_wallet):
    from PySide6.QtWidgets import QWidget
    from jal.db.balances_model import BalancesModel
    from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter
    _claim('12.5')
    parent = QWidget()   # a view built without one aborts the process from the cyclic collector
    model = BalancesModel(TreeViewWithFooter(parent))
    model._currency = USD
    model._date = NOW
    model.prepareData()

    rows = _leaves(model._root)
    assert [x['account_name'] for x in rows] == ['ETH wallet']
    assert [x['value'] for x in rows] == [Decimal('12.5')]


# ----------------------------------------------------------------------------------------------------------------------
# WHERE A RECEIVABLE MUST NOT APPEAR. A claim is unrealized value in an asset the ledger holds none of; letting it
# into a tax figure or a realized profit/loss would be inventing income that has not happened and may never happen.

# assets_list() is the single mechanism the tax report (data_export/taxes_flow.py) and the realized profit/loss
# report (reports/profit_loss.py) both walk, and it was deliberately NOT widened for this feature. Pinning it here
# pins both of them: a receivable that never enters this list cannot reach either.
def test_a_claim_never_enters_the_list_the_tax_and_profit_loss_reports_walk(eth_wallet):
    create_trades(WALLET, [(d2t(260101), d2t(260101), GHO, Decimal('100'), Decimal('1'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    before = [(x['asset'].id(), x['amount'], x['value']) for x in JalAccount(WALLET).assets_list(NOW)]
    _claim('12.5')

    assert [(x['asset'].id(), x['amount'], x['value']) for x in JalAccount(WALLET).assets_list(NOW)] == before
    assert GHO in [x[0] for x in before]


def test_a_claim_is_invisible_to_an_account_that_holds_nothing_else(eth_wallet):
    _claim('12.5')
    assert JalAccount(WALLET).assets_list(NOW) == []


def test_a_claim_does_not_reach_the_asset_portfolio(eth_wallet):
    from PySide6.QtWidgets import QTreeView
    from jal.db.holdings_model import HoldingsModel
    create_trades(WALLET, [(d2t(260101), d2t(260101), GHO, Decimal('100'), Decimal('1'), Decimal('0'))])
    Ledger().rebuild(from_timestamp=0)
    model = HoldingsModel(QTreeView())
    model._currency = USD
    model._date = NOW
    model.prepareData()
    before = [(x['asset_id'], x['qty']) for x in _leaves(model._root)]

    _claim('12.5')
    model.prepareData()
    assert [(x['asset_id'], x['qty']) for x in _leaves(model._root)] == before
    # the booked position only - the claim adds neither a row of its own nor a unit to this one
    assert [x for x in before if x[0] == GHO] == [(GHO, Decimal('100'))]



# ----------------------------------------------------------------------------------------------------------------------
# THE CLAIM HISTORY CHART - the sawtooth a campaign draws: it climbs while the reward accrues and drops to zero when
# it is claimed, at which moment the value stops being a receivable and becomes a StakingReward in the ledger.

def test_the_claim_chart_draws_the_series_the_updates_left_behind(eth_wallet):
    from jal.widgets.accrual_chart import ReceivableChartWindow
    JalReceivable().store(d2t(260801), WALLET, GHO, merkl.DISTRIBUTOR, Decimal('1'), Decimal('0.2'))
    JalReceivable().store(NOW, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('3'), Decimal('0.5'))

    window = ReceivableChartWindow(WALLET, GHO, merkl.DISTRIBUTOR)
    assert window.ready


def test_one_reading_is_not_a_history_yet(eth_wallet):
    from jal.widgets.accrual_chart import ReceivableChartWindow
    _claim('1')
    assert ReceivableChartWindow(WALLET, GHO, merkl.DISTRIBUTOR).ready


def test_the_chart_series_carries_both_amounts(eth_wallet):
    JalReceivable().store(d2t(260801), WALLET, GHO, merkl.DISTRIBUTOR, Decimal('1'), Decimal('0.2'))
    JalReceivable().store(NOW, WALLET, GHO, merkl.DISTRIBUTOR, Decimal('0'), Decimal('0.5'))

    series = JalReceivable().claim_history(WALLET, GHO, merkl.DISTRIBUTOR)
    assert [x['accrued'] for x in series] == [Decimal('1'), Decimal('0')]
    assert [x['pending'] for x in series] == [Decimal('0.2'), Decimal('0.5')]


# The axis bounds are shared with the accrual chart, and a series that has dropped to zero everywhere must not make
# it collapse
def test_a_series_that_is_all_zero_still_has_an_axis(eth_wallet):
    from jal.widgets.accrual_chart import axis_range
    series = [{'timestamp': d2t(260801), 'accrued': Decimal('0')}, {'timestamp': NOW, 'accrued': Decimal('0')}]
    bounds = axis_range(series)
    assert bounds[2] == 0 and bounds[3] > 0


# ----------------------------------------------------------------------------------------------------------------------
# THE MIGRATION. 'receivables' rides in the unreleased delta 67 rather than a delta of its own, so what has to hold is
# that the statements still apply cleanly to a database built by the previous schema, and that the delta still leaves
# the version where it found it.
#
# It is a pure CREATE, exactly as delta 62 was for 'chain_balances': nothing existing is read, rewritten or dropped,
# so a database upgraded by it behaves precisely as it did before.
_MIGRATION_FROM = "-- CLAIMABLE REWARDS THAT HAVE NOT BEEN PAID YET"
_MIGRATION_TO = "-- Set new DB schema version"


def test_the_migration_creates_the_table_on_an_older_database(prepare_db, project_root):
    JalDB._exec("DROP TABLE IF EXISTS receivables", commit=True)
    assert JalDB._read("SELECT COUNT(*) FROM sqlite_master WHERE name='receivables'") == 0

    with open(project_root + "/jal/updates/jal_delta_67.sql") as delta:
        text = delta.read()
    start, end = text.index(_MIGRATION_FROM), text.index(_MIGRATION_TO)
    for statement in sqlparse.split(text[start:end]):
        if not sqlparse.format(statement, strip_comments=True).strip():
            continue   # a run of comment lines is not a statement
        assert JalDB._exec(statement.strip()) is not None, f"Migration statement failed: {statement}"

    assert JalDB._read("SELECT COUNT(*) FROM sqlite_master WHERE name='receivables'") == 1
    assert JalDB._read("SELECT COUNT(*) FROM sqlite_master WHERE name='receivables_uniqueness'") == 1


# The version the delta leaves behind has to match what the application demands of a database, or every start would
# either re-run the delta or refuse to open the file.
def test_the_delta_and_the_required_version_agree(project_root):
    from constants import Setup
    latest_delta = f"/jal/updates/{Setup.UPDATE_PREFIX}{Setup.DB_REQUIRED_VERSION}.sql"
    with open(project_root + latest_delta) as delta:
        assert f"UPDATE settings SET value={Setup.DB_REQUIRED_VERSION} WHERE name=\'SchemaVersion\'" in delta.read()
    with open(project_root + "/jal/" + Setup.INIT_SCRIPT_PATH) as init:
        assert f"VALUES(\'SchemaVersion\', {Setup.DB_REQUIRED_VERSION})" in init.read()


# The unique key is what makes a second reading of the same second REPLACE rather than duplicate, and what keeps two
# distributors paying one token apart. Both halves are asserted at the storage level above; this pins the index itself.
def test_the_unique_key_is_account_asset_source_and_time(prepare_db):
    columns = JalDB._read("SELECT sql FROM sqlite_master WHERE name='receivables_uniqueness'")
    assert "account_id" in columns and "asset_id" in columns and "source" in columns and "timestamp" in columns


# A line JAL couldn't READ is not a claim that has been paid. Erasing a real receivable because verification failed
# once, or because a token stopped resolving, would lose money on screen on a bad afternoon.
def test_a_reading_that_fails_does_not_erase_what_was_recorded_before(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='4000000000000000000')])
    ChainBalanceReader().read_receivables(NOW)
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)['amount'] == Decimal('4')

    # the source still reports the stream, but its proof no longer verifies
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='4000000000000000000')])
    monkeypatch.setattr(merkl, "verified_amount", lambda account, token, amount, proofs, expected: None)
    ChainBalanceReader().read_receivables(LATER)

    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, LATER)['amount'] == Decimal('4')
    assert JalReceivable().claims(WALLET, LATER)[0]['amount'] == Decimal('4')


# An asset is invented only when there is something to record in it. Merkl reports a campaign for as long as it ever
# existed, so most streams read zero - and creating a quote-less asset for each of them would fill the asset list with
# tokens the account has never held and never will.
def test_a_stream_claimed_to_zero_creates_no_asset(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(ARB_CONTRACT, symbol='ARB', amount='3000000000000000000')],
                claimed={ARB_CONTRACT: 3000000000000000000})

    assert ChainBalanceReader().read_receivables(NOW) == 0
    assert JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, ARB_CONTRACT).id() == 0


# ...but a stream JAL already knows still gets its zero written down, because that zero is what stops a figure that
# has been paid from lingering on screen.
def test_a_known_stream_claimed_to_zero_is_still_recorded(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(GHO_CONTRACT, amount='3000000000000000000')],
                claimed={GHO_CONTRACT: 3000000000000000000})

    ChainBalanceReader().read_receivables(NOW)
    assert JalReceivable().latest(WALLET, GHO, merkl.DISTRIBUTOR, NOW)['amount'] == Decimal('0')


# A ticker is not unique and two different contracts sharing one is not a corner case: Aave's USDG receipt is
# '0x7c0477d0...' "Aave Ethereum USDG" and '0xb0217f23...' "Aave Ethereum USDG (wrapped)", both answering 'aEthUSDG'.
# The name has to come from the contract or the two assets are indistinguishable in every list that shows them.
def test_a_created_asset_is_named_by_the_contract_not_the_ticker(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(ARB_CONTRACT, symbol='aEthUSDG', amount='1000000000000000000')],
                name='Aave Ethereum USDG (wrapped)')

    ChainBalanceReader().read_receivables(NOW)
    asset = JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, ARB_CONTRACT).asset()
    assert asset.name() == 'Aave Ethereum USDG (wrapped)'
    assert asset.symbol(currency=USD, location=AssetLocation.ETH_BLOCKCHAIN) == 'aEthUSDG'


# A contract that won't say its name is not a reason to refuse the reward - the ticker is a worse name, not no name.
def test_a_nameless_contract_falls_back_to_the_ticker(eth_wallet, monkeypatch):
    _fake_chain(monkeypatch, [_reward(ARB_CONTRACT, symbol='ARB', amount='1000000000000000000')], name=None)

    ChainBalanceReader().read_receivables(NOW)
    assert JalSymbol.find_by_identifier(SymbolId.ETH_ADDRESS, ARB_CONTRACT).asset().name() == 'ARB'
