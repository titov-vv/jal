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
# Returns empty string for None value
# Returns Setup.NULL_VALUE for NaN value
def localize_decimal(value: Decimal, precision: int = None, percent: bool = False, sign: bool = False) -> str:
    if value is None:
        return ''
    if value.is_nan():
        return Setup.NULL_VALUE
    if percent:
        value *= Decimal('100')
    value = remove_exponent(value)
    has_sign, digits, exponent = remove_exponent(value).as_tuple()
    try:
        precision = int(precision)
    except (ValueError, TypeError):
        precision = -exponent
    rounded = round(value, precision)
    digits = [digit for digit in str(rounded)]    # Represent string as list for easier insertions/replacements
    if 'E' in digits:
        if has_sign:
            digits[2] = QLocale().decimalPoint()
        else:
            digits[1] = QLocale().decimalPoint()
    else:
        if precision > 0:
            digits[-precision - 1] = QLocale().decimalPoint()  # Replace decimal point with locale-specific value
            integer_part_size = len(digits) - precision - 1
        else:
            integer_part_size = len(digits)  # No decimal point is present in number
        if QLocale().groupSeparator():
            for i in range(3, integer_part_size, 3):           # Insert locale-specific thousand separator at each 3rd digit
                digits.insert(integer_part_size - i, QLocale().groupSeparator())
    if sign and not has_sign:
        digits.insert(0, '+')
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
# Returns timestamp of the first second of the year of given timestamp
def year_begin(timestamp: int) -> int:
    begin = datetime.utcfromtimestamp(timestamp).replace(month=1, day=1, hour=0, minute=0, second=0)
    return int(begin.replace(tzinfo=timezone.utc).timestamp())

# Returns timestamp of the last second of the year of given timestamp
def year_end(timestamp: int) -> int:
    end = datetime.utcfromtimestamp(timestamp).replace(month=1, day=1, hour=0, minute=0, second=0)
    end = end.replace(year=end.year + 1) - timedelta(seconds=1)
    return int(end.replace(tzinfo=timezone.utc).timestamp())

# Returns current timestamp
def now_ts() -> int:
    return int(datetime.now().replace(tzinfo=timezone.utc).timestamp())

# -------------------------------------------------------------------------------------------------------------------