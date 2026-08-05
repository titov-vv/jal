import json
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from constants import PredefinedAccountType, AssetLocation, PredefinedAsset, SymbolId, TokenList, TokenListKind
from jal.data_import.statement import JSF, Statement_ImportError
from jal.db.account import JalAccountCreator
from jal.db.asset import JalAssetCreator
from jal.db.settings import JalSettings
from jal.db.symbol import JalSymbol
from jal.db.token_blacklist import JalTokenBlacklist
from jal.net.chain_fetchers.avalanche import AvalancheFetcher
from jal.net.downloader import llama_coin_key
from jal.net.token_lists import TokenListProvider, _parse_tokenlist

# The three fixtures beside this file are the real validation wallet's whole Avalanche history, anonymized: every
# address and every transaction hash is replaced, and the block numbers and amounts are shifted so that no record
# can be looked up on-chain and traced back - an address, once published, is a permanent record. What is
# kept verbatim is what the classifier is judged by - the shape of each transaction, and the spam token's on-chain
# name and ticker, which is what the filter has to reject.
WALLET = "0x2222222222222222222222222222222222222222"
SENDER = "0x3333333333333333333333333333333333333333"          # paid the wallet AVAX twice
SPAM_SENDER = "0x4444444444444444444444444444444444444444"
SPAM_CONTRACT = "0x5555555555555555555555555555555555555555"   # the 'ecAVAX' airdrop's contract
DUST_SENDER = "0x6666666666666666666666666666666666666666"     # the AVAX dust delivered with that airdrop
RELAYER = "0x7777777777777777777777777777777777777777"         # a contract that delivered AVAX to the wallet
# The real Avalanche USDC contract, like the ETH test keeps the real mainnet one: it belongs to nobody in
# particular, and only a real address can be checked against a real allow-list and a real pricing key.
USDC_CONTRACT = "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e"

_FIXTURE = {"txlist": "avax_txlist.json", "tokentx": "avax_tokentx.json", "txlistinternal": "avax_internal.json"}


@pytest.fixture
def avax_wallet(prepare_db):
    JalSettings().setValue("ApiKey_Routescan", "test-key")
    account = JalAccountCreator(currency_id=2, number='', name='AVAX wallet', investing=1, organization=1,
                                account_type=PredefinedAccountType.Wallet, address=WALLET,
                                chain=AssetLocation.AVAX_BLOCKCHAIN).commit()
    assert account.id() == 1
    yield account


# Replaces the network with the recorded Routescan answers - which are Etherscan-shaped, that being the whole reason
# this chain is a subclass rather than a fetcher of its own.
@pytest.fixture
def fetcher(avax_wallet, data_path, monkeypatch):
    def fake_pages(self, action, start_block):
        with open(data_path + _FIXTURE[action], 'r', encoding='utf-8') as f:
            result = json.load(f)['result']
        return [x for x in result if int(x.get('blockNumber', 0)) >= start_block]

    monkeypatch.setattr(AvalancheFetcher, "_get_pages", fake_pages)
    yield AvalancheFetcher()


# Replaces the HTTP layer with a fake that serves a {action: [records]} history the way the API does - honouring
# 'startblock', 'page' and 'offset' - so that the paging loop itself is exercised instead of being stubbed out.
# Returns the list of parameter dicts that were sent, the url of each added under 'url'.
def _fake_api(monkeypatch, history: dict) -> list:
    sent = []

    class FakeRequest:
        GET = 'GET'

        def __init__(self, method, url, params=None):
            sent.append(dict(params, url=url))
            records = [x for x in history.get(params['action'], [])
                       if int(x['blockNumber']) >= params['startblock']]
            page, offset = params['page'], params['offset']
            self._result = records[(page - 1) * offset:page * offset]

        @staticmethod
        def isRunning():
            return False

        def data(self):
            return json.dumps({"status": "1", "message": "OK", "result": self._result})

    monkeypatch.setattr("jal.net.chain_fetchers.evm.WebRequest", FakeRequest)
    return sent


# Runs a fresh fetcher against a hand-built {action: [records]} history and returns the assembled JSF
def _drive(avax_wallet, monkeypatch, pages):
    def fake_pages(self, action, start_block):
        return [r for r in pages.get(action, []) if int(r['blockNumber']) >= start_block]
    monkeypatch.setattr(AvalancheFetcher, "_get_pages", fake_pages)
    instance = AvalancheFetcher()
    return instance, instance.fetch(avax_wallet)


def _tx(tx_hash, block, frm, to, value=0, gas_used='21000', gas_price='25000000000'):
    return {'hash': tx_hash, 'blockNumber': str(block), 'transactionIndex': '0', 'timeStamp': '1780000000',
            'from': frm, 'to': to, 'value': str(value), 'gasUsed': gas_used, 'gasPrice': gas_price,
            'isError': '0', 'methodId': '0x'}


def _token_tx(tx_hash, block, frm, to, value, contract=USDC_CONTRACT, symbol='USDC', name='USD Coin', decimals='6'):
    return {'hash': tx_hash, 'blockNumber': str(block), 'transactionIndex': '0', 'timeStamp': '1780000000',
            'from': frm, 'to': to, 'value': str(value), 'contractAddress': contract, 'tokenSymbol': symbol,
            'tokenName': name, 'tokenDecimal': decimals}


def _payments(data, payment_type) -> list:
    return [x for x in data.get(JSF.ASSET_PAYMENTS, []) if x['type'] == payment_type]


def _avax(wei) -> Decimal:
    return Decimal(wei) / (Decimal('10') ** 18)


# ----------------------------------------------------------------------------------------------------------------------
# The whole recorded history of the validation wallet, classified in one go. Four transactions, four different
# shapes, and none of them halts the import.
def test_recorded_history_is_classified(fetcher, avax_wallet):
    data = fetcher.fetch(avax_wallet)
    transfers = data[JSF.TRANSFERS]
    # Two plain AVAX receives, plus the AVAX a contract delivered on somebody's behalf - which is an ordinary
    # incoming transfer too: nothing in it says what it was sent for.
    assert [x['withdrawal'] for x in transfers] == [_avax('3120000000000000000'), _avax('1750000000000000000'),
                                                    _avax('2450000000000000000')]
    assert all(x['account'] == [0, 1, 1] for x in transfers)     # incoming, far side unknown to JAL
    assert [x['counterparty_address'] for x in transfers] == [SENDER, RELAYER, SENDER]
    # The wallet initiated none of them, so it paid gas for none of them either
    assert _payments(data, JSF.PAYMENT_GAS_FEE) == []
    # It has never sent a transaction on this chain - which is why the protocol registry for it is empty
    assert fetcher._new_cursor == '88000000'

    # The airdrop that came with the poisoning dust is quarantined, and the dust itself is booked as what it is.
    # Both belong to one transaction, and it must produce no transfer at all.
    assert JalTokenBlacklist.is_blacklisted(AssetLocation.AVAX_BLOCKCHAIN, SPAM_CONTRACT)
    assert not [s for a in data[JSF.ASSETS] for s in a[JSF.SYMBOLS] if s.get('address') == SPAM_CONTRACT]
    dust = _payments(data, JSF.PAYMENT_DUST_ATTACK)
    assert len(dust) == 1
    assert dust[0]['amount'] == _avax('7500000000000')
    # ... and no transfer was created for that transaction: everything it carried was either spam or dust
    assert not [x for x in data[JSF.TRANSFERS] if x['number'].endswith('2')]

    # Reading the whole recorded history leaves no window limit behind, and everything that was skipped is accounted
    # for - just the one spam/dust transaction above.
    assert fetcher._window_limit is None
    assert fetcher.skipped() == {"token quarantined as dust/spam": 1}


# The dust threshold is AVAX's own, not the ETH one EVMFetcher hands down: 0.0000075 AVAX is dust here while it
# would be an ordinary transfer under the inherited ETH threshold.
def test_dust_threshold_is_the_chain_s_own(fetcher, avax_wallet):
    assert AvalancheFetcher.native_dust_threshold != '0.0000001'
    assert fetcher._native_dust_threshold() == Decimal('0.0001')
    JalSettings().setValue("DustThreshold_AVAX", '0.000001')     # user-editable, and read per chain
    assert fetcher._native_dust_threshold() == Decimal('0.000001')
    data = fetcher.fetch(avax_wallet)
    assert _payments(data, JSF.PAYMENT_DUST_ATTACK) == []        # now above the threshold - an ordinary receive
    assert len(data[JSF.TRANSFERS]) == 4


# ----------------------------------------------------------------------------------------------------------------------
# Routescan, not Etherscan: a different root, a different key and a page budget that fits its result window.
def test_requests_go_to_routescan(avax_wallet, monkeypatch):
    sent = _fake_api(monkeypatch, {})
    AvalancheFetcher().fetch(avax_wallet)
    assert len(sent) == 3          # one page of each of the three account endpoints
    for params in sent:
        assert params['url'] == "https://api.routescan.io/v2/network/mainnet/evm/43114/etherscan/api"
        assert params['chainid'] == 43114
        assert params['apikey'] == 'test-key'
        assert params['offset'] == 1000
    assert [x['action'] for x in sent] == ["txlist", "tokentx", "txlistinternal"]


# Routescan refuses page x offset above 10000, so the page budget must not be able to ask for more than that
def test_page_budget_fits_the_result_window(avax_wallet):
    assert AvalancheFetcher.page_size * AvalancheFetcher.max_pages <= 10000


# The Routescan key is required and is not the Etherscan one - a wallet fetched with only the Etherscan key filled
# in must say what is missing rather than send an empty key and get an unhelpful refusal back.
def test_routescan_key_is_required(prepare_db):
    JalSettings().setValue("ApiKey_Routescan", '')
    JalSettings().setValue("ApiKey_Etherscan", 'etherscan-key')
    with pytest.raises(Statement_ImportError) as error:
        AvalancheFetcher()._api_key()
    assert "Routescan" in str(error.value)


# ----------------------------------------------------------------------------------------------------------------------
# An endpoint that uses up its whole page budget has not read the history to its end, and the cursor must not be
# allowed past the point where reading stopped - otherwise the transactions the OTHER endpoints did deliver from
# further on would advance it over the ones this endpoint never returned, and nothing would ever ask for them again.
def test_cursor_stops_where_the_result_window_ended(avax_wallet, monkeypatch):
    monkeypatch.setattr(AvalancheFetcher, "page_size", 2)
    monkeypatch.setattr(AvalancheFetcher, "max_pages", 1)
    TokenListProvider()._store(TokenList.COINGECKO_AVAX_LIST, TokenListKind.Allow, AssetLocation.AVAX_BLOCKCHAIN,
                               [{'address': USDC_CONTRACT, 'symbol': 'USDC', 'name': 'USD Coin'}])
    # txlist fills its single page and is cut off at block 300; tokentx reaches block 700 on its own, and its
    # transfer is a real one that would otherwise be imported and would carry the cursor with it.
    _fake_api(monkeypatch, {"txlist": [_tx('0xa1', 100, SENDER, WALLET, 10 ** 18),
                                       _tx('0xa2', 300, SENDER, WALLET, 2 * 10 ** 18),
                                       _tx('0xa3', 900, SENDER, WALLET, 3 * 10 ** 18)],
                            "tokentx": [_token_tx('0xb1', 700, SENDER, WALLET, 1000000)]})
    instance = AvalancheFetcher()
    data = instance.fetch(avax_wallet)
    assert instance._window_limit == 300
    # Only the block below the limit is imported. Block 300 itself is left out too - reading stopped in the middle
    # of it, so it can't be known to be complete.
    assert [x['number'] for x in data[JSF.TRANSFERS]] == ['0xa1']
    assert instance._new_cursor == '100'
    assert sum(instance.skipped().values()) == 2       # 0xa2 and the token transfer beyond it, both reported


# ----------------------------------------------------------------------------------------------------------------------
# The CoinGecko Avalanche list is parsed by the standard 'tokenlists' parser, and chain id 43114 has to map onto
# the Avalanche location for its records to survive at all
def test_token_list_covers_chain_43114():
    content = json.dumps({"tokens": [{"chainId": 43114, "address": USDC_CONTRACT, "symbol": "USDC",
                                      "name": "USD Coin"},
                                     {"chainId": 1, "address": USDC_CONTRACT, "symbol": "USDC", "name": "USD Coin"}]})
    parsed = _parse_tokenlist(content.encode(), [AssetLocation.AVAX_BLOCKCHAIN])
    assert parsed == [{'location_id': AssetLocation.AVAX_BLOCKCHAIN, 'address': USDC_CONTRACT,
                       'symbol': 'USDC', 'name': 'USD Coin'}]
    assert TokenList.COINGECKO_AVAX_LIST in TokenListProvider.SOURCES
    assert AssetLocation.AVAX_BLOCKCHAIN in TokenListProvider.SOURCES[TokenList.UNISWAP_DEFAULT]['chains']


# ----------------------------------------------------------------------------------------------------------------------
# DeFiLlama prices the native coin by its CoinGecko id and a token by the chain's own key prefix
def test_defillama_keys(prepare_db):
    def create_crypto(name, ticker, address='') -> int:
        creator = JalAssetCreator(PredefinedAsset.Crypto, name)
        symbol_id = creator.add_symbol(ticker, 2, location_id=AssetLocation.AVAX_BLOCKCHAIN)
        if address:
            creator.add_identifier(symbol_id, SymbolId.AVAX_ADDRESS, address)
        creator.commit()
        return symbol_id

    # A listing with no contract address behind it is the chain's native coin
    assert llama_coin_key(JalSymbol(create_crypto('Avalanche', 'AVAX'))) == "coingecko:avalanche-2"
    token = create_crypto('USD Coin', 'USDC', USDC_CONTRACT)
    assert llama_coin_key(JalSymbol(token)) == f"avax:{USDC_CONTRACT}"


# The chain is wired into the places a chain has to be wired into, and is discovered by the fetcher directory scan
def test_chain_is_registered():
    assert AssetLocation.AVAX_BLOCKCHAIN in AssetLocation.BLOCKCHAINS
    assert AssetLocation.address_id_of(AssetLocation.AVAX_BLOCKCHAIN) == SymbolId.AVAX_ADDRESS
    from jal.net.chain_fetchers import avalanche
    assert getattr(avalanche, "JAL_FETCHER_CLASS") == "AvalancheFetcher"
