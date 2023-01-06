from jal.db.db import JalDB


class JalSettings(JalDB):
    def __init__(self):
        super().__init__()

    def getValue(self, key, default=None):
        value = self._read("SELECT value FROM settings WHERE name=:key", [(":key", key)])
        if value is None:
            value = default
        return value

    def setValue(self, key, value):
        self._exec("INSERT OR REPLACE INTO settings(id, name, value) "
                   "VALUES((SELECT id FROM settings WHERE name=:key), :key, :value)",
                   [(":key", key), (":value", value)], commit=True)

    # Returns 2-letter language code that corresponds to current 'Language' settings in DB
    def getLanguage(self):
        lang_id = self.getValue('Language', default=1)
        return self._read("SELECT language FROM languages WHERE id = :language_id", [(':language_id', lang_id)])

    # Set 'Language' setting in DB that corresponds to given 2-letter language code
    def setLanguage(self, language_code):
        lang_id = self._read("SELECT id FROM languages WHERE language = :language_code",
                             [(':language_code', language_code)])
        self.setValue('Language', lang_id)
