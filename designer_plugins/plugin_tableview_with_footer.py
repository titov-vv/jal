from jal.widgets.custom.tableview_with_footer import TableViewWithFooter

from PySide6.QtGui import QIcon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='TableViewWithFooter' name='tableViewWithFooter'>
        <property name='geometry'>
            <rect>
                <x>0</x>
                <y>0</y>
                <width>400</width>
                <height>300</height>
            </rect>
        </property>
    </widget>
</ui>
"""


class TableViewWithFooterPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = TableViewWithFooter(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ''

    def icon(self):
        return QIcon()

    def includeFile(self):
        return 'jal/widgets/custom/tableview_with_footer.h'

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return 'TableViewWithFooter'

    def toolTip(self):
        return 'QTableView that has a footer'

    def whatsThis(self):
        return self.toolTip()
