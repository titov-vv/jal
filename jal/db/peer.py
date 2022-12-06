from jal.db.db import JalDB


class JalPeer(JalDB):
    def __init__(self, id: int = 0, data: dict = None, search=False, create=False) -> None:
        super().__init__()
        self._id = id
        if self._valid_data(data):
            if search:
                self._id = self._find_peer(data)
            if create and not self._id:   # If we haven't found peer before and requested to create new record
                query = self.execSQL("INSERT INTO agents (pid, name) VALUES (:pid, :name)",
                                     [(":pid", data['parent']), (":name", data['name'])])
                self._id = query.lastInsertId()
        self._data = self.readSQL("SELECT name FROM agents WHERE id=:peer_id",
                                  [(":peer_id", self._id)], named=True)
        self._name = self._data['name'] if self._data is not None else None

    def id(self) -> int:
        return self._id

    def name(self) -> str:
        return self._name

    # Returns possible peer_id by a given name
    @staticmethod
    def get_id_by_mapped_name(name: str) -> int:
        return JalDB.readSQL("SELECT mapped_to FROM map_peer WHERE value=:name", [(":name", name)])

    @staticmethod
    def add_or_update_mapped_name(name: str, peer_id: int) -> None:  # TODO Review, should it be not static or not
        _ = JalDB.execSQL("INSERT OR REPLACE INTO map_peer (value, mapped_to) VALUES (:peer_name, :peer_id)",
                          [(":peer_name", name), (":peer_id", peer_id)])

    def _valid_data(self, data: dict) -> bool:
        if data is None:
            return False
        if 'name' not in data:
            return False
        if 'parent' not in data:
            data['parent'] = 0
        return True

    def _find_peer(self, data: dict) -> int:
        peer_id = self.readSQL("SELECT id FROM agents WHERE name=:name", [(":name", data['name'])])
        if peer_id is None:
            return 0
        else:
            return peer_id
