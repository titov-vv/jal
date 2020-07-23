from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QAbstractItemView, QHeaderView

class hcol_idx:
    DB_NAME = 0
    DISPLAY_NAME = 1
    WIDTH = 2
    SORT_ORDER = 3
    DELEGATE = 4
# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width, sort_order, delegate)
# column will be hidden if display_column_name is None
# column with negative with will be stretched
# sort order should be from Qt module (eg. Qt.AscendingOrder) or None
# delegate is a function for custom paint and editors

def UseSqlTable(db, table_name, columns):
    model = QSqlTableModel(db=db)
    model.setTable(table_name)
    model.setEditStrategy(QSqlTableModel.OnManualSubmit)
    for column in columns:
        if column[hcol_idx.DISPLAY_NAME]:
            model.setHeaderData(model.fieldIndex(column[hcol_idx.DB_NAME]), Qt.Horizontal, column[hcol_idx.DISPLAY_NAME])
        if column[hcol_idx.SORT_ORDER] is not None:
            model.setSort(model.fieldIndex(column[hcol_idx.DB_NAME]), column[hcol_idx.SORT_ORDER])
    model.select()
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
