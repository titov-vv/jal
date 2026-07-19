import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from decimal import Decimal

import pytest

from tests.fixtures import project_root, data_path, prepare_db
from jal.db.settings import JalSettings
from jal.db.settings_registry import SettingsRegistry, SettingDescriptor, SettingType
from jal.data_import.token_filter import TokenFilter
from jal.widgets.preferences_dialog import PreferencesDialog


# ----------------------------------------------------------------------------------------------------------------------
def test_typed_settings_accessors(prepare_db):
    settings = JalSettings()

    # A value that consists of digits only must stay a string - an API key is the case that matters here,
    # as the untyped getValue() below reports it as an int.
    settings.setValue('TestApiKey', '9876543210')
    assert settings.getStr('TestApiKey') == '9876543210'
    assert settings.getValue('TestApiKey') == 9876543210      # Legacy behaviour, kept for existing callers

    settings.setValue('TestNumber', 42)
    assert settings.getInt('TestNumber') == 42
    assert settings.getStr('TestNumber') == '42'

    # bool is a subclass of int and would be stored as 'True' without an explicit conversion in setValue()
    settings.setValue('TestFlag', True)
    assert settings.getStr('TestFlag') == '1'
    assert settings.getBool('TestFlag')
    settings.setValue('TestFlag', False)
    assert not settings.getBool('TestFlag')

    # Defaults are returned for a key that doesn't exist. getValue() used to raise TypeError on int(None) here.
    assert settings.getValue('NoSuchKey') is None
    assert settings.getValue('NoSuchKey', 'fallback') == 'fallback'
    assert settings.getStr('NoSuchKey', 'fallback') == 'fallback'
    assert settings.getInt('NoSuchKey', 7) == 7
    assert settings.getBool('NoSuchKey', True)

    # A value that doesn't convert to the requested type gives the default instead of raising, so that a
    # settings table edited by hand can't stop the application from starting.
    settings.setValue('TestBroken', 'not-a-number')
    assert settings.getInt('TestBroken', 5) == 5
    assert not settings.getBool('TestBroken')


def test_settings_registry():
    # Every registered setting has a page, and pages keep their registration order
    assert 'Blockchain' in SettingsRegistry.pages()
    keys = [x.key for x in SettingsRegistry.settings_of_page('Blockchain')]
    assert 'ApiKey_TronGrid' in keys
    assert 'TokenDustThreshold' in keys

    # A key may be registered once only - a silently ignored second registration would mean two editors
    # writing to the same row
    with pytest.raises(ValueError):
        SettingsRegistry.register(SettingDescriptor(key='ApiKey_TronGrid', page='Blockchain', label='Duplicate'))

    # Internal values are deliberately absent, so the dialog can't be used to corrupt the database
    all_keys = [x.key for page in SettingsRegistry.pages() for x in SettingsRegistry.settings_of_page(page)]
    for internal in ['SchemaVersion', 'RebuildDB', 'CleanDB', 'WindowGeometry', 'WindowState']:
        assert internal not in all_keys


def test_preferences_dialog_roundtrip(prepare_db):
    dialog = PreferencesDialog()
    # One list entry per registered page, and the stack is kept in sync with the list
    assert dialog.ui.PagesList.count() == len(SettingsRegistry.pages())
    assert dialog.ui.PagesStack.count() == dialog.ui.PagesList.count()
    assert 'ApiKey_TronGrid' in dialog._editors

    # Surrounding whitespace of a pasted API key must not be stored
    dialog._editors['ApiKey_TronGrid'].setText('  1234567890  ')
    dialog._editors['TokenDustThreshold'].setText('2.5')
    dialog.accept()
    assert JalSettings().getStr('ApiKey_TronGrid') == '1234567890'

    # A reopened dialog shows what was stored (the dialog is kept in a variable on purpose - an unreferenced
    # one is garbage collected together with its C++ widgets while it is still being examined)
    reopened = PreferencesDialog()
    assert reopened._editors['ApiKey_TronGrid'].text() == '1234567890'

    # 'Cancel' discards the edits instead of writing them
    cancelled = PreferencesDialog()
    cancelled._editors['ApiKey_TronGrid'].setText('DISCARDED')
    cancelled.reject()
    assert JalSettings().getStr('ApiKey_TronGrid') == '1234567890'


def test_dust_threshold_setting_reaches_filter(prepare_db):
    # Default of the descriptor applies while the user hasn't set anything
    assert TokenFilter(lists=None)._dust_threshold == Decimal('1')

    JalSettings().setValue('TokenDustThreshold', '2.5')
    assert TokenFilter(lists=None)._dust_threshold == Decimal('2.5')

    # An explicit argument still wins over the setting (that is what the tests of TokenFilter rely on)
    assert TokenFilter(lists=None, dust_threshold=Decimal('7'))._dust_threshold == Decimal('7')

    # A broken setting falls back to the built-in default rather than breaking every import
    JalSettings().setValue('TokenDustThreshold', 'not-a-number')
    assert TokenFilter(lists=None)._dust_threshold == Decimal('1')
