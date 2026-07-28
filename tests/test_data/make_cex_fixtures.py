#!/usr/bin/env python3
"""Builds the synthetic KuCoin and Bitget statement fixtures for tests/test_data.

Every figure here is made up but internally consistent: the ledgers reconcile against the
balances the fixtures report, so the parsers' own acceptance checks run on them. See the
test module for the hand-computed values these are meant to produce.
"""
import os
import zipfile

BOM = '﻿'
KUCOIN_UID = '100000001'
BITGET_UID = '200000002'
BITGET_STAMP = '2025-02-03 11:22:33.123'


# Entries are written with a fixed timestamp so that regenerating the fixtures byte-for-byte reproduces them -
# zipfile stamps the current time by default, which would make every run show up as a change to a committed file.
FIXED_TIME = (2025, 1, 1, 0, 0, 0)


def add(archive, name, content):
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, content)


def csv_text(header, rows):
    """CSV with the BOM and CRLF endings both exchanges write."""
    lines = [','.join(header)] + [','.join(str(x) for x in row) for row in rows]
    return BOM + '\r\n'.join(lines) + '\r\n'


# ----------------------------------------------------------------------------------------------------------------------
# KuCoin: 18 files, 10 of them empty and carrying the "No matching records found." sentinel.
KUCOIN_LEDGER_HEADER = ['UID', 'Account Type', 'Currency', 'Side', 'Amount', 'Fee', 'Time(UTC)', 'Remark', 'Type']

FUNDING = [
    # fiat in: the ledger credits 999 net while the fiat file names the gross 1000 and the 1 fee
    [KUCOIN_UID, 'mainAccount', 'EUR', 'Deposit', '999', '1', '2025-01-10 10:00:00', 'card', 'Fiat Deposit'],
    [KUCOIN_UID, 'mainAccount', 'EUR', 'Withdrawal', '999', '0', '2025-01-10 10:05:00', 'Trading Account', 'Transfer'],
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Deposit', '500', '0', '2025-01-11 13:00:00', 'Trading Account', 'Transfer'],
    # coins out: the debit is gross of the 0.5 fee, so 100 actually travelled
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Withdrawal', '100.5', '0.5', '2025-01-12 12:00:30', 'to wallet', 'Withdraw'],
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Deposit', '50', '0', '2025-01-13 09:00:20', 'Deposit', 'Deposit'],
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Deposit', '0.5', '0', '2025-01-14 07:00:00', '', 'Hold to Earn Earnings'],
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Deposit', '2', '0', '2025-01-14 08:00:00', 'KuCoin-Activity', 'Referral Bonus'],
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Deposit', '10', '0', '2025-01-14 09:00:00', '', 'PLATFORM_REWARD_WITHDRAW'],
]

TRADING = [
    [KUCOIN_UID, 'mainAccount', 'EUR', 'Deposit', '999', '0', '2025-01-10 10:05:00', 'Funding Account', 'Transfer'],
    # buy 1000 USDT @ 0.9: EUR debit is the 900 volume plus the 0.9 fee
    [KUCOIN_UID, 'mainAccount', 'EUR', 'Withdrawal', '900.9', '0.9', '2025-01-10 10:10:00', '', 'Spot'],
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Deposit', '1000', '0', '2025-01-10 10:10:00', '', 'Spot'],
    # sell 200 USDT @ 0.95: EUR credit is the 190 volume less the 0.19 fee
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Withdrawal', '200', '0', '2025-01-11 11:00:00', '', 'Spot'],
    [KUCOIN_UID, 'mainAccount', 'EUR', 'Deposit', '189.81', '0.19', '2025-01-11 11:00:00', '', 'Spot'],
    # buy 500 ADA for 200 USDT, fee 0.2 USDT, of which 0.04 comes back as a coupon refund a second later
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Withdrawal', '200.2', '0.2', '2025-01-11 12:00:00', '', 'Spot'],
    [KUCOIN_UID, 'mainAccount', 'ADA', 'Deposit', '500', '0', '2025-01-11 12:00:00', '', 'Spot'],
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Deposit', '0.04', '0', '2025-01-11 12:00:01', 'KuCoin-Activity',
     'Deduction Coupon Refund'],
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Withdrawal', '500', '0', '2025-01-11 13:00:00', 'Funding Account', 'Transfer'],
    # locked into Earn and never redeemed within this statement, so the closing snapshot is short by 50 USDT
    [KUCOIN_UID, 'mainAccount', 'USDT', 'Withdrawal', '50', '0', '2025-01-15 10:00:00', 'USDT ACTIVITY',
     'KuCoin Earn Locked'],
]

FILLS_HEADER = ['UID', 'Account Type', 'Order ID', 'Symbol', 'Side', 'Order Type', 'Avg. Filled Price',
                'Filled Amount', 'Filled Volume', 'Filled Volume (USDT)', 'Filled Time(UTC)', 'Fee', 'Tax',
                'Maker/Taker', 'Fee Currency', 'Account Mode']
FILLS = [
    [KUCOIN_UID, 'mainAccount', 'ORD-1', 'USDT-EUR', 'BUY', 'LIMIT', '0.9', '1000', '900', '1000',
     '2025-01-10 10:10:00', '0.9', '', 'TAKER', 'EUR', 'CLASSIC'],
    [KUCOIN_UID, 'mainAccount', 'ORD-2', 'USDT-EUR', 'SELL', 'LIMIT', '0.95', '200', '190', '200',
     '2025-01-11 11:00:00', '0.19', '', 'MAKER', 'EUR', 'CLASSIC'],
    [KUCOIN_UID, 'mainAccount', 'ORD-3', 'ADA-USDT', 'BUY', 'LIMIT', '0.4', '500', '200', '200',
     '2025-01-11 12:00:00', '0.2', '', 'TAKER', 'USDT', 'CLASSIC'],
]

SNAPSHOT_HEADER = ['UID', 'Account Type', 'Account Name', 'Coin', 'Amount', 'Amount(USDT)', 'Time(UTC)']
SNAPSHOTS = [
    [KUCOIN_UID, 'mainAccount', 'Main Account', 'EUR', '0', '0', '2025-01-10 23:59:59'],
    [KUCOIN_UID, 'mainAccount', 'HF Trading Account', 'EUR', '98.1', '109', '2025-01-10 23:59:59'],
    [KUCOIN_UID, 'mainAccount', 'HF Trading Account', 'USDT', '1000', '1000', '2025-01-10 23:59:59'],
    # closing day: 462 + 49.84 USDT on the books, the 50 in Earn deliberately absent
    [KUCOIN_UID, 'mainAccount', 'Main Account', 'EUR', '0', '0', '2025-01-15 23:59:59'],
    [KUCOIN_UID, 'mainAccount', 'Main Account', 'USDT', '462', '462', '2025-01-15 23:59:59'],
    [KUCOIN_UID, 'mainAccount', 'HF Trading Account', 'EUR', '287.91', '319.9', '2025-01-15 23:59:59'],
    [KUCOIN_UID, 'mainAccount', 'HF Trading Account', 'USDT', '49.84', '49.84', '2025-01-15 23:59:59'],
    [KUCOIN_UID, 'mainAccount', 'HF Trading Account', 'ADA', '500', '200', '2025-01-15 23:59:59'],
]

KUCOIN_EMPTY = {
    'Account History_Cross Margin Account.csv': KUCOIN_LEDGER_HEADER,
    'Account History_Isolated Margin Account.csv': KUCOIN_LEDGER_HEADER,
    'Convert Orders_Filled Orders.csv': ['UID', 'Order ID', 'Sell', 'Buy', 'Price', 'Time(UTC)', 'Status'],
    'Earn Orders_Staking History.csv': ['UID', 'Product', 'Coin', 'Amount', 'Time(UTC)', 'Status'],
    'Earn Orders_Profit History.csv': ['UID', 'Product', 'Coin', 'Profit', 'Time(UTC)'],
    'Fiat Orders_Fiat Withdrawals.csv': ['Order ID', 'Currency (Fiat)', 'Fiat Amount', 'Fee', 'Status', 'Time(UTC)'],
    'Fiat Orders_Fast Trade Orders.csv': ['Order ID', 'Pay Amount', 'Receive Amount', 'Status', 'Time(UTC)'],
    'Fiat Orders_P2P Orders.csv': ['Order ID', 'Coin', 'Amount', 'Counterparty', 'Status', 'Time(UTC)'],
    'Fiat Orders_Third-Party Payment.csv': ['Order ID', 'Currency', 'Amount', 'Provider', 'Status', 'Time(UTC)'],
    'Others_VIP Lending.csv': ['UID', 'Coin', 'Amount', 'Interest', 'Time(UTC)', 'Status'],
    # the order-level trade file: redundant with the fill-level one and deliberately left without data
    'Spot Orders_Filled Orders.csv': ['UID', 'Order ID', 'Symbol', 'Side', 'Filled Amount', 'Filled Volume',
                                      'Filled Time(UTC)', 'Fee', 'Fee Currency'],
}


def build_kucoin(path):
    files = {
        'Account History_Funding Account.csv': csv_text(KUCOIN_LEDGER_HEADER, FUNDING),
        'Account History_Trading Account.csv': csv_text(KUCOIN_LEDGER_HEADER, TRADING),
        'Spot Orders_Filled Orders (Show Order-Splitting).csv': csv_text(FILLS_HEADER, FILLS),
        'Others_Asset Snapshots.csv': csv_text(SNAPSHOT_HEADER, SNAPSHOTS),
        'Deposit_Withdrawal History_Deposit History.csv': csv_text(
            ['UID', 'Account Type', 'Time(UTC)', 'Coin', 'Amount', 'Fee', 'Hash', 'Deposit Address',
             'Transfer Network', 'Status', 'Remarks'],
            [[KUCOIN_UID, 'mainAccount', '2025-01-13 09:00:00', 'USDT', '50', '0',
              '0x' + 'a1' * 32, '0x' + '11' * 20, 'ETH', 'SUCCESS', 'Deposit']]),
        'Deposit_Withdrawal History_Withdrawal History.csv': csv_text(
            ['UID', 'Account Type', 'Time(UTC)', 'Coin', 'Amount', 'Fee', 'Hash', 'Withdrawal Address/Account',
             'Transfer Network', 'Status', 'Remarks'],
            [[KUCOIN_UID, 'mainAccount', '2025-01-12 12:00:00', 'USDT', '100', '0.5',
              '0x' + 'b2' * 32, '0x' + '22' * 20, 'ARBITRUM', 'SUCCESS', 'to wallet']]),
        'Fiat Orders_Fiat Deposits.csv': csv_text(
            ['Order ID', 'Currency (Fiat)', 'Fiat Amount', 'Fee', 'Deposit Method', 'Status', 'Time(UTC)'],
            [['FIAT-1', 'EUR', '1000', '1', 'card', 'SUCCEEDED', '2025-01-10 09:59:58']]),
    }
    for name, header in KUCOIN_EMPTY.items():
        files[name] = BOM + ','.join(header) + '\r\nNo matching records found.\r\n'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            add(archive, name, files[name])


# ----------------------------------------------------------------------------------------------------------------------
# Bitget: names carry the UID and the export moment (with ':' in them), one entry has a '/' in its name, the Earn
# labels use an en-dash, ids are TAB-prefixed and the fill rows end with a stray comma.
BITGET_EARN = [
    'Earn–Simple Earn Flexible–subscription', 'Earn–Simple Earn Flexible–redemption', 'Earn–Simple Earn Flexible–profit',
    'Earn–Simple Earn Fixed–subscription', 'Earn–Simple Earn Fixed–redemption', 'Earn–Simple Earn Fixed–profit',
    'Earn–Simple Earn Fixed–penalty interest', 'Earn–On-chain Earn–staking', 'Earn–On-chain Earn–profit',
    'Earn–On-chain Earn–standard redemption', 'Earn–On-chain Earn–express redemption',
    'Earn–Dual Investment–subscription', 'Earn–Dual Investment–settlement', 'Earn–Dual Investment–profit',
    'Earn–Shark Fin–subscription', 'Earn–Shark Fin–settlement', 'Earn–Shark Fin–profit',
]
BITGET_FUTURES = ['USDT-M Futures', 'Coin-M Futures', 'USDC-M Futures']


def bitget_name(label, exported=False):
    return f"{'Exported' if exported else 'Export'} {label} {BITGET_UID}-{BITGET_STAMP}.csv"


def build_bitget(path):
    files = {}
    # the ledger, carrying its own running balance in 'Available'
    files[bitget_name('spot transactions')] = csv_text(
        ['order', 'Date', 'Coin', 'Type', 'Amount', 'Fee', 'Available'],
        [['\t9000000000000000010', '2025-02-01 09:00:00', 'EUR', 'Deposit', '500', '0', '500'],
         ['\t9000000000000000011', '2025-02-01 10:00:00', 'USDT', 'Buy', '200', '-0.2', '199.8'],
         ['\t9000000000000000012', '2025-02-01 10:00:00', 'EUR', 'Sell', '-180', '0', '320'],
         ['\t9000000000000000013', '2025-02-02 10:00:00', 'USDT', 'Sell', '-100', '0', '99.8'],
         ['\t9000000000000000014', '2025-02-02 10:00:00', 'EUR', 'Buy', '94', '-0.094', '413.906'],
         ['\t9000000000000000015', '2025-02-02 12:00:00', 'USDT', 'Ordinary Withdrawal', '-99.5', '-0.3', '0'],
         ['\t9000000000000000016', '2025-02-03 08:00:00', 'USDT', 'Rebate rewards', '0.05', '0', '0.05']])
    # fills - note the trailing comma, which makes each row one field longer than the header
    fills_header = ['Date', 'Trading pair', 'Base Asset', 'Quote Asset', 'Direction', 'Price', 'Amount', 'Total',
                    'Fee', 'Fee Coin']
    fills = [['2025-02-01 10:00:00', 'USDT/EUR', 'USDT', 'EUR', 'Buy', '0.9', '200', '180', '0.2', 'USDT', ''],
             ['2025-02-02 10:00:00', 'USDT/EUR', 'USDT', 'EUR', 'Sell', '0.94', '100', '94', '0.094', 'EUR', '']]
    files[bitget_name('spot order details')] = csv_text(fills_header, fills)
    files[bitget_name('spot order history')] = csv_text(
        ['Date', 'Type', 'Order Id', 'Trading pair', 'Base Asset', 'Quote Asset', 'Direction', 'Price',
         'Order amount', 'Executed', 'Average Price', 'Trading volume', 'Status'],
        [['2025-02-01 10:00:00', 'GTC', '\t9000000000000000001', 'USDT/EUR', 'USDT', 'EUR', 'Buy', '0.9', '200',
          '200', '0.9', '180', 'fully executed'],
         ['2025-02-02 10:00:00', 'GTC', '\t9000000000000000002', 'USDT/EUR', 'USDT', 'EUR', 'Sell', '0.94', '100',
          '100', '0.94', '94', 'fully executed']])
    # the entry whose NAME contains a '/' - extracting this archive would turn it into a directory
    files[bitget_name('deposit/withdrawal records')] = csv_text(
        ['Date', 'Type', 'Funding account', 'Coin', 'Quantity', 'Address', 'TxID', 'Status'],
        [['2025-02-02 11:57:00', 'Withdraw', 'Spot account', 'USDT', '99.8', 'On-chain address',
          '0x' + 'c3' * 32, 'Successful']])
    # 36 empty files, header only and with no sentinel row of any kind
    empty = {
        'cross margin order history': ['Date', 'Order Id', 'Trading pair', 'Direction', 'Price', 'Status'],
        'cross margin transactions': ['Date', 'Coin', 'Type', 'Amount'],
        'isolated margin order history': ['Date', 'Order Id', 'Trading pair', 'Direction', 'Price', 'Status'],
        'isolated margin transactions': ['Date', 'Coin', 'Type', 'Amount'],
        'small balance conversion history': ['Date', 'Coin', 'Amount', 'Converted'],
        'Onchain history': ['Date', 'Type', 'Coin', 'Amount', 'Status'],
        'Onchain transactions': ['Date', 'Coin', 'Amount'],
    }
    for label, header in empty.items():
        files[bitget_name(label)] = BOM + ','.join(header) + '\r\n'
    for label in BITGET_EARN:
        files[bitget_name(label)] = BOM + ','.join(['Date', 'Coin', 'Amount']) + '\r\n'
    for product in BITGET_FUTURES:
        for suffix, header in (('order history', ['Date', 'Order Id', 'Symbol', 'Direction', 'Status']),
                               ('order details', ['Date', 'Symbol', 'Direction', 'Price', 'Amount']),
                               ('position history', ['Date', 'Symbol', 'Side', 'PnL']),
                               ('transactions', ['Date', 'Coin', 'Type', 'Amount'])):
            files[bitget_name(f'{product} {suffix}', exported=True)] = BOM + ','.join(header) + '\r\n'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            add(archive, name, files[name])
    return len(files)


if __name__ == '__main__':
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    build_kucoin(os.path.join(target, 'kucoin.zip'))
    count = build_bitget(os.path.join(target, 'bitget.zip'))
    print(f"kucoin.zip: 18 files, bitget.zip: {count} files -> {target}")
