# Environment variable PYSIDE_DESIGNER_PLUGINS should contain path to this file

from designer_plugins.plugin_date_range_selector import DateRangeSelectorPlugin
from designer_plugins.plugin_db_lookup_combobox import DDbLookupComboBoxPlugin

from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

if __name__ == '__main__':
    QPyDesignerCustomWidgetCollection.addCustomWidget(DateRangeSelectorPlugin())
    QPyDesignerCustomWidgetCollection.addCustomWidget(DDbLookupComboBoxPlugin())
