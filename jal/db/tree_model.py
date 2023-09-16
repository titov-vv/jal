from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex

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

    def index(self, row, column, parent=None):
        if not parent.isValid():
            parent = self._root
        else:
            parent = parent.internalPointer()
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
        return self.createIndex(0, 0, parent_item)

    def rowCount(self, parent=None):
        if not parent.isValid():
            parent_item = self._root
        else:
            parent_item = parent.internalPointer()
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

    # defines report grouping by provided field list - 'group_field1;group_field2;...'
    # return True if grouping was actually changed and False otherwise
    def setGrouping(self, group_list) -> bool:
        new_groups = group_list.split(';') if group_list else []
        if new_groups == self._groups:
            return False
        self._groups = new_groups
        return True

    def prepareData(self):
        self.modelReset.emit()
        if not self._view_configured:
            self.configureView()
        self._view.expandAll()

    def configureView(self):
        font = self._view.header().font()
        font.setBold(True)
        self._view.header().setFont(font)
        self._view_configured = True
