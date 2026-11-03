import json
import pytest
from PySide6.QtWidgets import QWidget

from tests.fixtures import project_root, data_path, prepare_db
from jal.data_export.ru_ndfl3 import Ru_NDFL3
from jal.widgets.tax_widget import TaxMergeDialog


def _write(path, content) -> str:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False)
    return str(path)


def _merge(filenames):
    return Ru_NDFL3.merge_de5(filenames)


# Foreign income lines of every file are kept, counters follow them; any other key is taken from the fullest file
def test_de5_files_are_merged(prepare_db, tmp_path):
    first = _write(tmp_path / "a.de5", {
        "Person": {"Name": "", "INN": ""},
        "CurrencyIncomeList": [{"IncomeSource": "Broker A", "IncomeSum": 10.0}],
        "CurrencyQuantity": 1,
        "SourseInfoList": [{"Name": "A"}], "SourseInfoQuantity": 1
    })
    second = _write(tmp_path / "b.de5", {
        "Person": {"Name": "Ivanov", "INN": "123"},
        "CurrencyIncomeList": [{"IncomeSource": "Broker B", "IncomeSum": 20.0},
                               {"IncomeSource": "Broker B", "IncomeSum": 5.0}],
        "CurrencyQuantity": 2,
        "SourseInfoList": [{"Name": "B"}, {"Name": "C"}], "SourseInfoQuantity": 2
    })
    merged = _merge([first, second])
    assert [x['IncomeSum'] for x in merged['CurrencyIncomeList']] == [10.0, 20.0, 5.0]
    assert merged['CurrencyQuantity'] == 3
    assert merged['Person'] == {"Name": "Ivanov", "INN": "123"}
    assert merged['SourseInfoList'] == [{"Name": "B"}, {"Name": "C"}]
    assert merged['SourseInfoQuantity'] == 2


def test_de5_merge_refuses_what_it_cannot_read(prepare_db, tmp_path):
    broken = tmp_path / "broken.de5"
    broken.write_text("not json", encoding='utf-8')
    with pytest.raises(ValueError, match="broken.de5"):
        _merge([str(broken)])
    a_list = _write(tmp_path / "list.de5", [1, 2])
    with pytest.raises(ValueError, match="list.de5"):
        _merge([a_list])


# The dialog writes the merge of the files it lists into the file it names
def test_merge_dialog_writes_the_merged_file(prepare_db, tmp_path):
    first = _write(tmp_path / "a.de5", {"CurrencyIncomeList": [{"IncomeSum": 1.0}], "CurrencyQuantity": 1})
    second = _write(tmp_path / "b.de5", {"CurrencyIncomeList": [{"IncomeSum": 2.0}], "CurrencyQuantity": 1})
    parent = QWidget()
    dialog = TaxMergeDialog(parent)
    dialog.ui.InputFilesList.addItems([first, second])
    dialog.ui.OutputFileName.setText(str(tmp_path / "merged.de5"))
    dialog.accept()
    with open(tmp_path / "merged.de5", 'r', encoding='utf-8') as f:
        merged = json.load(f)
    assert merged['CurrencyQuantity'] == 2
