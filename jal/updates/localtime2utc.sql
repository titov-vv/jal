-- Convert timestamps in DB from localtime values used previously to UTC
-- Example:
--select timestamp,
--datetime(timestamp, 'unixepoch') asUTC,
--datetime(timestamp,'unixepoch', 'localtime') asMSK,
--strftime('%s', datetime(timestamp,'unixepoch', 'localtime')) MSK2UTC,
--datetime(strftime('%s', datetime(timestamp,'unixepoch', 'localtime')) , 'unixepoch') MSK2UTCdecoded
--from trades

-- Accounts
UPDATE accounts SET reconciled_on = strftime('%s', datetime(reconciled_on, 'unixepoch', 'localtime'));
-- Actions
UPDATE actions SET timestamp = strftime('%s', datetime(timestamp, 'unixepoch', 'localtime'));
-- Corporate actions
UPDATE corp_actions SET timestamp = strftime('%s', datetime(timestamp,'unixepoch', 'localtime'));
-- Dividends
UPDATE dividends SET timestamp = strftime('%s', datetime(timestamp,'unixepoch', 'localtime'));
-- Quotes
UPDATE quotes SET timestamp = strftime('%s', datetime(timestamp,'unixepoch', 'localtime'));
-- Trades
UPDATE trades SET timestamp = strftime('%s', datetime(timestamp,'unixepoch', 'localtime'));
UPDATE trades SET settlement = strftime('%s', datetime(settlement,'unixepoch', 'localtime')) WHERE settlement != 0;
-- Transfers
UPDATE transfers SET timestamp = strftime('%s', datetime(timestamp,'unixepoch', 'localtime'));

