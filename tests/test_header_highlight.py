import base64

import pytest
from PySide6.QtCore import QStringListModel
from PySide6.QtWidgets import QAbstractItemView, QTableView, QTreeView, QVBoxLayout, QWidget

from tests.fixtures import project_root, data_path, prepare_db
from jal.constants import Setup
from jal.db.settings import JalSettings
from jal.reports.reports import Reports
from jal.widgets.helpers import columns_state_key, forget_columns, restore_columns, set_grids_metrics
from jal.widgets.operations_widget import OperationsWidget


# Test widgets get a parent: a parentless one can abort the process from the cyclic collector
@pytest.fixture
def parent(prepare_db):
    forget_columns()
    holder = QWidget()
    yield holder
    forget_columns()
    holder.deleteLater()


class Window(QWidget):
    def __init__(self, parent, view_class=QTableView):
        super().__init__(parent)
        self.view = view_class(self)
        self.view.setObjectName('View')
        self.view.setModel(QStringListModel(["one", "two", "three"], self.view))
        QVBoxLayout(self).addWidget(self.view)
        self.resize(600, 200)


def highlighted_headers(window) -> list:
    views = [x for x in window.findChildren(QAbstractItemView) if isinstance(x, (QTableView, QTreeView))]
    views = [x for x in views if x.objectName() not in ('', 'qt_calendar_calendarview')]
    headers = []
    for view in views:
        if isinstance(view, QTreeView):
            headers.append((view, view.header()))
        else:
            headers += [(view, view.horizontalHeader()), (view, view.verticalHeader())]
    return [(type(window).__name__, view.objectName()) for view, header in headers if header.highlightSections()]


# ----------------------------------------------------------------------------------------------------------------------
def test_grids_are_not_highlighted(parent):
    for view_class in (QTableView, QTreeView):
        window = Window(parent, view_class)
        set_grids_metrics(window)
        assert highlighted_headers(window) == []


# A stored layout carries the flag and turns highlighting back on
def test_a_stored_layout_does_not_bring_highlighting_back(parent):
    window = Window(parent)
    header = window.view.horizontalHeader()
    assert header.highlightSections()   # as a layout stored by an earlier version has it
    stored = base64.encodebytes(header.saveState().data()).decode('utf-8')
    JalSettings().setValue(columns_state_key(window.view, Setup.COLUMNS_STATE_PREFIX), stored)

    set_grids_metrics(window)
    restore_columns(window.view, Setup.COLUMNS_STATE_PREFIX)
    assert not header.highlightSections()


def test_a_selection_does_not_change_the_header(parent):
    window = Window(parent)
    set_grids_metrics(window)
    window.show()
    header = window.view.horizontalHeader()
    before = header.grab().toImage()
    window.view.selectRow(0)
    assert header.grab().toImage() == before


def test_real_windows_are_not_highlighted(parent):
    reports = Reports(None, parent)
    for report in reports.items:
        window = getattr(report['module'], report['window_class'])(reports)
        assert highlighted_headers(window) == [], report['window_class']
    assert highlighted_headers(OperationsWidget(parent)) == []
