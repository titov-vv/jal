# Here reference goes from PYSIDE_DESIGNER_PLUGINS directory
from jal.widgets.account_select import AccountButton

from PySide6.QtGui import QIcon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='AccountButton' name='accountButton'>
    </widget>
</ui>
"""


class AccountButtonPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = AccountButton(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return 'JAL widgets'

    def icon(self):
        return QIcon()

    def includeFile(self):
        return 'jal/widgets/account_select.h'

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return 'AccountButton'

    def toolTip(self):
        return "Button that opens an account-selection dialog and displays the chosen account's name"

    def whatsThis(self):
        return self.toolTip()
