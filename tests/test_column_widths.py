import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QStringListModel
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTableView, QTreeView

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import Setup
from jal.db.settings import JalSettings
from jal.widgets.helpers import restore_columns, save_columns, columns_state_key, forget_columns
from jal.widgets.custom.tableview_with_footer import TableViewWithFooter
from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter


# Every widget built here gets a parent: a parentless one is collected by the cyclic collector at a moment
# unrelated to the test that made it, and takes the process down with it.
@pytest.fixture
def parent(prepare_db):
    holder = QWidget()
    yield holder
    holder.deleteLater()


# Two windows of different classes, each holding a table under the very same name - the case the key has to tell
# apart, as half the reports call their table 'ReportTableView'
class FirstWindow(QWidget):
    def __init__(self, parent=None, view_name='ReportTableView'):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.view = QTableView(self)
        self.view.setObjectName(view_name)
        self.view.setModel(QStringListModel(["one", "two", "three"], self.view))
        layout.addWidget(self.view)
        self.resize(600, 200)


class SecondWindow(FirstWindow):
    pass


# ----------------------------------------------------------------------------------------------------------------------
def test_a_width_the_user_set_survives_a_rebuild(parent):
    window = FirstWindow(parent)
    window.show()
    window.view.setColumnWidth(0, 275)
    save_columns(window, Setup.COLUMNS_STATE_PREFIX)
    window.close()
    forget_columns()      # the layout has to come back from the database, not from what is still in memory

    reopened = FirstWindow(parent)
    reopened.show()
    assert reopened.view.columnWidth(0) != 275     # ... it starts at the width the style gives it
    restore_columns(reopened.view, Setup.COLUMNS_STATE_PREFIX)
    assert reopened.view.columnWidth(0) == 275


def test_two_windows_with_a_table_of_the_same_name_keep_two_layouts(parent):
    first, second = FirstWindow(parent), SecondWindow(parent)
    first.show()
    second.show()
    assert columns_state_key(first.view, Setup.COLUMNS_STATE_PREFIX) \
           != columns_state_key(second.view, Setup.COLUMNS_STATE_PREFIX)

    first.view.setColumnWidth(0, 120)
    second.view.setColumnWidth(0, 320)
    save_columns(first, Setup.COLUMNS_STATE_PREFIX)
    save_columns(second, Setup.COLUMNS_STATE_PREFIX)
    forget_columns()

    reopened_first, reopened_second = FirstWindow(parent), SecondWindow(parent)
    reopened_first.show()
    reopened_second.show()
    restore_columns(reopened_first.view, Setup.COLUMNS_STATE_PREFIX)
    restore_columns(reopened_second.view, Setup.COLUMNS_STATE_PREFIX)
    assert reopened_first.view.columnWidth(0) == 120
    assert reopened_second.view.columnWidth(0) == 320


# A table with no objectName has no key of its own and must not be written under the bare prefix, where it would
# share one row with every other unnamed table in the application
def test_an_unnamed_table_is_not_stored(parent):
    window = FirstWindow(parent, view_name='')
    window.show()
    window.view.setColumnWidth(0, 175)
    save_columns(window, Setup.COLUMNS_STATE_PREFIX)
    assert JalSettings().getStr(Setup.COLUMNS_STATE_PREFIX) == ''
    restore_columns(window.view, Setup.COLUMNS_STATE_PREFIX)   # and asking for it back does nothing at all
    assert window.view.columnWidth(0) == 175


# A report re-configures its view on every change of its parameters, which re-applies the default widths.
# The width the user is looking at has to come back after that, without a trip through the database.
def test_a_width_survives_a_re_configuration_of_the_report(parent):
    window = FirstWindow(parent)
    window.show()
    restore_columns(window.view, Setup.COLUMNS_STATE_PREFIX)   # as the first configureView() would do
    default_width = window.view.columnWidth(0)

    window.view.setColumnWidth(0, 290)                          # as the user would drag it
    QApplication.processEvents()                                # the capture is deferred to the next event loop turn

    window.view.setColumnWidth(0, default_width)                # what a second configureView() applies ...
    restore_columns(window.view, Setup.COLUMNS_STATE_PREFIX)    # ... and what it ends with
    assert window.view.columnWidth(0) == 290


# The window area gives a report its own window; closing it is what stores the layout, through MdiWidget.closeEvent
def test_a_report_window_stores_its_columns_when_it_is_closed(parent):
    from jal.widgets.mdi import MdiWidget

    class Report(MdiWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)
            self.view = QTreeView(self)
            self.view.setObjectName('ReportTreeView')
            self.view.setModel(QStringListModel(["one", "two"], self.view))
            layout.addWidget(self.view)
            self.resize(500, 200)

    window = Report(parent)
    window.show()
    window.view.setColumnWidth(0, 310)
    window.close()
    forget_columns()

    reopened = Report(parent)
    reopened.show()
    restore_columns(reopened.view, Setup.COLUMNS_STATE_PREFIX)
    assert reopened.view.columnWidth(0) == 310


# The real thing: the operations window has its widths back when it is opened again
def test_operations_window_remembers_its_columns(parent):
    from jal.widgets.operations_widget import OperationsWidget

    parent.resize(1100, 620)
    parent.show()
    window = OperationsWidget(parent)
    window.resize(1100, 620)
    window.show()
    QApplication.processEvents()
    window.ui.OperationsTableView.setColumnWidth(1, 333)
    window.close()
    forget_columns()

    reopened = OperationsWidget(parent)
    reopened.resize(1100, 620)
    reopened.show()
    QApplication.processEvents()
    assert reopened.ui.OperationsTableView.columnWidth(1) == 333


# A table with a footer keeps the totals in a header of its own, which follows the columns through the signals the
# table header emits while the user drags them. QHeaderView.restoreState() puts a whole layout in place without
# emitting any of them, so the footer has to be told separately - otherwise every total stands under the wrong
# column as soon as a stored layout is restored.
class FooterModel(QAbstractTableModel):
    def rowCount(self, parent=QModelIndex()):
        return 2

    def columnCount(self, parent=QModelIndex()):
        return 4

    def data(self, index, role=Qt.DisplayRole):
        return f"{index.row()}:{index.column()}" if role == Qt.DisplayRole else None

    def footerData(self, section, role=Qt.DisplayRole):
        return f"total {section}" if role == Qt.DisplayRole else None


class FooterWindow(QWidget):
    def __init__(self, parent=None, tree=False):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.view = TreeViewWithFooter(self) if tree else TableViewWithFooter(self)
        self.view.setObjectName('FooterTreeView' if tree else 'FooterTableView')
        self.view.setModel(FooterModel(self.view))
        layout.addWidget(self.view)
        self.resize(700, 250)

    def header(self):
        return self.view.header() if isinstance(self.view, TreeViewWithFooter) else self.view.horizontalHeader()


@pytest.mark.parametrize("tree", [False, True])
def test_footer_columns_follow_a_restored_layout(parent, tree):
    window = FooterWindow(parent, tree=tree)
    window.show()
    for i, width in enumerate((60, 110, 160, 210)):
        window.header().resizeSection(i, width)
    save_columns(window, Setup.COLUMNS_STATE_PREFIX)
    window.close()
    forget_columns()

    reopened = FooterWindow(parent, tree=tree)
    reopened.show()
    for i, width in enumerate((210, 160, 110, 60)):   # the defaults a configureView() applies
        reopened.header().resizeSection(i, width)
    restore_columns(reopened.view, Setup.COLUMNS_STATE_PREFIX)
    footer = reopened.view.footer()
    assert [reopened.header().sectionSize(i) for i in range(4)] == [60, 110, 160, 210]
    assert [footer.sectionSize(i) for i in range(4)] == [60, 110, 160, 210]


# A footer section may be spanned over several columns (a 'Total' label under the first two, for instance) - after a
# restored layout it has to be as wide as the columns it covers, and the columns it takes the place of stay hidden
def test_a_spanned_footer_section_follows_a_restored_layout(parent):
    window = FooterWindow(parent)
    window.view.footer().set_span(0, [0, 1])
    window.show()
    for i, width in enumerate((60, 110, 160, 210)):
        window.header().resizeSection(i, width)
    save_columns(window, Setup.COLUMNS_STATE_PREFIX)
    window.close()
    forget_columns()

    reopened = FooterWindow(parent)
    reopened.view.footer().set_span(0, [0, 1])
    reopened.show()
    for i, width in enumerate((210, 160, 110, 60)):
        reopened.header().resizeSection(i, width)
    restore_columns(reopened.view, Setup.COLUMNS_STATE_PREFIX)
    footer = reopened.view.footer()
    assert footer.sectionSize(0) == 60 + 110
    assert footer.isSectionHidden(1)
    assert [footer.sectionSize(i) for i in (2, 3)] == [160, 210]
