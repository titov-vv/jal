from jal.widgets.custom.treeview_with_footer import TreeViewWithFooter

from designer_plugins.plugin_icon import jal_widget_icon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='TreeViewWithFooter' name='treeViewWithFooter'>
    </widget>
</ui>
"""


class TreeViewWithFooterPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = TreeViewWithFooter(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return 'JAL widgets'

    def icon(self):
        return jal_widget_icon()

    def includeFile(self):
        return 'jal/widgets/custom/treeview_with_footer.h'

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return 'TreeViewWithFooter'

    def toolTip(self):
        return 'QTreeView that has a footer'

    def whatsThis(self):
        return self.toolTip()
