from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QAbstractItemView, QHeaderView


COL_DB_NAME = 0
COL_DISPLAY_NAME = 1
COL_WIDTH = 2
COL_SORT_ORDER = 3
# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width)
# column will be hidden if display_column_name is None
# column with negative with will be stretched

def UseSqlTable(db, table_name, columns):
    model = QSqlTableModel(db=db)
    model.setTable(table_name)
    model.setEditStrategy(QSqlTableModel.OnManualSubmit)
    for column in columns:
        if column[COL_DISPLAY_NAME]:
            model.setHeaderData(model.fieldIndex(column[COL_DB_NAME]), Qt.Horizontal, column[COL_DISPLAY_NAME])
        if column[COL_SORT_ORDER] is not None:
            model.setSort(model.fieldIndex(column[COL_DB_NAME]), column[COL_SORT_ORDER])
    model.select()
    return model

# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width)
# column will be hidden if display_column_name is None
# column with negative with will be stretched

def ConfigureTableView(view, model, columns):
    view.setModel(model)
    for column in columns:
        if column[COL_DISPLAY_NAME] is None:   # hide column
            view.setColumnHidden(view.model().fieldIndex(column[COL_DB_NAME]), True)

        if column[COL_WIDTH] < 0:
            view.horizontalHeader().setSectionResizeMode(model.fieldIndex(column[COL_DB_NAME]), QHeaderView.Stretch)
        else:
            view.setColumnWidth(view.model().fieldIndex(column[COL_DB_NAME]), column[COL_WIDTH])
    view.setSelectionBehavior(QAbstractItemView.SelectRows)
    font = view.horizontalHeader().font()
    font.setBold(True)
    view.horizontalHeader().setFont(font)
