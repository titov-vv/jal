# Here reference goes from PYSIDE_DESIGNER_PLUGINS directory
from jal.widgets.account_select import OptionalCurrencyComboBox

from PySide6.QtGui import QIcon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='OptionalCurrencyComboBox' name='optionalCurrencyComboBox'>
    </widget>
</ui>
"""


class OptionalCurrencyComboBoxPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = OptionalCurrencyComboBox(parent)
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
        return 'OptionalCurrencyComboBox'

    def toolTip(self):
        return 'Optional currency selector: a checkbox plus a currency ComboBox, for a field where currency is not mandatory'

    def whatsThis(self):
        return self.toolTip()
