import logging
from zipfile import ZipFile
import pandas

from jal.widgets.helpers import g_tr


# -----------------------------------------------------------------------------------------------------------------------
class UralsibCapital:
    def __init__(self, parent, filename):
        self._parent = parent
        self._filename = filename

    def load(self):
        with ZipFile(self._filename) as zip_file:
            contents = zip_file.namelist()
            if len(contents) != 1:
                logging.info(g_tr('Uralsib', "Archive contains multiple files, only one is expected for import"))
                return False
            with zip_file.open(contents[0]) as r_file:
                report = pandas.read_excel(io=r_file.read(), header=None, na_filter=False)
        print(report)
