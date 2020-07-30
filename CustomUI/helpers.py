from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from PySide2.QtWidgets import QAbstractItemView, QHeaderView, QDataWidgetMapper, QFrame

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
    GROUP_NAME = 4

class map_idx:
    DB_NAME = 0
    WIDGET = 1
    WIDTH = 2
    VALIDATOR = 3


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


# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width, sort_order, delegate)
# column will be hidden if display_column_name is None
# column with negative with will be stretched
# sort order should be from Qt module (eg. Qt.AscendingOrder) or None
# delegate is a function for custom paint and editors
# relations - list of tuples that define lookup relations to other tables in database:
#             [(KEY_FEILD, LOOKUP_TABLE, FOREIGN_KEY, LOOKUP_FIELD), ...]
# mappings - list of tuples that define widgets linked to the fields in view:
#             [Field_name, MappedWidget, Width, Formatter]
def UseSqlTable(db, table_name, columns, relations):
    if relations:
        model = QSqlRelationalTableModel(db=db)
    else:
        model = QSqlTableModel(db=db)
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
            model.setHeaderData(model.fieldIndex(column[hcol_idx.DB_NAME]), Qt.Horizontal, column[hcol_idx.DISPLAY_NAME])
        if column[hcol_idx.SORT_ORDER] is not None:
            model.setSort(model.fieldIndex(column[hcol_idx.DB_NAME]), column[hcol_idx.SORT_ORDER])
    return model

# Use mappings to link between DB fields and GUI widgets with help of delegate
# mapping is a list of tuples [(FIELD_NAME, GUI_WIDGET, WIDTH, VALIDATOR)]
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
        # if no USER property we should use QByteArray().setRawData("account_id", 10)) here
        mapper.addMapping(mapping[map_idx.WIDGET], model.fieldIndex(mapping[map_idx.DB_NAME]))
        if mapping[map_idx.WIDTH]:
            mapping[map_idx.WIDGET].setFixedWidth(mapping[map_idx.WIDTH])
        if mapping[map_idx.VALIDATOR]:
            mapping[map_idx.WIDGET].setValidator(mapping[map_idx.VALIDATOR])
    return mapper

def ConfigureTableView(view, model, columns):
    view.setModel(model)
    for column in columns:
        if column[hcol_idx.DISPLAY_NAME] is None:   # hide column
            view.setColumnHidden(model.fieldIndex(column[hcol_idx.DB_NAME]), True)
        if column[hcol_idx.WIDTH] is not None:
            if column[hcol_idx.WIDTH] < 0:
                view.horizontalHeader().setSectionResizeMode(model.fieldIndex(column[hcol_idx.DB_NAME]), QHeaderView.Stretch)
            else:
                view.setColumnWidth(model.fieldIndex(column[hcol_idx.DB_NAME]), column[hcol_idx.WIDTH])

    view.setSelectionBehavior(QAbstractItemView.SelectRows)
    view.setSelectionMode(QAbstractItemView.SingleSelection)
    font = view.horizontalHeader().font()
    font.setBold(True)
    view.horizontalHeader().setFont(font)

    # Return value is a list of delegates because storage of delegates
    # is required to keep ownership and prevent SIGSEGV as
    # https://doc.qt.io/qt-5/qabstractitemview.html#setItemDelegateForColumn says:
    # Any existing column delegate for column will be removed, but not deleted.
    # QAbstractItemView does not take ownership of delegate.
    delegates = []
    for column in columns:
        if column[hcol_idx.DELEGATE] is not None:
            delegates.append(column[hcol_idx.DELEGATE](view))
            view.setItemDelegateForColumn(model.fieldIndex(column[hcol_idx.DB_NAME]), delegates[-1])
    return delegates
