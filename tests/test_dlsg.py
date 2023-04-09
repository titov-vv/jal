import os
import json
import filecmp
from jal.data_export.dlsg import DLSG
from tests.fixtures import project_root, data_path


def test_empty_dlsg(tmp_path, project_root, data_path):
    test_tax_files_empty = {
        2020: "3ndfl_2020_empty.dc0",
        2021: "3ndfl_2021_empty.dc1",
        2022: "3ndfl_2022_empty.dc2"
    }

    for year in test_tax_files_empty:
        tax_form = DLSG(year)
        assert tax_form._year == year

        # Validate saving of empty tax form file
        tax_form.save(str(tmp_path) + os.sep + test_tax_files_empty[year])
        assert filecmp.cmp(data_path + test_tax_files_empty[year], str(tmp_path) + os.sep + test_tax_files_empty[year])
        os.remove(str(tmp_path) + os.sep + test_tax_files_empty[year])


def test_full_dlsg(tmp_path, project_root, data_path):
    test_tax_files_full = {
        2020: "3ndfl_2020.dc0",
        2021: "3ndfl_2021.dc1",
        2022: "3ndfl_2022.dc2"
    }

    for year in test_tax_files_full:
        tax_form = DLSG(year)
        assert tax_form._year == year

        with open(data_path + 'taxes_rus.json', 'r', encoding='utf-8') as json_file:
            tax_report = json.load(json_file)
        tax_form.update_taxes(tax_report, {"currency": "USD", "broker_name": "IBKR", "broker_iso_country": "840"})

        # Validate saving of tax form file with data from tax report
        tax_form.save(str(tmp_path) + os.sep + test_tax_files_full[year])
        assert filecmp.cmp(data_path + test_tax_files_full[year], str(tmp_path) + os.sep + test_tax_files_full[year])
        os.remove(str(tmp_path) + os.sep + test_tax_files_full[year])
