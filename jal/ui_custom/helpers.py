from datetime import time, datetime, timedelta, timezone
from PySide2.QtCore import QCoreApplication, Qt


# -----------------------------------------------------------------------------------------------------------------------
# Global translate helper to make lines shorter in code
def g_tr(context, text):
    return QCoreApplication.translate(context, text)


# -----------------------------------------------------------------------------------------------------------------------
# Returns True if all modules from module_list are present in the system
def dependency_present(module_list):
    result = True
    for module in module_list:
        try:
            __import__(module)
        except ImportError:
            result = False
    return result


# -----------------------------------------------------------------------------------------------------------------------
# Helpers to work with numbers

def formatFloatLong(value):
    if abs(value - round(value)) <= 10e-2:
        text = f"{value:.0f}"
    elif abs(value - round(value, 2)) <= 10e-4:
        text = f"{value:.2f}"
    elif abs(value - round(value, 4)) <= 10e-6:
        text = f"{value:.4f}"
    elif abs(value - round(value, 6)) <= 10e-8:
        text = f"{value:.6f}"
    else:
        text = f"{value:.8f}"
    return text


# -----------------------------------------------------------------------------------------------------------------------
# Helpers to work with datetime
class ManipulateDate:
    @staticmethod
    def toTimestamp(date_value):
        time_value = time(0, 0, 0)
        dt_value = datetime.combine(date_value, time_value)
        return int(dt_value.replace(tzinfo=timezone.utc).timestamp())

    @staticmethod
    def startOfPreviousWeek(day=datetime.today()):
        prev_week = day - timedelta(days = 7)
        start_of_week = prev_week - timedelta(days = prev_week.weekday())
        return ManipulateDate.toTimestamp(start_of_week)

    @staticmethod
    def startOfPreviousMonth(day=datetime.today()):
        first_day_of_month = day.replace(day=1)
        last_day_of_prev_month = first_day_of_month - timedelta(days=1)
        first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_month)

    @staticmethod
    def startOfPreviousQuarter(day=datetime.today()):
        prev_quarter_month = day.month - day.month % 3 - 3
        if prev_quarter_month > 0:
            quarter_back = day.replace(month = prev_quarter_month)
        else:
            quarter_back = day.replace(month = (prev_quarter_month + 12), year = (day.year - 1))
        first_day_of_prev_quarter = quarter_back.replace(day=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_quarter)

    @staticmethod
    def startOfPreviousYear(day=datetime.today()):
        first_day_of_year = day.replace(day=1, month=1)
        last_day_of_prev_year = first_day_of_year - timedelta(days=1)
        first_day_of_prev_year = last_day_of_prev_year.replace(day=1, month=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_year)

    @staticmethod
    def Last3Months(day=datetime.today()):
        end = day + timedelta(days=1)
        begin_month = day.month - 3
        if begin_month > 0:
            begin = day.replace(month=begin_month)
        else:
            begin = day.replace(month=(begin_month + 12), year=(day.year - 1))
        begin = begin.replace(day=1)
        return (ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end))

    @staticmethod
    def RangeYTD(day=datetime.today()):
        end = day + timedelta(days=1)
        begin = day.replace(day=1, year=(day.year - 1))
        return (ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end))

    @staticmethod
    def RangeThisYear(day=datetime.today()):
        end = day + timedelta(days=1)
        begin = day.replace(day=1, month=1)
        return (ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end))

    @staticmethod
    def RangePreviousYear(day=datetime.today()):
        end = day.replace(day=1, month=1)
        begin = end.replace(year=(day.year - 1))
        return (ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end))


