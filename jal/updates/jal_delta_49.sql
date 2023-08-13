BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
UPDATE transfers SET deposit=(deposit-fee), fee_account=NULL, fee=NULL WHERE id IN
(SELECT t.id FROM transfers t LEFT JOIN accounts fa ON fa.id = t.fee_account WHERE fa.organization_id IS NULL AND t.fee IS NOT NULL AND t.fee_account==t.deposit_account);
UPDATE transfers SET withdrawal=(withdrawal+fee), fee_account=NULL, fee=NULL WHERE id IN
(SELECT t.id FROM transfers t LEFT JOIN accounts fa ON fa.id = t.fee_account WHERE fa.organization_id IS NULL AND t.fee IS NOT NULL AND t.fee_account==t.withdrawal_account);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=49 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
INSERT OR REPLACE INTO settings(id, name, value) VALUES (10, 'MessageOnce',
'{"en": "Database version was updated.\nTransfers handling was changed - fee account should now have organization assigned.\nYou may assign it in the Data->Accounts menu if a related error will appear in the log.",
  "ru": "Версия базы данных обновлена.\nОбработка переводов была изменена - счёт комиссии теперь должен иметь организацию-владельца.\nВы можете указать её в меню Данные->Счета, если будут в логе будет ошибка об этом."}');
COMMIT;
-- Reduce file size
VACUUM;