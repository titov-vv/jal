import json
import logging
from pkg_resources import parse_version
from jal.data_import.statement import FOF, Statement, Statement_ImportError

JAL_STATEMENT_CLASS = "StatementOpenPortfolio"


MANDATORY = 0
LOADER = 1
# -----------------------------------------------------------------------------------------------------------------------
class StatementOpenPortfolio(Statement):
    def __init__(self):
        super().__init__()
        self.name = self.tr("Investbook / IZI-Invest")
        self.icon_name = "open_portfolio.png"
        self.filename_filter = self.tr("Open portfolio (*.json)")

        self._sections = {
            "version": (True, self._validate_version),
            "start": (True, self._skip_section),
            "end": (True, self._get_period),
            "generated": (False, self._remove_section),
            "generated-by": (False, self._remove_section)
        }

    def load(self, filename: str) -> None:
        self._data = {}
        try:
            with open(filename, 'r', encoding='utf-8') as exchange_file:
                try:
                    self._data = json.load(exchange_file)
                except json.JSONDecodeError:
                    logging.error(self.tr("Failed to read JSON from file: ") + filename)
        except Exception as err:
            raise Statement_ImportError(self.tr("Failed to read file: ") + str(err))
        for section in self._sections:
            if section in self._data:
                self._sections[section][LOADER](section)
            else:
                if self._sections[section][MANDATORY]:
                    raise Statement_ImportError(self.tr("Mandatory section is missing: ") + str(section))

    def _skip_section(self, section):
        pass # do nothing

    def _remove_section(self, section):
        self._data.pop(section)

    def _validate_version(self, section):
        version = self._data[section]
        if parse_version(version) > parse_version("1.1.0"):
            raise Statement_ImportError(self.tr("Unsupported version of open portfolio format: ") + version)
        self._data.pop(section)

    def _get_period(self, _section):
        self._data[FOF.PERIOD] = [self._data["start"], self._data["end"]]
        self._data.pop("start")
        self._data.pop("end")
