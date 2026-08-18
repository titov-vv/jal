# Here reference goes from PYSIDE_DESIGNER_PLUGINS directory
from jal.widgets.mdi import TabbedMdiArea

from designer_plugins.plugin_icon import jal_widget_icon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='TabbedMdiArea' name='tabbedMdiArea'>
    </widget>
</ui>
"""


class TabbedMdiAreaPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = TabbedMdiArea(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return 'JAL widgets'

    def icon(self):
        return jal_widget_icon()

    def includeFile(self):
        return 'jal/widgets/mdi.h'

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return 'TabbedMdiArea'

    def toolTip(self):
        return 'MDI area with a bottom tab bar for switching between maximized sub-windows'

    def whatsThis(self):
        return self.toolTip()
