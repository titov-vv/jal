from jal.db.db import JalDB


class JalAccount(JalDB):
    def __init__(self, id=0):
        super().__init__()
        self._id = id
        self._data = self._readSQL("SELECT name, currency_id, organization_id, reconciled_on, precision "
                                   "FROM accounts WHERE id=:id", [(":id", self._id)], named=True)
        self._name = self._data['name'] if self._data is not None else None
        self._currency_id = self._data['currency_id'] if self._data is not None else None
        self._organization_id = self._data['organization_id'] if self._data is not None else None
        self._reconciled = int(self._data['reconciled_on']) if self._data is not None else 0
        self._precision = int(self._data['precision']) if self._data is not None else 2

    def id(self):
        return self._id

    def name(self):
        return self._name

    def currency(self):
        return self._currency_id

    def organization(self):
        return self._organization_id

    def reconciled_at(self):
        return self._reconciled

    def precision(self):
        return self._precision
