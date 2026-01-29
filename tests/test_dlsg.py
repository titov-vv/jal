import os
import json
import filecmp
from jal.data_export.ru_ndfl3 import Ru_NDFL3
from tests.fixtures import project_root, data_path


def test_full_dlsg(tmp_path, project_root, data_path):
    year = 2025
    file_name = "ru_tax_test.json"
    tax_form = Ru_NDFL3(year)
    assert tax_form._year == year

    with open(data_path + 'taxes_rus.json', 'r', encoding='utf-8') as json_file:
        tax_report = json.load(json_file)
    tax_form.update_taxes(tax_report, {"currency": "USD", "broker_name": "IBKR", "broker_iso_country": "840"})

    # Validate saving of tax form file with data from tax report
    tax_form.save(str(tmp_path) + os.sep + file_name)
    assert filecmp.cmp(data_path + file_name, str(tmp_path) + os.sep + file_name)   # FIXME: Update with real file when available
    os.remove(str(tmp_path) + os.sep + file_name)
