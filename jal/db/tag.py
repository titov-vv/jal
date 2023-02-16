from jal.db.db import JalDB


class JalTag(JalDB):
    def __init__(self, id: int = 0):
        super().__init__()
        self._id = id

    def replace_with(self, new_id):
        self._exec("UPDATE action_details SET tag_id=:new_id WHERE tag_id=:old_id",
                   [(":new_id", new_id), (":old_id", self._id)])
        self._exec("DELETE FROM tags WHERE id=:old_id", [(":old_id", self._id)], commit=True)
        self._id = 0
