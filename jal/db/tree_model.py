from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex
from jal.constants import Setup
from jal.widgets.helpers import restore_columns

# ----------------------------------------------------------------------------------------------------------------------
# Base class to provide a common functionality of a tree element
class AbstractTreeItem:
    def __init__(self, parent=None, group=''):
        self._parent = parent
        self._children = []
        self._group = group

    def setParent(self, parent: AbstractTreeItem):
        self._parent = parent

    def getParent(self) -> AbstractTreeItem:
        return self._parent

    def childrenCount(self) -> int:
        return len(self._children)

    def appendChild(self, child: AbstractTreeItem):
        child.setParent(self)
        self._children.append(child)
        if self.isGroup():
            self.updateGroupDetails(child.details())

    def getChild(self, id) -> Optional[AbstractTreeItem]:
        if id < 0 or id >= len(self._children):
            return None
        return self._children[id]

    def childIndex(self, child):
        assert child in self._children
        return self._children.index(child)

    def row(self):
        if self._parent is None:
            return 0
        return self._parent.childIndex(self)

    def details(self, **kwargs):
        raise NotImplementedError("To be defined in derived class")

    # Update current group data after new child with child_data was added into the group
    def updateGroupDetails(self, child_data):
        self._calculateGroupTotals(child_data)
        if self._parent is not None:
            self._parent.updateGroupDetails(child_data)
        self.updateChildrenData()

    # Update group children data (usually after some changes in group data)
    def updateChildrenData(self):
        if self.isGroup():
            for child in self._children:
                child._afterParentGroupUpdate(self.details())
                child.updateChildrenData()

    # This method is called if current item is a group. It should update group data with new child_data
    def _calculateGroupTotals(self, child_data):
        raise NotImplementedError("To be defined in derived class")

    # This method is called if parent group data were updated. It should update element data with new group_data
    def _afterParentGroupUpdate(self, group_data):
        raise NotImplementedError("To be defined in derived class")

    def isGroup(self) -> bool:
        if self._parent is None:   # Root element is always a group
            return True
        return self._group != ''

    # True for a group the model wants folded when the tree is (re)built - a bucket whose subtotal says everything
    # the reader normally needs. A model that has no such group leaves this alone and every group opens as before.
    def isFolded(self) -> bool:
        return False


# ----------------------------------------------------------------------------------------------------------------------
# Base class to provide a common functionality of a tree model
class ReportTreeModel(QAbstractItemModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._root = None
        self._groups = []
        self._columns = []
        self._view_configured = False
        # Group rows the user has opened by hand since this model was created. A rebuild happens on every ledger
        # update, so without this a folded group would snap shut under a reader who had just opened it.
        self._unfolded = set()
        self._restoring_folds = False   # True while the model itself opens and closes rows - see prepareData()

    # An absent index is an INVALID QModelIndex, never None: index() is asked for children that may not exist (the
    # xlsx exporter probes for a second tree level that way, and an empty report has no first one), and a None fed
    # back into hasIndex()/index() raises instead of simply being invalid.
    def index(self, row, column, parent=None):
        parent = QModelIndex() if parent is None else parent
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent = parent.internalPointer() if parent.isValid() else self._root
        child = parent.getChild(row)
        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()

    def parent(self, index=None):
        if not index.isValid():
            return QModelIndex()
        child_item = index.internalPointer()
        parent_item = child_item.getParent()
        if parent_item == self._root:
            return QModelIndex()
        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent=None):
        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item = parent.internalPointer()
        if parent.column() > 0:
            return 0
        if parent_item is not None:
            return parent_item.childrenCount()
        else:
            return 0

    def headerWidth(self, section):
        return self._view.header().sectionSize(section)

    def fieldIndex(self, field_name: str) -> int:
        for i, column in enumerate(self._columns):
            if column['field'] == field_name:
                return i
        return -1

    def columnCount(self, parent=None):
        if parent is None:
            parent_item = self._root
        elif not parent.isValid():
            parent_item = self._root
        else:
            parent_item = parent.internalPointer()
        if parent_item is not None:
            return len(self._columns)
        else:
            return 0

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._columns[section]['name']
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignCenter)
        return None

    def footerData(self, section, role=Qt.DisplayRole):
        return None

    # defines report grouping by provided field list - 'group_field1;group_field2;...'
    # return True if grouping was actually changed and False otherwise
    def setGrouping(self, group_list) -> bool:
        new_groups = group_list.split(';') if group_list else []
        if new_groups == self._groups:
            return False
        self._groups = new_groups
        return True

    def prepareData(self):
        if not self._view_configured:
            self.configureView()
        # expandAll() and collapse() below emit the view's own expanded/collapsed signals, which is how the user's
        # choices are recorded - so what the model does to the tree itself must not be mistaken for one of them.
        self._restoring_folds = True
        self._view.expandAll()
        self._fold_groups()
        self._restoring_folds = False

    # Collapses the groups that ask to be folded, after expandAll() has opened everything. Only top-level groups are
    # examined: a folded group hides its whole subtree anyway, and the state of what is inside it is not visible.
    def _fold_groups(self):
        for row in range(self.rowCount(QModelIndex())):
            index = self.index(row, 0)
            item = index.internalPointer()
            if item is not None and item.isFolded() and self.groupKey(item) not in self._unfolded:
                self._view.collapse(index)

    # What identifies a group row across rebuilds, so that "the user opened this one" outlives the tree it was in
    def groupKey(self, item) -> str:
        group = item.getGroup()
        return f"{group[0]}={group[1]}" if group else ''

    # Called by the view when the user opens or closes a group, so a folded group stays open once it is opened
    def setGroupExpanded(self, index, expanded: bool):
        if self._restoring_folds or not index.isValid():
            return
        item = index.internalPointer()
        if item is None or not item.isGroup():
            return
        key = self.groupKey(item)
        if not key:
            return
        if expanded:
            self._unfolded.add(key)
        else:
            self._unfolded.discard(key)

    def configureView(self):
        self._view.header().setStretchLastSection(False)
        self._view_configured = True
        restore_columns(self._view, Setup.COLUMNS_STATE_PREFIX)
