# ----------------------------------------------------------------------------------------------------------------------
# Base class to provide a common functionality of a tree element
class AbstractTreeItem:
    def __init__(self, parent=None, group=''):
        self._parent = parent
        self._children = []
        self._group = group

    def setParent(self, parent):
        self._parent = parent

    def getParent(self):
        return self._parent

    def childrenCount(self):
        return len(self._children)

    def appendChild(self, child):
        child.setParent(self)
        self._children.append(child)
        if self._group:
            self.updateGroupDetails(child.details())

    def getChild(self, id):
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

    def isGroup(self):
        return self._group != ''
