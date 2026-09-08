from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from PySide6.QtCore import QLocale
from jal.constants import Setup, JalGlobals


# -------------------------------------------------------------------------------------------------------------------
# Enough significant digits for any amount this application stores: a token with 18 decimals held in a balance of
# any realistic size stays well inside it. Only used to keep normalize() below from rounding.
DECIMAL_PRECISION = 60


# Return "canonical" string for decimal number.
# This is the single spelling of a Decimal in the database - every value bound to a query goes through it (see
# JalDB._exec), so the same number is always stored the same way and a string comparison of two amounts is
# meaningful. normalize() drops trailing zeros and puts round numbers in exponent form ('40' -> '4E+1'); both
# Decimal() and SQLite's CAST read that back correctly.
def format_decimal(d) -> str:
    # normalize() rounds to the precision of the active decimal context, 28 significant digits by default. That
    # silently truncates a high-precision amount - 12345678901234.123456789012345678 loses its last four digits -
    # so the context is widened here to keep the canonical form exact.
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
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


# Make a locale-specific string from an amount whose kind is not known in advance - a money sum and a quantity of a
# crypto asset may reach the same place (an account balance, a question about a transfer), and one fixed number of
# decimals cannot serve both: two digits turn 0.0004 BTC into '0.00', while the 18 decimals a token can carry are
# noise in every other case.
#
# So the amount is shown with the digits it actually has: never fewer than 'minimum' (a money sum keeps its familiar
# two) and never more than 'maximum'. Rounding to 'maximum' may still hide a genuinely tiny amount, and showing a
# non-zero amount as zero would be a lie - such a value is spelled out in full instead, however long it turns out.
def localize_amount(value: Decimal, minimum: int = Setup.DEFAULT_ACCOUNT_PRECISION,
                    maximum: int = Setup.MAX_AMOUNT_PRECISION) -> str:
    if value is None or type(value) != Decimal or value.is_nan():
        return localize_decimal(value)
    decimals = -remove_exponent(value).as_tuple().exponent   # trailing zeros don't count as digits worth showing
    decimals = min(max(decimals, minimum), maximum)
    if value != Decimal('0') and round(value, decimals) == Decimal('0'):
        return localize_decimal(value)          # too small to be shown rounded, and it is not nothing
    return localize_decimal(value, precision=decimals)


# Digits that spell the number of zeros of a compact amount, see localize_compact_amount()
SUBSCRIPT_DIGITS = "₀₁₂₃₄₅₆₇₈₉"


# Make a locale-specific string from an amount that is too small to be seen with 'precision' decimals: a gas fee of
# 0.00000021 ETH is not '0.00', while spelling it out in full makes a wall of zeros out of a column of money sums.
# The zeros that follow the decimal point are replaced by their count written in subscript - '0,0₆21' - the notation
# crypto wallets use, and 'digits' significant digits follow it. An amount that is visible with 'precision' decimals -
# every money sum among them - is left to localize_decimal() and looks exactly as it always did.
def localize_compact_amount(value: Decimal, precision: int = Setup.DEFAULT_ACCOUNT_PRECISION,
                            digits: int = 2, sign: bool = False) -> str:
    plain = localize_decimal(value, precision=precision, sign=sign)
    if type(value) != Decimal or value.is_nan() or value == Decimal('0'):
        return plain
    if any([char in '123456789' for char in plain]):   # it is visible with 'precision' decimals, whatever it rounds to
        return plain
    amount = abs(value)
    zeros = -amount.adjusted() - 1     # adjusted() is the power of ten of the first significant digit
    # Scaling by the zeros and the digits asked for puts exactly those digits before the decimal point
    significant = int(amount.scaleb(zeros + digits).to_integral_value(rounding=ROUND_HALF_UP))
    if significant >= 10 ** digits:    # rounding up carried into one more digit: 9.99E-7 is 0,0₅10 and not 0,0₆100
        zeros -= 1
        significant //= 10
    prefix = '-' if value < Decimal('0') else ('+' if sign else '')
    zeros_text = ''.join([SUBSCRIPT_DIGITS[int(digit)] for digit in str(zeros)])
    return prefix + '0' + JalGlobals().number_decimal_point + '0' + zeros_text + str(significant)


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

# The moment now, as JAL stores it: the instant itself, which is the same number on every clock. What the user's own
# clock reads at that instant is a question for jal/db/clock.py, which is where a timestamp meets a person.
def now_ts() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())

# The instant at which the wall clock of 'zone' showed the digits of 'moment' - what a source reports converted into
# what JAL stores. The offset in force at the moment itself is used, so it stays right across DST boundaries.
# A source that names no zone has its digits taken as UTC, which is what every importer did before any of them
# declared one and what leaves an undeclared source exactly where it was.
def wall_clock_timestamp(moment: datetime, zone: str = '') -> int:
    return int(moment.replace(tzinfo=ZoneInfo(zone) if zone else timezone.utc).timestamp())

# Returns timestamp of the first second of the day of given timestamp
def day_begin(timestamp: int) -> int:
    begin = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(hour=0, minute=0, second=0)
    return int(begin.replace(tzinfo=timezone.utc).timestamp())

# Returns timestamp of the last second of the day of given timestamp
def day_end(timestamp: int) -> int:
    end = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(hour=23, minute=59, second=59)
    return int(end.replace(tzinfo=timezone.utc).timestamp())

# A stored timestamp that states a DAY rather than a moment in it. JAL spells such a value as a fixed time of day, and
# the value is what says so - nothing is stored beside it. Currently, in use only 00:00:00.
# A marker is never re-read on another clock: it carries no time of day to convert, and converting it could only move
# it to a different day.
DAY_BEGIN_MARKER = 0
COMMON_DAY_MARKERS = (DAY_BEGIN_MARKER,)

def is_day_marker(timestamp: int, source_markers: tuple = ()) -> bool:
    return (timestamp - day_begin(timestamp)) in COMMON_DAY_MARKERS + tuple(source_markers)
# -------------------------------------------------------------------------------------------------------------------