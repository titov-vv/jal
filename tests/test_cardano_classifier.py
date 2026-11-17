from decimal import Decimal

import pytest
from bip_utils import Bip44Changes, CardanoIcarusSeedGenerator, CardanoShelley, Cip1852, Cip1852Coins

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedAccountType, PredefinedAsset, AssetLocation, AccountData
from jal.data_import.statement import JSF
from jal.db.account import JalAccountCreator, JalAccount
from jal.db.asset import JalAsset
from jal.db.db import JalDB
from jal.db.ledger import Ledger
from jal.db.operations import AssetIncome
from jal.db.staking import JalStakingBox
from jal.net.chain_fetchers.cardano import CardanoFetcher


TEST_MNEMONIC = "test walk nut penalty hip pave soap entry language right filter choice"


# Accounts 0 and 1 of the CIP-0019 test-vector mnemonic stand for the wallet and for somebody else - nobody's money
def _wallet(account_index: int) -> tuple:
    seed = CardanoIcarusSeedGenerator(TEST_MNEMONIC).Generate()
    wallet = CardanoShelley.FromCip1852Object(
        Cip1852.FromSeed(seed, Cip1852Coins.CARDANO_ICARUS).Purpose().Coin().Account(account_index))
    stake = wallet.StakingObject().PublicKey().ToAddress()
    return stake, wallet.Change(Bip44Changes.CHAIN_EXT).AddressIndex(0).PublicKeys().ToAddress()


OWN_STAKE, OWN_PAYMENT = _wallet(0)
OTHER_STAKE, OTHER_PAYMENT = _wallet(1)
BYRON = "Ae2tdPwUPEZFRbyhz3cpfC2CumGzNkFBN2L42rcUc2yjQpEkxDbkPodpMAi"     # a legacy address, it has no stake part
TIP = 1000


def utxo(lovelace: int, owner: str = 'own', assets=()) -> dict:
    stake, payment = {'own': (OWN_STAKE, OWN_PAYMENT), 'other': (OTHER_STAKE, OTHER_PAYMENT),
                      'byron': (None, BYRON)}[owner]
    return {"value": str(lovelace), "stake_addr": stake, "payment_addr": {"bech32": payment, "cred": None},
            "asset_list": list(assets), "datum_hash": None, "inline_datum": None, "reference_script": None}


# A tx_info record as Koios returns it; the values of each test balance: inputs + withdrawals = outputs + fee + deposit
def transaction(n: int, inputs: list, outputs: list, fee: int, **fields) -> dict:
    record = {"tx_hash": f"{n:064x}", "block_height": 10 * n, "tx_block_index": 0, "tx_timestamp": 1700000000 + n,
              "fee": str(fee), "deposit": "0", "treasury_donation": "0", "inputs": inputs, "outputs": outputs,
              "withdrawals": [], "certificates": [], "collateral_inputs": [], "collateral_output": None,
              "reference_inputs": [], "plutus_contracts": [], "native_scripts": [], "assets_minted": [],
              "voting_procedures": [], "proposal_procedures": []}
    record.update(fields)
    return record


def delegation(stake: str = OWN_STAKE) -> dict:
    return {"index": 0, "type": "pool_delegation",
            "info": {"stake_address": stake, "pool_id_bech32": "pool1" + "q" * 51, "pool_id_hex": "00" * 28}}


def registration(stake: str = OWN_STAKE) -> dict:
    return {"index": 0, "type": "stake_registration", "info": {"stake_address": stake, "deposit": "2000000"}}


def deregistration(stake: str = OWN_STAKE) -> dict:
    return {"index": 0, "type": "stake_deregistration", "info": {"stake_address": stake}}


def vote_delegation(stake: str = OWN_STAKE) -> dict:
    return {"index": 2, "type": "vote_delegation",
            "info": {"stake_address": stake, "drep_id": "drep_always_abstain", "drep_hex": None}}


def withdrawal(lovelace: int, stake: str = OWN_STAKE) -> dict:
    return {"amount": str(lovelace), "stake_addr": stake}


# The first delegation of a wallet, as wallets build it: key registration, pool and vote delegation in one go
def first_delegation(n: int, balance: int, fee: int) -> dict:
    return transaction(n, [utxo(balance)], [utxo(balance - fee - 2_000_000)], fee=fee, deposit="2000000",
                       certificates=[registration(), delegation(), vote_delegation()])


@pytest.fixture
def ada_wallet(prepare_db):
    yield JalAccountCreator(currency_id=2, number='', name='ADA wallet', investing=1, organization=1,
                            account_type=PredefinedAccountType.Wallet, address=OWN_STAKE,
                            chain=AssetLocation.ADA_BLOCKCHAIN).commit()


# Fetches the given transactions from a fake Koios that knows nothing else
def fetch(wallet, *transactions) -> tuple:
    fetcher = CardanoFetcher()
    by_hash = {x['tx_hash']: x for x in transactions}

    def get(endpoint, params):
        if endpoint == "tip":
            return [{"block_height": TIP}]
        return [{"tx_hash": x['tx_hash'], "block_height": x['block_height']} for x in transactions]
    fetcher._get = get
    fetcher._post = lambda endpoint, body: [by_hash[x] for x in body["_tx_hashes"]]
    return fetcher, fetcher.fetch(wallet)


# The wallet's stake key box with the deposit of an earlier registration in it
def deposit_box(wallet) -> JalStakingBox:
    fetcher, _ = fetch(wallet, first_delegation(0, 50_000_000, fee=176_000))
    fetcher.import_fetched()
    [box] = JalStakingBox.all_boxes()
    return box


def box_of(fetcher, transfer: dict, end: int) -> int:
    return fetcher.mapped_id(JSF.ACCOUNTS, transfer['account'][end])


def payments(data, payment_type) -> list:
    return [x for x in data[JSF.ASSET_PAYMENTS] if x['type'] == payment_type]


def ada(lovelace: int) -> Decimal:
    return Decimal(lovelace) / Decimal('1000000')


# ----------------------------------------------------------------------------------------------------------------------
def test_incoming_from_a_legacy_address(ada_wallet):
    received = transaction(1, [utxo(900_000_000, 'byron')],
                           [utxo(250_000_000), utxo(649_828_000, 'byron')], fee=172_000)
    _, data = fetch(ada_wallet, received)
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['account'] == [0, 1, 1]
    assert transfer['withdrawal'] == ada(250_000_000)
    assert transfer['fee'] == Decimal('0')                   # the sender paid it
    assert transfer['counterparty_address'] == BYRON
    assert transfer['number'] == received['tx_hash'] and transfer['timestamp'] == received['tx_timestamp']


# A Shelley sender is named by its stake address, which stands for all of its payment addresses
def test_incoming_sender_is_its_stake_address(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(30_000_000, 'other')],
                                            [utxo(20_000_000), utxo(9_830_000, 'other')], fee=170_000))
    assert data[JSF.TRANSFERS][0]['counterparty_address'] == OTHER_STAKE


def test_outgoing_excludes_the_change(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(50_000_000), utxo(7_000_000)],
                                            [utxo(10_000_000, 'other'), utxo(46_820_000)], fee=180_000))
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['account'] == [1, 0, 1]
    assert transfer['withdrawal'] == ada(10_000_000)
    assert transfer['fee'] == ada(180_000) and 'fee_symbol' in transfer
    assert transfer['counterparty_address'] == OTHER_STAKE


def test_own_move_is_only_a_fee(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(50_000_000)], [utxo(20_000_000), utxo(29_830_000)],
                                            fee=170_000))
    assert not data[JSF.TRANSFERS]
    [fee] = payments(data, JSF.PAYMENT_GAS_FEE)
    assert fee['amount'] == ada(170_000) and fee['event'] == JSF.EVENT_NO_OP


def test_delegation_is_only_a_fee(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(50_000_000)], [utxo(49_820_000)], fee=180_000,
                                            certificates=[delegation()]))
    assert not data[JSF.TRANSFERS]
    [fee] = payments(data, JSF.PAYMENT_GAS_FEE)
    assert fee['amount'] == ada(180_000) and fee['event'] == JSF.EVENT_POSITION_COMMAND


def test_withdrawal_is_a_staking_reward(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(50_000_000)], [utxo(52_820_000)], fee=180_000,
                                            withdrawals=[withdrawal(3_000_000)]))
    assert not data[JSF.TRANSFERS] and not payments(data, JSF.PAYMENT_GAS_FEE)
    [reward] = payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert reward['amount'] == ada(3_000_000)               # what the reward account paid, not the wallet's delta
    assert reward['fee'] == ada(180_000)


def test_withdrawal_with_a_payment(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(50_000_000)], [utxo(10_000_000, 'other'), utxo(42_820_000)],
                                            fee=180_000, withdrawals=[withdrawal(3_000_000)]))
    [reward] = payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert reward['amount'] == ada(3_000_000) and 'fee' not in reward
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['withdrawal'] == ada(10_000_000) and transfer['fee'] == ada(180_000)


# Somebody else's withdrawal in a transaction that pays the wallet is not the wallet's reward
def test_foreign_withdrawal_is_ignored(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(10_000_000, 'other')], [utxo(12_000_000), utxo(820_000, 'other')],
                                            fee=180_000, withdrawals=[withdrawal(3_000_000, OTHER_STAKE)]))
    assert not payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert data[JSF.TRANSFERS][0]['withdrawal'] == ada(12_000_000)


def test_registration_deposit_goes_to_a_new_box(ada_wallet):
    _, data = fetch(ada_wallet, first_delegation(1, 50_000_000, fee=176_000))
    assert not data[JSF.ASSET_PAYMENTS]                     # the fee is carried by the deposit, not a gas record
    [transfer] = data[JSF.TRANSFERS]
    [box] = [x for x in data[JSF.ACCOUNTS] if x['id'] == transfer['account'][1]]
    assert transfer['account'][0] == 1 and box['id'] != 1    # out of the wallet, into the box created at import
    assert box['name'] == "ADA wallet: stake key deposit"
    assert transfer['withdrawal'] == ada(2_000_000)
    assert transfer['fee'] == ada(176_000) and 'fee_symbol' in transfer
    assert 'counterparty_address' not in transfer
    assert not transfer['description'].startswith('[custody] ')
    assert not JalStakingBox.all_boxes()                     # nothing is written before the import


# Deregistration requires the reward account emptied, so wallets withdraw the rest in the same transaction
def test_deregistration_returns_the_deposit(ada_wallet):
    box = deposit_box(ada_wallet)
    fetcher, data = fetch(ada_wallet, transaction(1, [utxo(40_000_000)], [utxo(42_830_000)], fee=170_000,
                                                  deposit="-2000000", withdrawals=[withdrawal(1_000_000)],
                                                  certificates=[deregistration()]))
    [reward] = payments(data, JSF.PAYMENT_STAKING_REWARD)
    assert reward['amount'] == ada(1_000_000) and reward['fee'] == ada(170_000)
    [transfer] = data[JSF.TRANSFERS]
    assert box_of(fetcher, transfer, 0) == box.id() and transfer['account'][1:] == [1, 1]
    assert transfer['withdrawal'] == ada(2_000_000) and transfer['fee'] == Decimal('0')


def test_deregistration_alone_carries_the_fee(ada_wallet):
    deposit_box(ada_wallet)
    _, data = fetch(ada_wallet, transaction(1, [utxo(40_000_000)], [utxo(41_830_000)], fee=170_000,
                                            deposit="-2000000", certificates=[deregistration()]))
    assert not data[JSF.ASSET_PAYMENTS]
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['withdrawal'] == ada(2_000_000) and transfer['fee'] == ada(170_000)


# A deposit JAL never saw paid has no box to come back from; nothing is invented for it
def test_refund_without_a_box_stays_pending(ada_wallet):
    fetcher, data = fetch(ada_wallet, transaction(1, [utxo(40_000_000)], [utxo(41_830_000)], fee=170_000,
                                                  deposit="-2000000", certificates=[deregistration()]))
    [transfer] = data[JSF.TRANSFERS]
    assert transfer['account'] == [0, 1, 1]
    assert transfer['description'].startswith('[custody] ')
    assert any("no box" in x for x in fetcher.skipped())
    fetcher.import_fetched()
    assert not JalStakingBox.all_boxes()


def test_registration_with_a_payment(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(50_000_000)], [utxo(10_000_000, 'other'), utxo(37_820_000)],
                                            fee=180_000, deposit="2000000", certificates=[registration()]))
    sent, deposit = sorted(data[JSF.TRANSFERS], key=lambda x: x['withdrawal'], reverse=True)
    assert sent['withdrawal'] == ada(10_000_000) and sent['fee'] == ada(180_000)
    assert deposit['withdrawal'] == ada(2_000_000) and deposit['fee'] == Decimal('0')


# Register, deregister, register again, each in a fetch of its own: one box, filled, emptied and filled again, and
# the wallet short by the deposit and the fees alone
def test_deposit_round_trip_through_one_box(ada_wallet):
    ada_wallet.set_data(AccountData.Precision, 6)
    for transactions in ([transaction(1, [utxo(60_000_000, 'other')], [utxo(50_000_000), utxo(9_830_000, 'other')],
                                      fee=170_000),
                          first_delegation(2, 50_000_000, fee=176_000)],
                         [transaction(3, [utxo(47_824_000)], [utxo(49_654_000)], fee=170_000, deposit="-2000000",
                                      certificates=[deregistration()])],
                         [first_delegation(4, 49_654_000, fee=176_000)]):
        fetcher, _ = fetch(ada_wallet, *transactions)
        fetcher.import_fetched()
    [box] = JalStakingBox.all_boxes()
    assert box.protocol() == "Cardano stake key"
    pending = JalDB._read_to_list("SELECT oid FROM transfers WHERE withdrawal_account IS NULL "
                                  "OR deposit_account IS NULL", named=True)
    assert len(pending) == 1                                 # only the arrival from a stranger
    Ledger().rebuild(from_timestamp=0)
    ada_id = JalAsset.find({'symbol': 'ADA', 'type': PredefinedAsset.Crypto}).id()
    assert box.account().get_asset_amount(2 ** 31, ada_id) == ada(2_000_000)
    assert ada_wallet.get_asset_amount(2 ** 31, ada_id) == ada(50_000_000 - 2 * 176_000 - 170_000 - 2_000_000)


# A box created by an import that then failed is taken up again, not duplicated
def test_an_empty_box_left_behind_is_reused(ada_wallet):
    left = JalStakingBox.create(JalAccount(ada_wallet.id()), "ADA wallet: stake key deposit",
                                protocol="Cardano stake key")
    fetcher, data = fetch(ada_wallet, first_delegation(1, 50_000_000, fee=176_000))
    assert box_of(fetcher, data[JSF.TRANSFERS][0], 1) == left.id()
    fetcher.import_fetched()
    assert [x.id() for x in JalStakingBox.all_boxes()] == [left.id()]


def test_dust_is_recorded_as_an_attack(ada_wallet):
    _, data = fetch(ada_wallet, transaction(1, [utxo(5_000_000, 'other')], [utxo(1_000_000), utxo(3_830_000, 'other')],
                                            fee=170_000))
    assert not data[JSF.TRANSFERS]
    assert payments(data, JSF.PAYMENT_DUST_ATTACK)[0]['amount'] == ada(1_000_000)


@pytest.mark.parametrize("shape, reason", [
    (dict(inputs=[utxo(600_000_000)], outputs=[utxo(99_820_000)], deposit="500000000",
          certificates=[{"index": 0, "type": "drep_registration", "info": {"deposit": "500000000"}}]),
     "other than the wallet's stake key"),
    (dict(inputs=[utxo(50_000_000)], outputs=[utxo(46_820_000)], deposit="3000000",
          certificates=[registration()]), "doesn't match"),
    (dict(inputs=[utxo(50_000_000)], outputs=[utxo(47_820_000)], deposit="2000000",
          certificates=[registration(), delegation(OTHER_STAKE)]), "other than the wallet's stake key"),
    (dict(inputs=[utxo(10_000_000, 'other')], outputs=[utxo(1_500_000, assets=[{"policy_id": "00" * 28}]),
                                                       utxo(8_320_000, 'other')]), "tokens"),
    (dict(inputs=[utxo(50_000_000)], outputs=[utxo(49_820_000)], plutus_contracts=[{"valid_contract": True}],
          collateral_inputs=[utxo(5_000_000)]), "script"),
    (dict(inputs=[utxo(10_000_000), utxo(30_000_000, 'other')], outputs=[utxo(39_820_000)]), "somebody else"),
    (dict(inputs=[utxo(10_000_000, 'other')], outputs=[utxo(9_820_000)], certificates=[registration()]),
     "didn't fund"),
])
def test_unsupported_shapes_halt(ada_wallet, shape, reason):
    first = transaction(1, [utxo(5_000_000, 'other')], [utxo(4_830_000)], fee=170_000)
    halting = transaction(2, fee=180_000, **shape)
    fetcher, data = fetch(ada_wallet, first, halting)
    assert [x['number'] for x in data[JSF.TRANSFERS]] == [first['tx_hash']]      # what came before it is kept
    assert not data[JSF.ASSET_PAYMENTS]
    assert any(reason in x for x in fetcher.skipped()), fetcher.skipped()
    assert '"height": 10' in fetcher._new_cursor                                  # the next fetch retries it


def test_history_reaches_the_database(ada_wallet):
    ada_wallet.set_data(AccountData.Precision, 6)                # lovelace; the default 2 digits would round it away
    fetcher, _ = fetch(ada_wallet,
                       transaction(1, [utxo(900_000_000, 'byron')], [utxo(250_000_000), utxo(649_828_000, 'byron')],
                                   fee=172_000),
                       transaction(2, [utxo(250_000_000)], [utxo(249_820_000)], fee=180_000,
                                   certificates=[delegation()]),
                       transaction(3, [utxo(249_820_000)], [utxo(100_000_000, 'other'), utxo(152_640_000)],
                                   fee=180_000, withdrawals=[withdrawal(3_000_000)]))
    fetcher.import_fetched()
    Ledger().rebuild(from_timestamp=0)
    [reward] = AssetIncome.get_list(ada_wallet.id(), subtype=AssetIncome.StakingReward)
    assert reward.amount() == ada(3_000_000)
    assert ada_wallet.get_asset_amount(2 ** 31, reward.asset().id()) == ada(152_640_000)     # the wallet's own utxo
    assert JalAccount(ada_wallet.id()).get_data(AccountData.SyncCursor)
