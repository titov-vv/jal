from dataclasses import dataclass
from PySide6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP
from jal.db.settings import JalSettings

# Context that every translatable string of the settings registry belongs to.
# Mind that the registration sites below spell it out as the literal "Preferences" instead of using this
# constant: 'lupdate' reads the source without executing it and silently skips a QT_TRANSLATE_NOOP whose
# context is a variable, so such a string never reaches the translation files. The constant is used on the
# display side only, where the value is resolved at run time.
TR_CONTEXT = "Preferences"


# ----------------------------------------------------------------------------------------------------------------------
# Types a user-editable setting may have. The type decides both how the value is read back from the 'settings'
# table (see the typed accessors of JalSettings) and which editor the preferences dialog builds for it.
class SettingType:
    String = 1
    Integer = 2
    Boolean = 3


# Describes one setting that the user may edit in the preferences dialog. The 'settings' table also holds values
# that are none of the user's business - the schema version, the rebuild flags, window geometry and view states.
# Those are simply never registered here, which is what keeps them out of the dialog: the dialog can only show
# what the registry knows, so there is no way to corrupt the database by editing a value that was never meant
# to be edited.
#
# 'page' and 'label' are stored untranslated and are translated when they are displayed - a descriptor is created
# at import time, long before the translator is installed. Wrap the literals in QT_TRANSLATE_NOOP("Preferences", ...)
# at the registration site so that they are collected into the translation files.
@dataclass
class SettingDescriptor:
    key: str                             # Name of the row in the 'settings' table
    page: str                            # Page of the preferences dialog this setting is shown at
    label: str                           # Text shown next to the editor
    type: int = SettingType.String
    default: object = ''
    tooltip: str = ''

    def translated_page(self) -> str:
        return QCoreApplication.translate(TR_CONTEXT, self.page)

    def translated_label(self) -> str:
        return QCoreApplication.translate(TR_CONTEXT, self.label)

    def translated_tooltip(self) -> str:
        return QCoreApplication.translate(TR_CONTEXT, self.tooltip) if self.tooltip else ''

    # Current value of the setting, typed according to the descriptor
    def value(self):
        settings = JalSettings()
        if self.type == SettingType.Boolean:
            return settings.getBool(self.key, bool(self.default))
        if self.type == SettingType.Integer:
            return settings.getInt(self.key, int(self.default))
        return settings.getStr(self.key, str(self.default))

    def set_value(self, value) -> None:
        JalSettings().setValue(self.key, value)


# ----------------------------------------------------------------------------------------------------------------------
# Holds every setting that the user may edit. Modules register the settings they own themselves, so that adding
# a new data source (a blockchain fetcher, a receipt API, a quote provider) doesn't require an edit of any central
# list or of the preferences dialog - it declares its settings next to the code that reads them.
# Pages are kept in registration order, which is why the module-level registrations at the bottom of this file
# define the order of the built-in pages.
class SettingsRegistry:
    _settings = []

    @classmethod
    def register(cls, descriptor: SettingDescriptor) -> None:
        if any(x.key == descriptor.key for x in cls._settings):
            raise ValueError(f"Setting '{descriptor.key}' is already registered")
        cls._settings.append(descriptor)

    # Names of the pages, in registration order, untranslated
    @classmethod
    def pages(cls) -> list:
        pages = []
        for setting in cls._settings:
            if setting.page not in pages:
                pages.append(setting.page)
        return pages

    @classmethod
    def settings_of_page(cls, page: str) -> list:
        return [x for x in cls._settings if x.page == page]


# ----------------------------------------------------------------------------------------------------------------------
# Built-in settings.
# The blockchain API keys below are declared here because the chain fetchers that consume them don't exist yet.
# Each of them moves into its fetcher module (as a SettingsRegistry.register() call next to the code that reads
# the key) as soon as that fetcher is written - the dialog picks it up from wherever it is registered.
def _register_builtin_settings() -> None:
    # Every displayed string goes through QT_TRANSLATE_NOOP so that 'lupdate' collects it: the strings are
    # translated later, at display time, and a bare literal here would never reach the translation files.
    # The context must stay a literal here - see the note at TR_CONTEXT above.
    SettingsRegistry.register(SettingDescriptor(
        key="ApiKey_TronGrid",
        page=QT_TRANSLATE_NOOP("Preferences", "Blockchain"),
        label=QT_TRANSLATE_NOOP("Preferences", "TronGrid API key"),
        tooltip=QT_TRANSLATE_NOOP("Preferences",
                                  "Required to fetch Tron (TRX/TRC-20) transactions. A free key allows 15 requests "
                                  "per second and 100000 requests per day; without a key TronGrid rejects almost "
                                  "every request.")))
    SettingsRegistry.register(SettingDescriptor(
        key="TokenDustThreshold",
        page=QT_TRANSLATE_NOOP("Preferences", "Blockchain"),
        label=QT_TRANSLATE_NOOP("Preferences", "Dust airdrop threshold"), default='1',
        tooltip=QT_TRANSLATE_NOOP("Preferences",
                                  "An incoming token transfer that is worth less than this value in account "
                                  "currency, and comes from an address you never dealt with, is treated as an "
                                  "unsolicited airdrop and is not imported.")))


_register_builtin_settings()
