import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import glob
import xml.etree.ElementTree as xml_tree

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QWidget, QVBoxLayout, QDateEdit, QDateTimeEdit

from tests.fixtures import project_root, data_path, prepare_db
from tests.helpers import d2t, dt2t
from jal.db.settings import JalSettings
from jal.db.settings_registry import SettingsRegistry, SettingType
from jal.widgets.delegates import TimestampDelegate
from jal.widgets.helpers import DateFormat, ts2d, ts2dt, set_date_formats, refresh_date_formats
from jal.widgets.preferences_dialog import PreferencesDialog
from jal.data_export.xlsx import XLSX, TAX_REPORT_DATE_FORMAT


# Every widget built here gets a parent: a parentless one is collected by the cyclic collector at a moment
# unrelated to the test that made it, and takes the process down with it.
@pytest.fixture
def parent(prepare_db):
    holder = QWidget()
    yield holder
    holder.deleteLater()


def _select(layout_id):
    JalSettings().setValue(DateFormat.SETTINGS_KEY, layout_id)
    DateFormat.invalidate()


# A form as the .ui files declare it: the day-first layout is the design-time value of every date editor
def _form(parent):
    form = QWidget(parent)
    layout = QVBoxLayout(form)
    date = QDateEdit(form)
    date.setDisplayFormat("dd/MM/yyyy")
    layout.addWidget(date)
    moment = QDateTimeEdit(form)
    moment.setDisplayFormat("dd/MM/yyyy hh:mm:ss")
    layout.addWidget(moment)
    return form, date, moment


# ----------------------------------------------------------------------------------------------------------------------
# The 31st of December 2026 is the date that tells the five layouts apart in every position
def test_every_layout_renders_the_same_day(prepare_db):
    timestamp = d2t(261231)
    expected = {
        DateFormat.EU: '31/12/2026',
        DateFormat.EU_SHORT: '31/12/26',
        DateFormat.US: '12/31/2026',
        DateFormat.US_SHORT: '12/31',
        DateFormat.ISO: '2026-12-31'
    }
    for layout, text in expected.items():
        _select(layout)
        assert ts2d(timestamp) == text
        assert ts2dt(dt2t(2612312359)) == text + ' 23:59:00'


def test_default_layout_is_day_first_and_a_broken_setting_doesnt_change_it(prepare_db):
    assert DateFormat.current() == DateFormat.EU     # nothing stored yet

    JalSettings().setValue(DateFormat.SETTINGS_KEY, 42)      # not a layout at all
    DateFormat.invalidate()
    assert DateFormat.current() == DateFormat.EU
    JalSettings().setValue(DateFormat.SETTINGS_KEY, 'nonsense')
    DateFormat.invalidate()
    assert DateFormat.current() == DateFormat.EU


# ----------------------------------------------------------------------------------------------------------------------
def test_editors_of_a_form_take_the_chosen_layout(parent):
    _select(DateFormat.ISO)
    form, date, moment = _form(parent)
    set_date_formats(form)
    assert date.displayFormat() == 'yyyy-MM-dd'
    assert moment.displayFormat() == 'yyyy-MM-dd hh:mm:ss'     # the time part is left as it is

    # The rewrite reads its own output as well as the design-time value, so switching layouts twice works
    _select(DateFormat.US)
    set_date_formats(form)
    assert date.displayFormat() == 'MM/dd/yyyy'
    assert moment.displayFormat() == 'MM/dd/yyyy hh:mm:ss'
    _select(DateFormat.EU_SHORT)
    set_date_formats(form)
    assert date.displayFormat() == 'dd/MM/yy'


# 'dd/MM/yyyy' starts with 'dd/MM/yy' and 'MM/dd/yyyy' with 'MM/dd', so a careless replacement would leave
# a stray year behind ('dd/MM/yyyy' -> 'dd/MM/yyyy' + 'yy')
def test_a_four_digit_year_is_not_taken_for_a_two_digit_one(prepare_db):
    _select(DateFormat.EU_SHORT)
    assert DateFormat.localized('dd/MM/yyyy') == 'dd/MM/yy'
    _select(DateFormat.US_SHORT)
    assert DateFormat.localized('dd/MM/yyyy hh:mm') == 'MM/dd/yyyy hh:mm'   # an editor keeps the year
    _select(DateFormat.EU)
    assert DateFormat.localized('MM/dd/yyyy') == 'dd/MM/yyyy'
    assert DateFormat.localized('a format with no date in it') == 'a format with no date in it'


# Every date editor declared in a .ui file has to be one that set_date_formats() recognizes - a new form that
# declares its dates in some other way would silently keep the day-first layout for good.
def test_every_declared_display_format_is_one_of_the_layouts(project_root):
    known = [layout[0] for layout in DateFormat.LAYOUTS.values()]
    declared = []
    for ui_file in glob.glob(project_root + '/jal/ui/**/*.ui', recursive=True):
        for element in xml_tree.parse(ui_file).getroot().iter('property'):
            if element.get('name') == 'displayFormat':
                declared.append((os.path.basename(ui_file), element.find('string').text))
    assert declared      # the files do declare formats, so the check above is not vacuous
    for file_name, display_format in declared:
        assert any(pattern in display_format for pattern in known), f"{file_name}: {display_format}"


# ----------------------------------------------------------------------------------------------------------------------
def test_timestamp_delegate_follows_the_setting(prepare_db):
    locale = QLocale()
    moment = TimestampDelegate()
    day = TimestampDelegate(date_only=True)
    _select(DateFormat.US)
    assert day.displayText(d2t(261231), locale) == '12/31/2026'
    assert moment.displayText(dt2t(2612311015), locale) == '12/31/2026 10:15:00'

    # The layout is read per cell, so a delegate built before the change shows the new one
    _select(DateFormat.ISO)
    assert day.displayText(d2t(261231), locale) == '2026-12-31'
    assert moment.displayText(dt2t(2612311015), locale) == '2026-12-31 10:15:00'
    assert day.displayText(0, locale) == ''                      # an empty date stays empty


def test_delegate_editor_matches_what_it_edits(parent):
    _select(DateFormat.ISO)
    editor = TimestampDelegate(date_only=True).createEditor(parent, None, None)
    assert editor.displayFormat() == 'yyyy-MM-dd'
    editor = TimestampDelegate().createEditor(parent, None, None)
    assert editor.displayFormat() == 'yyyy-MM-dd hh:mm:ss'


# ----------------------------------------------------------------------------------------------------------------------
def test_the_layout_is_offered_as_a_choice_in_preferences(parent):
    setting = [x for x in SettingsRegistry.settings_of_page('Interface') if x.key == DateFormat.SETTINGS_KEY]
    assert len(setting) == 1
    assert setting[0].type == SettingType.Choice
    assert [value for value, label in setting[0].options] == list(DateFormat.LAYOUTS.keys())

    dialog = PreferencesDialog(parent=parent)
    editor = dialog._editors[DateFormat.SETTINGS_KEY]
    assert editor.count() == len(DateFormat.LAYOUTS)
    assert editor.currentData() == DateFormat.EU            # the default, as nothing is stored yet
    editor.setCurrentIndex(editor.findData(DateFormat.ISO))
    dialog.accept()
    assert JalSettings().getInt(DateFormat.SETTINGS_KEY) == DateFormat.ISO


# A change of the layout is visible without a restart: open editors are rewritten in place
def test_open_editors_follow_a_change_of_the_preference(parent):
    _select(DateFormat.EU)
    form, date, moment = _form(parent)
    set_date_formats(form)
    assert date.displayFormat() == 'dd/MM/yyyy'

    JalSettings().setValue(DateFormat.SETTINGS_KEY, DateFormat.ISO)
    refresh_date_formats()
    assert date.displayFormat() == 'yyyy-MM-dd'
    assert moment.displayFormat() == 'yyyy-MM-dd hh:mm:ss'
    assert ts2d(d2t(261231)) == '2026-12-31'


# ----------------------------------------------------------------------------------------------------------------------
# The tax report is read by an authority that expects the layout of its own country, not by the user who set a
# preference, so the 'D' format of the report templates stays day-first whatever the interface shows.
def test_tax_report_dates_ignore_the_preference(prepare_db, tmp_path):
    _select(DateFormat.US_SHORT)
    report = XLSX(str(tmp_path / 'tax.xlsx'))
    value, _ = report.apply_format(d2t(261231), 'D')
    assert value == '31/12/2026'
    assert TAX_REPORT_DATE_FORMAT == '%d/%m/%Y'
    report.save()
