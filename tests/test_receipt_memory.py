import sqlparse

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import PredefinedCategory
from jal.db.db import JalDB
from jal.db.peer import JalPeer
from jal.db.category import JalCategory
from jal.db.tag import JalTag
from jal.db.receipt_memory import JalReceiptMemory, item_key

FEES, TAXES = PredefinedCategory.Fees, PredefinedCategory.Taxes


def _rows() -> list:
    return JalDB._read_to_list("SELECT peer_id, printed, name, category_id, tag_id FROM receipt_items ORDER BY id")


def test_item_key_ignores_case_punctuation_and_the_quantity_tail():
    assert item_key("Pão de Leite, UND (2 x 0.45)") == item_key("PÃO DE LEITE UND") == "pãodeleiteund"
    assert item_key("LEITE (UHT)") == "leiteuht"            # not a quantity tail
    assert item_key(" - ") == ''


def test_item_is_found_exactly_then_by_the_nearest_text(prepare_db):
    memory = JalReceiptMemory(1)
    assert memory.find("LEITE MEIO GORDO") == (None, '')
    memory.remember("LEITE MEIO GORDO (2 x 0.89)", "milk", FEES, 1)
    memory.remember("LEITE MEIO GORDA", "", TAXES, None)
    assert [x[:4] for x in _rows()] == [[1, "LEITE MEIO GORDO", "milk", FEES], [1, "LEITE MEIO GORDA", "", TAXES]]
    memory = JalReceiptMemory(1)                             # read back from the database
    item, how = memory.find("leite meio-gordo")
    assert (item['name'], item['category_id'], item['tag_id'], how) == ("milk", FEES, 1, JalReceiptMemory.EXACT)
    item, how = memory.find("LEITE MEI0 GORDO")              # an OCR slip: the nearest of the two wins
    assert (item['name'], how) == ("milk", JalReceiptMemory.GUESS)
    assert memory.find("LEITE") == (None, '')                # too far from both
    assert memory.find("") == (None, '')


def test_item_stored_again_replaces_what_was_remembered(prepare_db):
    memory = JalReceiptMemory(1)
    memory.remember("LEITE", "milk", FEES, 1)
    memory.remember("Leite.", "", TAXES, None)               # the same item as another receipt printed it
    assert [x[:4] for x in _rows()] == [[1, "Leite.", "", TAXES]]
    memory.remember("PAO", "bread", 0, None)                 # nothing to remember without a category
    JalReceiptMemory(0).remember("PAO", "bread", FEES, None)     # ... or without a peer
    assert len(_rows()) == 1


def test_memory_follows_a_replaced_peer_category_and_tag(prepare_db):
    other = JalPeer(data={'name': "Other shop", 'parent': 0}, create=True).id()
    JalReceiptMemory(1).remember("LEITE", "milk", FEES, 1)
    JalReceiptMemory(other).remember("LEITE", "leite", TAXES, None)
    JalReceiptMemory(other).remember("PAO", "bread", TAXES, 1)
    JalPeer(other).replace_with(1)
    assert [x[:4] for x in _rows()] == [[1, "LEITE", "milk", FEES], [1, "PAO", "bread", TAXES]]
    JalCategory(TAXES).replace_with(FEES)
    new_tag = JalDB._exec("INSERT INTO tags (pid, tag) VALUES (0, 'New tag')", commit=True).lastInsertId()
    JalTag(1).replace_with(new_tag)
    assert [x[3:] for x in _rows()] == [[FEES, new_tag], [FEES, new_tag]]


# A schema-87 database has no table; the delta creates the same one jal_init.sql does
def test_delta_88_upgrade(prepare_db, project_root):
    def table_sql():     # columns, foreign keys and the unique index, as SQLite understood them
        return [JalDB._read_to_list(f"SELECT * FROM pragma_{x}('receipt_items')")
                for x in ("table_info", "foreign_key_list", "index_list")]
    table = table_sql()
    assert len(table[0]) == 6 and len(table[1]) == 3
    JalDB._exec("DROP TABLE receipt_items", commit=True)
    with open(project_root + "/jal/updates/jal_delta_88.sql", encoding='utf-8') as delta:
        text = delta.read()
    for statement in sqlparse.split(text[text.index("CREATE TABLE"):text.index("-- Set new DB schema version")]):
        if sqlparse.format(statement, strip_comments=True).strip():
            assert JalDB._exec(statement.strip(), commit=True) is not None
    assert table_sql() == table
