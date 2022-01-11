from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget, QMdiArea, QTabBar, QVBoxLayout


# ----------------------------------------------------------------------------------------------------------------------
# Class that acts as QMdiArea in SubWindowView mode but has Tabs at the same time
class TabbedMdiArea(QWidget):
    TAB_IDX_PROPERTY = 'TabIndex'

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.subWindows = {}

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)

        self.mdi = QMdiArea(self)
        self.layout.addWidget(self.mdi)

        self.tabs = QTabBar(self)
        self.tabs.setShape(QTabBar.RoundedSouth)
        self.tabs.setExpanding(False)
        self.tabs.setTabsClosable(True)
        self.layout.addWidget(self.tabs)

        self.mdi.subWindowActivated.connect(self.subWindowActivated)
        self.tabs.currentChanged.connect(self.tabClicked)

    def addSubWindow(self, widget):
        sub_window = self.mdi.addSubWindow(widget)
        idx = self.tabs.addTab(sub_window.windowTitle())
        sub_window.setProperty(TabbedMdiArea.TAB_IDX_PROPERTY, idx)
        self.subWindows[idx] = sub_window
        return sub_window

    @Slot()
    def subWindowActivated(self, window):
        if window is not None:
            self.tabs.setCurrentIndex(window.property(TabbedMdiArea.TAB_IDX_PROPERTY))

    @Slot()
    def tabClicked(self, index):
        try:
            sub_window = self.subWindows[index]
        except KeyError:
            return
        self.mdi.setActiveSubWindow(sub_window)
