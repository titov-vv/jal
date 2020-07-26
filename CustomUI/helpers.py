from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation
from PySide2.QtWidgets import QAbstractItemView, QHeaderView

class hcol_idx:
    DB_NAME = 0
    DISPLAY_NAME = 1
    WIDTH = 2
    SORT_ORDER = 3
    DELEGATE = 4

class rel:
    KEY_FIELD = 0
    LOOKUP_TABLE = 1
    FOREIGN_KEY = 2
    LOOKUP_FIELD = 3
    GROUP_NAME = 4
# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width, sort_order, delegate)
# column will be hidden if display_column_name is None
# column with negative with will be stretched
# sort order should be from Qt module (eg. Qt.AscendingOrder) or None
# delegate is a function for custom paint and editors
# relations - list of tuples that define lookup relations to other tables in database:
#             [(KEY_FEILD, LOOKUP_TABLE, FOREIGN_KEY, LOOKUP_FIELD), ...]
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
            model.setRelation(model.fieldIndex(relation[rel.KEY_FIELD]),
                              QSqlRelation(relation[rel.LOOKUP_TABLE],
                                           relation[rel.FOREIGN_KEY], relation[rel.LOOKUP_FIELD]))
    for column in columns:
        if column[hcol_idx.DISPLAY_NAME]:
            model.setHeaderData(model.fieldIndex(column[hcol_idx.DB_NAME]), Qt.Horizontal, column[hcol_idx.DISPLAY_NAME])
        if column[hcol_idx.SORT_ORDER] is not None:
            model.setSort(model.fieldIndex(column[hcol_idx.DB_NAME]), column[hcol_idx.SORT_ORDER])
    return model

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
