from __future__ import annotations
from PySide6.QtCore import QAbstractItemModel, QModelIndex

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
        if self._group:
            self.updateGroupDetails(child.details())

    def getChild(self, id) -> AbstractTreeItem:
        if id < 0 or id >= len(self._children):
            return None
        return self._children[id]

    def details(self):
        raise NotImplementedError("To be defined in derived class")

    def updateGroupDetails(self, child_data):
        self._calculateGroupTotals(child_data)
        if self._parent is not None:
            self._parent.updateGroupDetails(child_data)

    def _calculateGroupTotals(self, child_data):
        raise NotImplementedError("To be defined in derived class")

    def isGroup(self) -> bool:
        return self._group != ''


# ----------------------------------------------------------------------------------------------------------------------
# Base class to provide a common functionality of a tree model
class AbstractTreeModel(QAbstractItemModel):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self._view = parent_view
        self._root = None

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

    # defines report grouping by provided field list - 'group_field1;group_field2;...'
    def setGrouping(self, group_list):
        if group_list:
            self._groups = group_list.split(';')
        else:
            self._groups = []
        self.prepareData()
        self.configureView()

    def prepareData(self):
        raise NotImplementedError("To be defined in descendant class")

    def configureView(self):
        raise NotImplementedError("To be defined in descendant class")
