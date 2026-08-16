# Here reference goes from PYSIDE_DESIGNER_PLUGINS directory
from jal.widgets.reference_selector import ReferenceSelectorWidget

from PySide6.QtGui import QIcon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='ReferenceSelectorWidget' name='referenceSelectorWidget'>
    </widget>
</ui>
"""


class ReferenceSelectorWidgetPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = ReferenceSelectorWidget(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return 'JAL widgets'

    def icon(self):
        return QIcon()

    def includeFile(self):
        return 'jal/widgets/reference_selector.h'

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return 'ReferenceSelectorWidget'

    def toolTip(self):
        return 'Widget to select and display a reference-table item, with a search dialog button'

    def whatsThis(self):
        return self.toolTip()
