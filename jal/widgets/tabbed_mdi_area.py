from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget, QMdiArea, QTabBar, QVBoxLayout


# ----------------------------------------------------------------------------------------------------------------------
# Class that acts as QMdiArea in SubWindowView mode but has Tabs at the same time
class TabbedMdiArea(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        self.mdi = QMdiArea(self)
        self.mdi.setOption(QMdiArea.DontMaximizeSubWindowOnActivation)
        self.layout.addWidget(self.mdi)

        self.tabs = QTabBar(self)
        self.tabs.setShape(QTabBar.RoundedSouth)
        self.tabs.setExpanding(False)
        self.tabs.setTabsClosable(True)
        self.layout.addWidget(self.tabs)

        self.mdi.subWindowActivated.connect(self.subWindowActivated)
        self.tabs.currentChanged.connect(self.tabClicked)
        self.tabs.tabCloseRequested.connect(self.tabClose)

    def subWindowList(self, order=QMdiArea.CreationOrder):
        return self.mdi.subWindowList(order)

    def addSubWindow(self, widget, maximized=False):
        sub_window = self.mdi.addSubWindow(widget)
        widget.onClose.connect(self.subWindowClosed)
        self.tabs.addTab(sub_window.windowTitle())
        if maximized:
            sub_window.showMaximized()
        else:
            sub_window.show()
        return sub_window

    @Slot()
    def subWindowActivated(self, window):
        if window is not None:
            self.tabs.setCurrentIndex(self.mdi.subWindowList().index(window))

    @Slot()
    def subWindowClosed(self, window):
        index = self.subWindowList().index(window)
        self.tabs.removeTab(index)

    @Slot()
    def tabClicked(self, index):
        try:
            sub_window = self.subWindowList()[index]
        except IndexError:
            return
        self.mdi.setActiveSubWindow(sub_window)

    @Slot()
    def tabClose(self, index):
        try:
            sub_window = self.subWindowList()[index]
        except KeyError:
            return
        self.mdi.removeSubWindow(sub_window)
        self.tabs.removeTab(index)
