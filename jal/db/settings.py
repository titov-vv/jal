from jal.db.db import JalDB


class JalSettings(JalDB):
    def __init__(self):
        super().__init__()

    def getValue(self, key, default=None):
        value = self._readSQL("SELECT value FROM settings WHERE name=:key", [(":key", key)])
        if value is None:
            value = default
        return value

    def setValue(self, key, value):
        self._executeSQL("INSERT OR REPLACE INTO settings(id, name, value) "
                         "VALUES((SELECT id FROM settings WHERE name=:key), :key, :value)",
                         [(":key", key), (":value", value)], commit=True)
