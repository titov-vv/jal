BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
UPDATE transfers SET deposit='0' WHERE asset IS NOT NULL;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=50 WHERE name='SchemaVersion';
INSERT OR REPLACE INTO settings(id, name, value) VALUES (7, 'RebuildDB', 1);
INSERT OR REPLACE INTO settings(id, name, value) VALUES (10, 'MessageOnce',
'{"en": "Database version was updated.\nAssets transfer handling was changed.\nSet a non-zero cost basis if you need to see a relevant open price for tranferred positions in another currency.",
  "ru": "Версия базы данных обновлена.\nОбработка переводов ЦБ была изменена.\nУкажите ненулевую стоимость позиции, если вы хотите видеть правильную цену покупки переведённых бумаг в другой валюте."}');
COMMIT;
-- Reduce file size
VACUUM;