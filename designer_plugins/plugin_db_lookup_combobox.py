# Here reference goes from PYSIDE_DESIGNER_PLUGINS directory
from jal.widgets.custom.db_lookup_combobox import DbLookupComboBox

from PySide6.QtGui import QIcon
from PySide6.QtDesigner import (QDesignerCustomWidgetInterface)


DOM_XML = """
<ui language='c++'>
    <widget class='DbLookupComboBox' name='dbLookupCombobox'>
        <property name='geometry'>
            <rect>
                <x>0</x>
                <y>0</y>
                <width>300</width>
                <height>32</height>
            </rect>
        </property>
        <property name='db_table'>
            <string notr="true" />
        </property>
        <property name='key_field'>
            <string notr="true" />
        </property>
        <property name='db_field'>
            <string notr="true" />
        </property>
    </widget>
</ui>
"""


class DbLookupComboBoxPlugin(QDesignerCustomWidgetInterface):
    def __init__(self):
        super().__init__()
        self._initialized = False

    def createWidget(self, parent):
        t = DbLookupComboBox(parent)
        return t

    def domXml(self):
        return DOM_XML

    def group(self):
        return ''

    def icon(self):
        return QIcon()

    def includeFile(self):
        return 'jal/widgets/custom/db_lookup_combobox.h'

    def initialize(self, form_editor):
        if self._initialized:
            return
        self._initialized = True

    def isContainer(self):
        return False

    def isInitialized(self):
        return self._initialized

    def name(self):
        return 'DbLookupComboBox'

    def toolTip(self):
        return 'ComboBox to select available values from database lookup table'

    def whatsThis(self):
        return self.toolTip()
