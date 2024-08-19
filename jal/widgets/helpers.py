import logging
from datetime import time, datetime, timedelta, timezone
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from jal.constants import Setup
try:
    from pyzbar import pyzbar
except ImportError:
    pass  # Helpers that use this imports shouldn't be called if imports are absent

# -----------------------------------------------------------------------------------------------------------------------
# Returns True if all modules from module_list are present in the system
def dependency_present(module_list: list) -> bool:
    result = True
    for module in module_list:
        try:
            __import__(module)
        except ImportError:
            result = False
    return result

# -----------------------------------------------------------------------------------------------------------------------
# Check if given signal of an object is connected or not
def is_signal_connected(object, signal_name) -> bool:
    meta_object = object.metaObject()
    method_index = meta_object.indexOfSignal(signal_name)
    return object.isSignalConnected(meta_object.method(method_index))

# -----------------------------------------------------------------------------------------------------------------------
# center given window with respect to main application window
def center_window(window):
    main_window = None
    for widget in QApplication.topLevelWidgets():
        if widget.objectName() == Setup.MAIN_WND_NAME:
            main_window = widget
    if main_window:
        x = main_window.x() + main_window.width() / 2 - window.width() / 2
        y = main_window.y() + main_window.height() / 2 - window.height() / 2
        window.setGeometry(x, y, window.width(), window.height())

# -----------------------------------------------------------------------------------------------------------------------
# Returns true if text does contain only English alphabet
def is_english(text):
    try:
        text.encode(encoding='utf-8').decode(encoding='ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True

# -----------------------------------------------------------------------------------------------------------------------
# converts string with leading zeros to integer (like '03'->3, '00'->0, ''->0)
def str2int(value: str) -> int:
    value = value.lstrip('0')
    if value:
        return int(value)
    else:
        return 0

# -----------------------------------------------------------------------------------------------------------------------
# converts given unix-timestamp into string that represents date and time
def ts2dt(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%d/%m/%Y %H:%M:%S')

# -----------------------------------------------------------------------------------------------------------------------
# converts given unix-timestamp into string that represents date
def ts2d(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%d/%m/%Y')

# -----------------------------------------------------------------------------------------------------------------------
# converts given datetime value into unix-timestamp
def dt2ts(value: datetime) -> int:
    return int(value.replace(tzinfo=timezone.utc).timestamp())

# -----------------------------------------------------------------------------------------------------------------------
# returns unix timestamp for the first second of the month/year
def month_start_ts(year: int, month: int) -> int:
    start = datetime(year=year, month=month, day=1, hour=0, minute=0, second=0)
    return dt2ts(start)

# returns unix timestamp for the first second of the given week of the month
def week_start_ts(year: int, week: int) -> int:
    start = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")
    return dt2ts(start)

# -----------------------------------------------------------------------------------------------------------------------
# returns unix timestamp for the last second of the month/year
def month_end_ts(year: int, month: int) -> int:
    start = datetime(year=year, month=month, day=1, hour=0, minute=0, second=0)
    if month == 12:
        end = start.replace(year=year + 1, month=1)
    else:
        end = start.replace(month=month + 1)
    end = end - timedelta(seconds=1)
    return dt2ts(end)

# returns unix timestamp for the last second of the given week of the month
def week_end_ts(year: int, week: int) -> int:
    end = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w") + timedelta(days=7)
    return dt2ts(end)

# -----------------------------------------------------------------------------------------------------------------------
# returns an iterator that represents beginning of each day between start_ts unix-timestamp and end_ts unix-timestamp
def timestamp_range(start_ts, end_ts):
    start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    start_date = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
    end_date = datetime.fromtimestamp(end_ts, tz=timezone.utc)
    end_date = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
    for n in range(int((end_date - start_date).days)+1):
        day_n = start_date + timedelta(n)
        yield int(day_n.timestamp())

# -----------------------------------------------------------------------------------------------------------------------
# returns a list of dictionaries for each month between 'begin' and 'end' timestamps (including):
# { year, number, begin_ts, end_ts }
# where number is a month number from 1 to 12
def month_list(begin: int, end: int) -> list:
    result = []
    year_begin = int(datetime.fromtimestamp(begin, tz=timezone.utc).strftime('%Y'))
    month_begin = str2int(datetime.fromtimestamp(begin, tz=timezone.utc).strftime('%m'))
    year_end = int(datetime.fromtimestamp(end, tz=timezone.utc).strftime('%Y'))
    month_end = str2int(datetime.fromtimestamp(end, tz=timezone.utc).strftime('%m'))
    for year in range(year_begin, year_end+1):
        month1 = month_begin if year == year_begin else 1
        month2 = month_end + 1 if year == year_end else 13
        for month in range(month1, month2):
            result.append({'year': year, 'number': month,
                           'begin_ts': month_start_ts(year, month), 'end_ts': month_end_ts(year, month)})
    return result

# returns a list of dictionaries for each week between 'begin' and 'end' timestamps (including):
# { year, number, begin_ts, end_ts }
# where number is a week number in year from 1 to 53
def week_list(begin: int, end: int) -> list:
    result = []
    year_begin = int(datetime.fromtimestamp(begin, tz=timezone.utc).strftime('%Y'))
    week_begin = str2int(datetime.fromtimestamp(begin, tz=timezone.utc).strftime('%W'))
    if week_begin == 0:
        year_begin -= 1
        week_begin = 53
    year_end = int(datetime.fromtimestamp(end, tz=timezone.utc).strftime('%Y'))
    week_end = int(datetime.fromtimestamp(end, tz=timezone.utc).strftime('%W'))
    if week_end == 0:
        year_end -= 1
        week_end = 53
    for year in range(year_begin, year_end + 1):
        wk1 = week_begin if year == year_begin else 1
        wk2 = week_end + 1 if year == year_end else 54
        for week in range(wk1, wk2):
            result.append({'year': year, 'number': week,
                           'begin_ts': week_start_ts(year, week), 'end_ts': week_end_ts(year, week)})
    return result

# ----------------------------------------------------------------------------------------------------------------------
# Function takes an image and searches for QR in it. Content of first found QR is returned. Otherwise - empty string.
def decodeQR(qr_image: QImage, code_type=None) -> str:
    if qr_image.isNull():
        return ''
    if not dependency_present(['pyzbar']):
        logging.warning("Package pyzbar not found for QR recognition.")
        return ''
    if code_type is None:
        code_type = pyzbar.ZBarSymbol.QRCODE
    qr_image.convertTo(QImage.Format_Grayscale8)
    # bytesPerXXX is more accurate than width and height
    data = (qr_image.bits().tobytes(), qr_image.bytesPerLine(), int(qr_image.sizeInBytes()/qr_image.bytesPerLine()))
    barcodes = pyzbar.decode(data, symbols=[code_type])
    if barcodes:
        return barcodes[0].data.decode('utf-8')
    return ''


# -----------------------------------------------------------------------------------------------------------------------
# Helpers to work with datetime
class ManipulateDate:
    @staticmethod
    def toTimestamp(date_value):
        time_value = time(0, 0, 0)
        dt_value = datetime.combine(date_value, time_value)
        return int(dt_value.replace(tzinfo=timezone.utc).timestamp())

    @staticmethod
    def PreviousWeek(day=datetime.today()):
        end = day + timedelta(days=1)
        prev_week = day - timedelta(days=7)
        start_of_week = prev_week - timedelta(days=prev_week.weekday())
        return ManipulateDate.toTimestamp(start_of_week), ManipulateDate.toTimestamp(end)

    @staticmethod
    def PreviousMonth(day=datetime.today()):
        end = day + timedelta(days=1)
        first_day_of_month = day.replace(day=1)
        last_day_of_prev_month = first_day_of_month - timedelta(days=1)
        first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_month), ManipulateDate.toTimestamp(end)

    @staticmethod
    def PreviousQuarter(day=datetime.today()):
        end = day + timedelta(days=1)
        prev_quarter_month = day.month - day.month % 3 - 3
        if prev_quarter_month > 0:
            quarter_back = day.replace(day=1, month=prev_quarter_month)
        else:
            quarter_back = day.replace(day=1, month=(prev_quarter_month + 12), year=(day.year - 1))
        return ManipulateDate.toTimestamp(quarter_back), ManipulateDate.toTimestamp(end)

    @staticmethod
    def PreviousYear(day=datetime.today()):
        end = day + timedelta(days=1)
        first_day_of_year = day.replace(day=1, month=1)
        last_day_of_prev_year = first_day_of_year - timedelta(days=1)
        first_day_of_prev_year = last_day_of_prev_year.replace(day=1, month=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_year), ManipulateDate.toTimestamp(end)

    @staticmethod
    def QuarterToDate(day=datetime.today()):
        end = day + timedelta(days=1)
        begin_month = day.month - 3
        if begin_month > 0:
            begin = day.replace(day=1, month=begin_month)
        else:
            begin = day.replace(day=1, month=(begin_month + 12), year=(day.year - 1))
        return ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end)

    @staticmethod
    def YearToDate(day=datetime.today()):
        end = day + timedelta(days=1)
        begin = day.replace(day=1, year=(day.year - 1))
        return ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end)

    @staticmethod
    def ThisYear(day=datetime.today()):
        end = day + timedelta(days=1)
        begin = day.replace(day=1, month=1)
        return ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end)

    @staticmethod
    def LastYear(day=datetime.today()):
        end = day.replace(day=1, month=1)
        begin = end.replace(year=(day.year - 1))
        return ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end)

    @staticmethod
    def AllDates(day=datetime.today()):
        end = day + timedelta(days=1)
        return 0, ManipulateDate.toTimestamp(end)
