from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtWidgets import QWidget, QTabWidget


# ----------------------------------------------------------------------------------------------------------------------
# Base class that is used for any other widget which should be displayed inside JAL MainWindow window area
# implemented as TabbedWindowArea() class (below)
class MdiWidget(QWidget):
    onClose = Signal(QWidget)   # Reports the widget itself, so that the area it belongs to may drop it

    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot()
    def closeEvent(self, event):
        self.onClose.emit(self)
        super().closeEvent(event)

    def refresh(self):
        pass


# ----------------------------------------------------------------------------------------------------------------------
# Area that keeps all application windows. Document-like ones (operations, reports) are shown as tabs, while
# small auxiliary ones (charts, tax forms) are shown as separate top-level windows still owned by the main
# window - a tab would leave no way to look at the data the window was opened from.
# Child windows should be derived from MdiWidget class for correct operation
class TabbedWindowArea(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setDocumentMode(True)
        self.setTabsClosable(True)
        self.setMovable(True)

        self._windows = []   # Free-floating windows - they have no tab of their own

        self.tabCloseRequested.connect(self.onTabCloseRequested)

    # Every window that is currently open in the area: tabs in tab order first, free-floating ones after them
    def windows(self) -> list:
        return [self.widget(i) for i in range(self.count())] + list(self._windows)

    # Shows the given widget as a tab or, if floating is True, as a window of its own of the given size
    def addWindow(self, widget, floating=False, size=None):
        widget.onClose.connect(self.onWindowClosed)
        if floating:
            self._windows.append(widget)
            widget.setParent(self.window(), Qt.Window)   # A real window that the main window still owns
            if size is not None:
                widget.resize(size[0], size[1])
            geometry = widget.frameGeometry()
            geometry.moveCenter(self.window().frameGeometry().center())
            widget.move(geometry.topLeft())
            widget.show()
        else:
            self.addTab(widget, widget.windowTitle().replace('&', '&&'))  # & -> && to prevent shortcut creation
            self.setCurrentWidget(widget)
        return widget

    @Slot(int)
    def onTabCloseRequested(self, index):
        widget = self.widget(index)
        if widget is not None:
            widget.close()   # A closed widget removes itself from the area via its onClose signal

    @Slot(QWidget)
    def onWindowClosed(self, widget):
        index = self.indexOf(widget)
        if index >= 0:
            self.removeTab(index)    # Removal from the tab bar doesn't drop the widget itself, hence deleteLater()
        if widget in self._windows:
            self._windows.remove(widget)
        widget.deleteLater()
