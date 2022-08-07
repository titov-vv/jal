from jal.db.helpers import readSQL, executeSQL


class JalSettings:
    def __init__(self):
        pass

    def getValue(self, key, default=None):
        value = readSQL("SELECT value FROM settings WHERE name=:key", [(":key", key)])
        if value is None:
            value = default
        return value

    def setValue(self, key, value):
        executeSQL("INSERT OR REPLACE INTO settings(id, name, value) "
                   "VALUES((SELECT id FROM settings WHERE name=:key), :key, :value)",
                   [(":key", key), (":value", value)], commit=True)
