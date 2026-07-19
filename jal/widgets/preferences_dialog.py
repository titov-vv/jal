from PySide6.QtWidgets import QDialog, QWidget, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QListWidgetItem
from jal.ui.ui_preferences_dlg import Ui_PreferencesDlg
from jal.db.settings_registry import SettingsRegistry, SettingType


# ----------------------------------------------------------------------------------------------------------------------
# Modal dialog that shows every setting registered in SettingsRegistry, one page per registered page name.
# The dialog knows nothing about any particular setting: pages, labels and editors are built from the registered
# descriptors, so a module that registers a new setting gets it displayed without a change here.
# Values are written to the database only when the dialog is accepted, so 'Cancel' discards every change.
class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_PreferencesDlg()
        self.ui.setupUi(self)
        self._editors = {}    # SettingDescriptor.key -> editor widget

        for page in SettingsRegistry.pages():
            settings = SettingsRegistry.settings_of_page(page)
            self.ui.PagesStack.addWidget(self._build_page(settings))
            QListWidgetItem(settings[0].translated_page(), self.ui.PagesList)
        self.ui.PagesList.currentRowChanged.connect(self.ui.PagesStack.setCurrentIndex)
        if self.ui.PagesList.count():
            self.ui.PagesList.setCurrentRow(0)

    # Builds one page of the dialog as a form of 'label: editor' rows
    def _build_page(self, settings: list) -> QWidget:
        page = QWidget(self)
        layout = QFormLayout(page)
        for setting in settings:
            editor = self._build_editor(setting)
            if setting.tooltip:
                editor.setToolTip(setting.translated_tooltip())
            self._editors[setting.key] = editor
            layout.addRow(setting.translated_label(), editor)
        return page

    # Creates the editor that matches the type of the setting, loaded with its current value
    def _build_editor(self, setting) -> QWidget:
        value = setting.value()
        if setting.type == SettingType.Boolean:
            editor = QCheckBox(self)
            editor.setChecked(value)
        elif setting.type == SettingType.Integer:
            editor = QSpinBox(self)
            # Integer settings are counts, sizes and intervals, so they are deliberately kept non-negative.
            # A setting that needs another range should carry it in its descriptor rather than widen this default.
            editor.setRange(0, 2147483647)
            editor.setValue(value)
        else:
            editor = QLineEdit(self)
            editor.setText(value)
        return editor

    # Stores the edited values. Called on 'Ok' only, as the button box is connected to accept() in the .ui file.
    def accept(self) -> None:
        for page in SettingsRegistry.pages():
            for setting in SettingsRegistry.settings_of_page(page):
                setting.set_value(self._editor_value(setting))
        super().accept()

    def _editor_value(self, setting):
        editor = self._editors[setting.key]
        if setting.type == SettingType.Boolean:
            return editor.isChecked()
        if setting.type == SettingType.Integer:
            return editor.value()
        return editor.text().strip()
