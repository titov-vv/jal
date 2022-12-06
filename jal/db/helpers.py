import os
import logging
from PySide6.QtCore import QLocale
from PySide6.QtSql import QSqlDatabase, QSqlQuery
from PySide6.QtGui import QIcon
from jal.constants import Setup
from decimal import Decimal


# FIXME all database calls should be via JalDB (or mate) class. Get rid of SQL calls from other code

# -------------------------------------------------------------------------------------------------------------------
# Return "canonical" string for decimal number
def format_decimal(d) -> str:
    return str(d.normalize())


# Removes exponent and trailing zeros from Decimal number
def remove_exponent(d) -> Decimal:
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


# Make a locale-specific string from a Decimal value rounded to 'precision' digits after decimal point
# Multiplies value by 100 if 'percent' is True
def localize_decimal(value: Decimal, precision: int = None, percent: bool = False) -> str:
    if percent:
        value *= 100
    try:
        precision = int(precision)
    except (ValueError, TypeError):
        precision = -remove_exponent(value).as_tuple().exponent
    rounded = round(remove_exponent(value), precision)
    digits = [digit for digit in str(rounded)]    # Represent string as list for easier insertions/replacements
    if precision > 0:
        digits[-precision - 1] = QLocale().decimalPoint()  # Replace decimal point with locale-specific value
        integer_part_size = len(digits) - precision - 1
    else:
        integer_part_size = len(digits)  # No decimal point is present in number
    if QLocale().groupSeparator():
        for i in range(3, integer_part_size, 3):           # Insert locale-specific thousand separator at each 3rd digit
            digits.insert(integer_part_size - i, QLocale().groupSeparator())
    formatted_number = ''.join(digits)
    return formatted_number


# Make number not locale-specific - i.e. replace decimal separator with '.' and remove any thousand separators
# Divide value by 100 if 'percent' is True
def delocalize_decimal(value: str, percent: bool = False) -> str:
    number_text = value.replace(' ', '')
    number_text = number_text.replace(QLocale().groupSeparator(), '')
    number_text = number_text.replace(QLocale().decimalPoint(), '.')
    number = Decimal(number_text) if number_text else Decimal('0')
    if percent:
        number /= Decimal('100')
    return str(number)


# -------------------------------------------------------------------------------------------------------------------
# Returns absolute path to a folder from where application was started
def get_app_path() -> str:
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + os.sep


# -------------------------------------------------------------------------------------------------------------------
def get_dbfilename(app_path):
    return app_path + Setup.DB_PATH


# -------------------------------------------------------------------------------------------------------------------
# returns QIcon loaded from the file with icon_name located in folder Setup.ICONS_PATH
def load_icon(icon_name) -> QIcon:
    return QIcon(get_app_path() + Setup.ICONS_PATH + os.sep + icon_name)


# -------------------------------------------------------------------------------------------------------------------
# This function returns SQLite connection used by JAL or fails with RuntimeError exception
def _db_connection():
    db = QSqlDatabase.database(Setup.DB_CONNECTION)
    if not db.isValid():
        raise RuntimeError(f"DB connection '{Setup.DB_CONNECTION}' is invalid")
    if not db.isOpen():
        logging.fatal(f"DB connection '{Setup.DB_CONNECTION}' is not open")
    return db


def readSQLrecord(query, named=False):
    if named:
        values = {}
    else:
        values = []
    for i in range(query.record().count()):
        if named:
            values[query.record().fieldName(i)] = query.value(i)
        else:
            values.append(query.value(i))
    if values:
        if len(values) == 1 and not named:
            return values[0]
        else:
            return values
    else:
        return None
