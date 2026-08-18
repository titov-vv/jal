# Here reference goes from PYSIDE_DESIGNER_PLUGINS directory
from jal.widgets.operations_tabs import JalOperationsTabs

from designer_plugins.plugin_icon import jal_widget_icon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='JalOperationsTabs' name='jalOperationsTabs'>
    </widget>
</ui>
"""


class JalOperationsTabsPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = JalOperationsTabs(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return 'JAL widgets'

    def icon(self):
        return jal_widget_icon()

    def includeFile(self):
        return 'jal/widgets/operations_tabs.h'

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return 'JalOperationsTabs'

    def toolTip(self):
        return 'Stacked set of all ledger operation entry forms (trade, transfer, dividend, etc.), one page per operation type'

    def whatsThis(self):
        return self.toolTip()
