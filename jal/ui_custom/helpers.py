import datetime

from jal.constants import ColumnWidth
from PySide2.QtCore import QCoreApplication, Qt, QStringListModel, QByteArray
from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from PySide2.QtWidgets import QHeaderView, QDataWidgetMapper, QFrame, QDateTimeEdit

class hcol_idx:
    DB_NAME = 0
    DISPLAY_NAME = 1
    WIDTH = 2
    SORT_ORDER = 3
    DELEGATE = 4

class rel_idx:
    KEY_FIELD = 0
    LOOKUP_TABLE = 1
    FOREIGN_KEY = 2
    LOOKUP_FIELD = 3
    GROUP_NAME = 4          # Name of group field if Reference Data dialog

class map_idx:
    DB_NAME = 0
    WIDGET = 1


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
# a simple VLine, like the one from Qt Designer to use in Status Bar for example
class VLine(QFrame):
    def __init__(self):
        super(VLine, self).__init__()
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)


# -----------------------------------------------------------------------------------------------------------------------
# Helpers to work with datetime
class ManipulateDate:
    @staticmethod
    def toTimestamp(date_value):
        time_value = datetime.time(0, 0, 0)
        dt_value = datetime.datetime.combine(date_value, time_value)
        return int(dt_value.timestamp())

    @staticmethod
    def startOfPreviousWeek():
        prev_week = datetime.date.today() - datetime.timedelta(days = 7)
        start_of_week = prev_week - datetime.timedelta(days = prev_week.weekday())
        return ManipulateDate.toTimestamp(start_of_week)

    @staticmethod
    def startOfPreviousMonth():
        day = datetime.date.today()
        first_day_of_month = day.replace(day=1)
        last_day_of_prev_month = first_day_of_month - datetime.timedelta(days=1)
        first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_month)

    @staticmethod
    def startOfPreviousQuarter():
        day = datetime.date.today()
        prev_quarter_month = day.month - day.month % 3 - 3
        if prev_quarter_month > 0:
            quarter_back = day.replace(month = prev_quarter_month)
        else:
            quarter_back = day.replace(month = (prev_quarter_month + 12), year = (day.year - 1))
        first_day_of_prev_quarter = quarter_back.replace(day=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_quarter)

    @staticmethod
    def startOfPreviousYear():
        day = datetime.date.today()
        first_day_of_year = day.replace(day=1, month=1)
        last_day_of_prev_year = first_day_of_year - datetime.timedelta(days=1)
        first_day_of_prev_year = last_day_of_prev_year.replace(day=1, month=1)
        return ManipulateDate.toTimestamp(first_day_of_prev_year)

    @staticmethod
    def Last3Months():
        day = datetime.date.today()
        end = day + datetime.timedelta(days=1)
        begin_month = day.month - 3
        if begin_month > 0:
            begin = day.replace(month=begin_month)
        else:
            begin = day.replace(month=(begin_month + 12), year=(day.year - 1))
        begin = begin.replace(day=1)
        return (ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end))

    @staticmethod
    def RangeYTD():
        day = datetime.date.today()
        end = day + datetime.timedelta(days=1)
        begin = day.replace(day=1, year=(day.year - 1))
        return (ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end))

    @staticmethod
    def RangeThisYear():
        day = datetime.date.today()
        end = day + datetime.timedelta(days=1)
        begin = day.replace(day=1, month=1)
        return (ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end))

    @staticmethod
    def RangePreviousYear():
        day = datetime.date.today()
        end = day.replace(day=1, month=1)
        begin = end.replace(year=(day.year - 1))
        return (ManipulateDate.toTimestamp(begin), ManipulateDate.toTimestamp(end))


# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width, sort_order, delegate)
# column will be hidden if display_column_name is None
# column with negative with will be stretched
# sort order should be from Qt module (eg. Qt.AscendingOrder) or None
# delegate is a function for custom paint and editors
# relations - list of tuples that define lookup relations to other tables in database:
#             [(KEY_FEILD, LOOKUP_TABLE, FOREIGN_KEY, LOOKUP_FIELD), ...]
# Returns QSqlTableModel/QSqlRelationalQueryModel
def UseSqlTable(parent, table_name, columns, relations):
    if relations:
        model = QSqlRelationalTableModel(parent=parent, db=parent.db)
    else:
        model = QSqlTableModel(parent=parent, db=parent.db)
    model.setTable(table_name)
    model.setEditStrategy(QSqlTableModel.OnManualSubmit)
    if relations:
        model.setJoinMode(QSqlRelationalTableModel.LeftJoin)  # to work correctly with NULL values in fields
        for relation in relations:
            model.setRelation(model.fieldIndex(relation[rel_idx.KEY_FIELD]),
                              QSqlRelation(relation[rel_idx.LOOKUP_TABLE],
                                           relation[rel_idx.FOREIGN_KEY], relation[rel_idx.LOOKUP_FIELD]))
    for column in columns:
        if column[hcol_idx.DISPLAY_NAME]:
            model.setHeaderData(model.fieldIndex(column[hcol_idx.DB_NAME]), Qt.Horizontal,
                                g_tr('TableViewConfig', column[hcol_idx.DISPLAY_NAME]))
        if column[hcol_idx.SORT_ORDER] is not None:
            model.setSort(model.fieldIndex(column[hcol_idx.DB_NAME]), column[hcol_idx.SORT_ORDER])
    return model

# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width, sort_order, delegate)
# column will be hidden if display_column_name is None
# column with negative with will be stretched
# sort order is ignored as it might be set by Query itself
# delegate is a function for custom paint and editors
# Returns : QSqlTableModel
def UseSqlQuery(parent, query, columns):
    model = QSqlTableModel(parent=parent, db=parent.db)
    model.setQuery(query)
    for column in columns:
        if column[hcol_idx.DISPLAY_NAME]:
            model.setHeaderData(model.fieldIndex(column[hcol_idx.DB_NAME]), Qt.Horizontal, column[hcol_idx.DISPLAY_NAME])
    return model

# -------------------------------------------------------------------------------------------------------------------
# Use mappings to link between DB fields and GUI widgets with help of delegate
# mapping is a list of tuples [(FIELD_NAME, GUI_WIDGET)]
# If widget is a custom one:
#    - initialize database connection for it
#    - connect "changed" signal to "submit" slot of QDataWidgetMapper (to reflect data changes in UI)
def ConfigureDataMappers(model, mappings, delegate):
    mapper = QDataWidgetMapper(model)
    mapper.setModel(model)
    mapper.setSubmitPolicy(QDataWidgetMapper.AutoSubmit)
    mapper.setItemDelegate(delegate(mapper))
    for mapping in mappings:
        if hasattr(mapping[map_idx.WIDGET], "isCustom"):
            mapping[map_idx.WIDGET].init_db(model.database())
            mapping[map_idx.WIDGET].changed.connect(mapper.submit)
        if mapping[map_idx.WIDGET].property("stringModelData") is not None:
            # Load lookup values from dynamic property into combo-box model
            comboModel = QStringListModel(mapping[map_idx.WIDGET].property("stringModelData").split(';'))
            mapping[map_idx.WIDGET].setModel(comboModel)
            mapper.addMapping(mapping[map_idx.WIDGET], model.fieldIndex(mapping[map_idx.DB_NAME]),
                              QByteArray().setRawData("currentIndex", 12))
        else:  # ComboBox has no USER property so we use QByteArray above, and simple mapping for others below
            mapper.addMapping(mapping[map_idx.WIDGET], model.fieldIndex(mapping[map_idx.DB_NAME]))
        # adjust width of QDateTimeEdits to show full date-time string
        if isinstance(mapping[map_idx.WIDGET], QDateTimeEdit):
            mapping[map_idx.WIDGET].setFixedWidth(
                mapping[map_idx.WIDGET].fontMetrics().width("00/00/0000 00:00:00") * 1.25)
    return mapper

# -------------------------------------------------------------------------------------------------------------------
# Return value is a list of delegates because storage of delegates
# is required to keep ownership and prevent SIGSEGV as
# https://doc.qt.io/qt-5/qabstractitemview.html#setItemDelegateForColumn says:
# Any existing column delegate for column will be removed, but not deleted.
# QAbstractItemView does not take ownership of delegate.
def ConfigureTableView(view, model, columns):
    view.setModel(model)
    for column in columns:
        if column[hcol_idx.DISPLAY_NAME] is None:   # hide column
            view.setColumnHidden(model.fieldIndex(column[hcol_idx.DB_NAME]), True)
        if column[hcol_idx.WIDTH] is not None:
            if column[hcol_idx.WIDTH] == ColumnWidth.STRETCH:
                view.horizontalHeader().setSectionResizeMode(model.fieldIndex(column[hcol_idx.DB_NAME]),
                                                             QHeaderView.Stretch)
            elif column[hcol_idx.WIDTH] == ColumnWidth.FOR_DATETIME:
                view.setColumnWidth(model.fieldIndex(column[hcol_idx.DB_NAME]),
                                    view.fontMetrics().width("00/00/0000 00:00:00") * 1.1)
            else:  # set custom width
                view.setColumnWidth(model.fieldIndex(column[hcol_idx.DB_NAME]), column[hcol_idx.WIDTH])

    font = view.horizontalHeader().font()
    font.setBold(True)
    view.horizontalHeader().setFont(font)

    delegates = []
    for column in columns:
        if column[hcol_idx.DELEGATE] is None:
            # Use standard delegate / Remove old delegate if there was any
            view.setItemDelegateForColumn(model.fieldIndex(column[hcol_idx.DB_NAME]), None)
        else:
            delegates.append(column[hcol_idx.DELEGATE](view))
            view.setItemDelegateForColumn(model.fieldIndex(column[hcol_idx.DB_NAME]), delegates[-1])
    return delegates
