# Here reference goes from PYSIDE_DESIGNER_PLUGINS directory
from jal.constants import AccountTypeComboBox

from PySide6.QtGui import QIcon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='AccountTypeComboBox' name='accountTypeComboBox'>
    </widget>
</ui>
"""


class AccountTypeComboBoxPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = AccountTypeComboBox(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return 'JAL widgets'

    def icon(self):
        return QIcon()

    def includeFile(self):
        return 'jal/constants.h'

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return 'AccountTypeComboBox'

    def toolTip(self):
        return 'ComboBox listing predefined account types'

    def whatsThis(self):
        return self.toolTip()
