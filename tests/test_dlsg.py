import os
import filecmp
from jal.data_export.dlsg import DLSG
from tests.fixtures import project_root, data_path

test_tax_files = {
    2020: "3ndfl_2020_empty.dc0",
    2021: "3ndfl_2021_empty.dc1"
}


def test_dlsg(tmp_path, project_root, data_path):
    for year in test_tax_files:
        tax_form = DLSG(year)
        assert tax_form._year == year
        tax_form.save(str(tmp_path) + os.sep + test_tax_files[year])
        assert filecmp.cmp(data_path + test_tax_files[year], str(tmp_path) + os.sep + test_tax_files[year])
        os.remove(str(tmp_path) + os.sep + test_tax_files[year])
