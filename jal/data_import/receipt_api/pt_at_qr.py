import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


# ----------------------------------------------------------------------------------------------------------------------
# Portuguese fiscal QR code (Portaria n.º 195/2020): 'key:value' fields joined by '*', e.g. 'A:503340855*B:...*O:11.94'
class AtQr:
    MANDATORY = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I1', 'N', 'O', 'Q', 'R')
    PURCHASES = ('FT', 'FS', 'FR')     # invoice, simplified invoice, invoice-receipt
    RETURNS = ('NC',)                  # credit note
    NORMAL = 'N'                       # document status; 'A' is an annulled document
    _money = re.compile(r"^-?\d+\.\d{2}$")

    def __init__(self, fields: dict):
        self._fields = fields

    # Returns None if the text isn't a well-formed AT QR code
    @classmethod
    def parse(cls, raw: str) -> Optional['AtQr']:
        fields = {}
        for part in raw.split('*'):
            key, separator, value = part.partition(':')
            if not separator or key in fields:
                return None
            fields[key] = value
        if not all(x in fields for x in cls.MANDATORY):
            return None
        if not re.fullmatch(r"\d{9}", fields['A']) or not cls._money.match(fields['N']) \
                or not cls._money.match(fields['O']):
            return None
        try:
            datetime.strptime(fields['F'], "%Y%m%d")
        except ValueError:
            return None
        return cls(fields)

    def value(self, key: str) -> str:
        return self._fields.get(key, '')

    @property
    def nif(self) -> str:
        return self._fields['A']

    @property
    def doc_type(self) -> str:
        return self._fields['D']

    @property
    def status(self) -> str:
        return self._fields['E']

    @property
    def date(self) -> date:
        return datetime.strptime(self._fields['F'], "%Y%m%d").date()

    @property
    def doc_id(self) -> str:
        return self._fields['G']

    @property
    def atcud(self) -> str:
        return self._fields['H']

    @property
    def tax_total(self) -> Decimal:
        return Decimal(self._fields['N'])

    @property
    def total(self) -> Decimal:
        return Decimal(self._fields['O'])

    # Document identity for the duplicate check: the document id is unique per issuer only
    @property
    def number(self) -> str:
        return f"{self.nif}:{self.doc_id}"

    @property
    def is_return(self) -> bool:
        return self.doc_type in self.RETURNS
