import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import QLocale
from PySide6.QtGui import QIcon
from jal.constants import Setup


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
def delocalize_decimal(value: str, percent: bool = False) -> Decimal:
    number_text = value.replace(' ', '')
    number_text = number_text.replace(QLocale().groupSeparator(), '')
    number_text = number_text.replace(QLocale().decimalPoint(), '.')
    try:
        number = Decimal(number_text)
    except InvalidOperation:
        number = Decimal('0')
    if percent:
        number /= Decimal('100')
    return number


# -------------------------------------------------------------------------------------------------------------------
# Returns absolute path to a folder from where application was started
def get_app_path() -> str:
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + os.sep


# -------------------------------------------------------------------------------------------------------------------
def get_dbfilename(app_path):
    return app_path + Setup.DB_PATH

# -------------------------------------------------------------------------------------------------------------------
# Return a row from the model in form of {"field_name": value} dictionary
def db_row2dict(model, row) -> dict:
    record = model.record(row)
    return {record.field(x).name(): record.value(x) for x in range(record.count())}

# -------------------------------------------------------------------------------------------------------------------
# returns QIcon loaded from the file with icon_name located in folder Setup.ICONS_PATH
def load_icon(icon_name) -> QIcon:
    return QIcon(get_app_path() + Setup.ICONS_PATH + os.sep + icon_name)

# -------------------------------------------------------------------------------------------------------------------
# Returns timestamp of the first second of the year of given timestamp
def year_begin(timestamp: int) -> int:
    begin = datetime.utcfromtimestamp(timestamp).replace(month=1, day=1, hour=0, minute=0, second=0)
    return int(begin.replace(tzinfo=timezone.utc).timestamp())

# Returns timestamp of the last second of the year of given timestamp
def year_end(timestamp: int) -> int:
    end = datetime.utcfromtimestamp(timestamp).replace(month=1, day=1, hour=0, minute=0, second=0)
    end = end.replace(year=end.year + 1) - timedelta(seconds=1)
    return int(end.replace(tzinfo=timezone.utc).timestamp())

# -------------------------------------------------------------------------------------------------------------------