from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from PySide6.QtCore import QLocale
from jal.constants import Setup, JalGlobals


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
    if type(value) != Decimal:
        try:
            value = Decimal(value)
        except:
            return f"* {value} *"  # Indicate failure
    if value.is_nan():
        return Setup.NULL_VALUE
    if percent:
        value *= Decimal('100')
    f_str = '{:'
    if sign:
        f_str += '+'
    f_str += ','
    if precision:
        f_str += f".{precision}"
    f_str += "f}"
    formatted_number = f_str.format(value)
    pos = formatted_number.find('.')
    if pos==0:
        formatted_number = '0' + formatted_number
        pos += 1
    if pos > 0:
        if precision is not None:
            formatted_number = formatted_number[:pos+precision+1]
        else:
            formatted_number = formatted_number.rstrip('0')
            formatted_number = formatted_number[:-1] if formatted_number[-1]=='.' else formatted_number
    formatted_number = formatted_number.replace(',', JalGlobals().number_group_separator).replace('.', JalGlobals().number_decimal_point)
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
# Return a row from the model in form of {"field_name": value} dictionary
def db_row2dict(model, row) -> dict:
    record = model.record(row)
    return {record.field(x).name(): record.value(x) for x in range(record.count())}

# -------------------------------------------------------------------------------------------------------------------
# Returns timestamp of the first second of the year of given timestamp
def year_begin(timestamp: int) -> int:
    begin = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(month=1, day=1, hour=0, minute=0, second=0)
    return int(begin.replace(tzinfo=timezone.utc).timestamp())

# Returns timestamp of the last second of the year of given timestamp
def year_end(timestamp: int) -> int:
    end = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(month=1, day=1, hour=0, minute=0, second=0)
    end = end.replace(year=end.year + 1) - timedelta(seconds=1)
    return int(end.replace(tzinfo=timezone.utc).timestamp())

# Returns current timestamp
def now_ts() -> int:
    return int(datetime.now().replace(tzinfo=timezone.utc).timestamp())

# Returns timestamp of the first second of the day of given timestamp
def day_begin(timestamp: int) -> int:
    begin = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(hour=0, minute=0, second=0)
    return int(begin.replace(tzinfo=timezone.utc).timestamp())

# Returns timestamp of the last second of the day of given timestamp
def day_end(timestamp: int) -> int:
    end = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(hour=23, minute=59, second=59)
    return int(end.replace(tzinfo=timezone.utc).timestamp())
# -------------------------------------------------------------------------------------------------------------------