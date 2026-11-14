import re
from difflib import SequenceMatcher
from typing import Optional
from jal.db.db import JalDB

_QUANTITY_TAIL = re.compile(r'\s*\(\S+ x \S+\)$')     # ' (2 x 1.50)' that a receipt line's name ends with


# What a printed item is remembered by: its text without the quantity tail, letters and digits only, in one case
def item_key(printed: str) -> str:
    return ''.join(x for x in _QUANTITY_TAIL.sub('', printed).casefold() if x.isalnum())


#-----------------------------------------------------------------------------------------------------------------------
# What the user made of the items a shop prints on its receipts: the name, category and tag last stored for each
class JalReceiptMemory(JalDB):
    EXACT = "exact"
    GUESS = "guess"
    SIMILARITY = 0.85     # of the nearest remembered text for it to be offered as a guess

    def __init__(self, peer_id: int):
        super().__init__()
        self._peer_id = peer_id
        self._items = {}      # key -> {'printed', 'name', 'category_id', 'tag_id'}
        query = self._exec("SELECT printed, name, category_id, tag_id FROM receipt_items WHERE peer_id=:peer_id",
                           [(":peer_id", peer_id)])
        while query.next():
            item = self._read_record(query, named=True)
            self._items[item_key(item['printed'])] = item

    # Returns (remembered item, EXACT or GUESS) for a printed text, (None, '') if nothing like it is remembered
    def find(self, printed: str) -> tuple:
        key = item_key(printed)
        if not key:
            return None, ''
        if key in self._items:
            return self._items[key], self.EXACT
        nearest, similarity = None, self.SIMILARITY
        for known in self._items:
            ratio = SequenceMatcher(None, known, key).ratio()
            if ratio >= similarity:
                nearest, similarity = known, ratio
        return (self._items[nearest], self.GUESS) if nearest is not None else (None, '')

    # Stores what the item became; 'name' is empty for an item that kept its printed name
    def remember(self, printed: str, name: str, category_id: int, tag_id: Optional[int]):
        key = item_key(printed)
        if not key or not self._peer_id or not category_id:
            return
        known = self._items.get(key)
        if known is not None:
            self._exec("DELETE FROM receipt_items WHERE peer_id=:peer_id AND printed=:printed",
                       [(":peer_id", self._peer_id), (":printed", known['printed'])])
        printed = _QUANTITY_TAIL.sub('', printed)
        self._exec("INSERT INTO receipt_items (peer_id, printed, name, category_id, tag_id) "
                   "VALUES (:peer_id, :printed, :name, :category_id, :tag_id)",
                   [(":peer_id", self._peer_id), (":printed", printed), (":name", name),
                    (":category_id", category_id), (":tag_id", tag_id or None)], commit=True)
        self._items[key] = {'printed': printed, 'name': name, 'category_id': category_id, 'tag_id': tag_id or None}
