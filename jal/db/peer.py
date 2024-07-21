from jal.db.db import JalDB
from jal.constants import PredefinedAgents


class JalPeer(JalDB):
    def __init__(self, id: int = 0, data: dict = None, search=False, create=False) -> None:
        super().__init__()
        self._id = id
        if self._valid_data(data):
            if search:
                self._id = self._find_peer(data)
            if create and not self._id:   # If we haven't found peer before and requested to create new record
                query = self._exec("INSERT INTO agents (pid, name) VALUES (:pid, :name)",
                                   [(":pid", data['parent']), (":name", data['name'])])
                self._id = query.lastInsertId()
        self._data = self._read("SELECT name FROM agents WHERE id=:peer_id",
                                [(":peer_id", self._id)], named=True)
        self._name = self._data['name'] if self._data is not None else None

    def dump(self):
        return self._data

    def id(self) -> int:
        return self._id

    def name(self) -> str:
        return self._name

    # Returns True if it is a predefined peer (that can't be removed)
    def is_predefined(self) -> bool:
        return self._id in PredefinedAgents()

    # Returns True if peer or its children are used in any transactions
    def is_in_use(self) -> bool:
        use_count = int(self._read("SELECT COUNT(oid) FROM actions WHERE peer_id=:peer_id", [(":peer_id", self._id)]))
        if use_count:
            return True
        for child_peer in self.get_child_peers():
            if child_peer.is_in_use():
                return True
        return False

    # Returns a list of JalPeers objects that represent child peers of the current peer
    def get_child_peers(self) -> list:   # FIXME - the code is similar to JalCategory.get_child_categories()
        children = []
        query = self._exec("SELECT id FROM agents WHERE pid=:peer_id", [(":peer_id", self._id)])
        while query.next():
            children.append(JalPeer(self._read_record(query)))
        return children

    # Returns a list of all available peers
    @classmethod
    def get_all_peers(cls):
        peers = []
        query = cls._exec("SELECT id FROM agents")
        while query.next():
            peers.append(JalPeer(cls._read_record(query, cast=[int])))
        return peers

    # Returns possible peer_id by a given name
    @classmethod
    def get_id_by_mapped_name(cls, name: str) -> int:
        return cls._read("SELECT mapped_to FROM map_peer WHERE value=:name", [(":name", name)])

    def add_or_update_mapped_name(self, name: str) -> None:
        _ = self._exec("INSERT OR REPLACE INTO map_peer (value, mapped_to) VALUES (:peer_name, :peer_id)",
                       [(":peer_name", name), (":peer_id", self._id)])

    def _valid_data(self, data: dict) -> bool:
        if data is None:
            return False
        if 'name' not in data:
            return False
        if 'parent' not in data:
            data['parent'] = 0
        return True

    def _find_peer(self, data: dict) -> int:
        peer_id = self._read("SELECT id FROM agents WHERE name=:name", [(":name", data['name'])])
        if peer_id is None:
            return 0
        else:
            return peer_id

    # returns number of operations that uses this Peer
    def number_of_documents(self) -> int:
        return self._read("SELECT COUNT(*) FROM (SELECT DISTINCT otype, oid FROM ledger WHERE peer_id=:id)",
                          [(":id", self._id)])

    # if old_name isn't empty then it is put in non-empty notes of action
    def replace_with(self, new_id, old_name=''):
        self._exec("UPDATE accounts SET organization_id=:new_id WHERE organization_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        if old_name:
            self._exec("UPDATE actions SET note=:old_name WHERE peer_id=:old_id AND coalesce(note, '')=''",
                       [(":old_id", self._id), (":old_name", old_name)])
        self._exec("UPDATE actions SET peer_id=:new_id WHERE peer_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("UPDATE map_peer SET mapped_to=:new_id WHERE mapped_to=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("DELETE FROM agents WHERE id=:old_id", [(":old_id", self._id)], commit=True)
        self._id = 0
