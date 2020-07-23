from PySide2.QtCore import Qt
from PySide2.QtSql import QSqlTableModel
from PySide2.QtWidgets import QAbstractItemView, QHeaderView


# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width)
# column will be hidden if display_column_name is None
# column with negative with will be stretched

def UseSqlTable(db, table_name, columns):
    model = QSqlTableModel(db=db)
    model.setTable(table_name)
    model.setEditStrategy(QSqlTableModel.OnManualSubmit)
    for column in columns:
        if column[1]:
            model.setHeaderData(model.fieldIndex(column[0]), Qt.Horizontal, column[1])
        if column[3] is not None:
            model.setSort(model.fieldIndex(column[0]), column[3])
    model.select()
    return model

# -------------------------------------------------------------------------------------------------------------------
# column_list is a list of tuples: (db_column_name, display_column_name, width)
# column will be hidden if display_column_name is None
# column with negative with will be stretched

def ConfigureTableView(view, model, columns):
    view.setModel(model)
    for column in columns:
        if column[1] is None:   # hide column
            view.setColumnHidden(view.model().fieldIndex(column[0]), True)

        if column[2] < 0:
            view.horizontalHeader().setSectionResizeMode(model.fieldIndex(column[0]), QHeaderView.Stretch)
        else:
            view.setColumnWidth(view.model().fieldIndex(column[0]), column[2])
    view.setSelectionBehavior(QAbstractItemView.SelectRows)
    font = view.horizontalHeader().font()
    font.setBold(True)
    view.horizontalHeader().setFont(font)
