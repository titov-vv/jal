from PySide6.QtCore import Slot, Signal
from PySide6.QtWidgets import QWidget, QMdiArea, QTabBar, QVBoxLayout


# ----------------------------------------------------------------------------------------------------------------------
# Base class that is used for any other widget which should be displayed inside JAL MainWindow MDI
# implemented as TabbedMdiArea() class (below)
class MdiWidget(QWidget):
    onClose = Signal(QWidget)

    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot()
    def closeEvent(self, event):
        self.onClose.emit(self.parent())
        super().closeEvent(event)

    def refresh(self):
        pass


# ----------------------------------------------------------------------------------------------------------------------
# Class that acts as QMdiArea in SubWindowView mode but has Tabs at the same time
# Child windows should be derived from MdiWidget class for correct operation
class TabbedMdiArea(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

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

    def addSubWindow(self, widget, maximized=False, size=None):
        sub_window = self.mdi.addSubWindow(widget)
        widget.onClose.connect(self.subWindowClosed)
        self.tabs.addTab(sub_window.windowTitle().replace('&', '&&'))  # & -> && to prevent shortcut creation
        if maximized:
            sub_window.showMaximized()
        else:   # show centered otherwise
            if size is None:
                w = sub_window.width()
                h = sub_window.height()
            else:
                w = size[0]
                h = size[1]
            x = self.mdi.x() + self.mdi.width() / 2 - w / 2
            y = self.mdi.y() + self.mdi.height() / 2 - h / 2
            sub_window.setGeometry(x, y, w, h)
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
