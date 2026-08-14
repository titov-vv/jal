import os
import pytest
import xml.etree.ElementTree as ET

from tests.fixtures import project_root, data_path, prepare_db
from jal.widgets.helpers import menu_label, menu_mnemonic, sort_menu_items
from jal.reports.reports import Reports
from jal.data_import.statements import Statements
from jal.net.chain_fetchers.fetchers import ChainFetchers


# ----------------------------------------------------------------------------------------------------------------------
# Two items of one menu that declare the same access key leave that key cycling between them instead of activating
# one of them - a menu stays usable but stops being operable from the keyboard. Nothing in Qt reports it, and the
# labels involved are spread over main_window.ui and ~28 separately translated modules, so it is checked here.
#
# Only the English source strings are seen by these tests. A translation introduces its own set of access keys and
# can collide on its own; there the same guarantee has to come from whoever maintains the .ts files.
def duplicate_mnemonics(labels: list) -> list:
    seen, duplicates = {}, []
    for label in labels:
        key = menu_mnemonic(label)
        if not key:
            continue
        if key in seen:
            duplicates.append(f"'{key}': {seen[key]} <> {menu_label(label)}")
        else:
            seen[key] = menu_label(label)
    return duplicates


# Returns {menu title: [labels of its items]} for every menu declared in main_window.ui, plus the menu bar itself
# under the '<menu bar>' key. Submenus appear both as an item of their parent and as a menu of their own.
def main_menu_structure(project_root) -> dict:
    root = ET.parse(os.path.join(project_root, 'jal', 'ui', 'main_window.ui')).getroot()
    window = root.find('widget')
    texts = {action.get('name'): action.find('property/string').text for action in root.iter('action')}
    for menu in window.iter('widget'):
        if menu.get('class') == 'QMenu':
            texts[menu.get('name')] = menu.find('property[@name="title"]/string').text

    structure = {}
    for menu in window.iter('widget'):
        if menu.get('class') not in ('QMenu', 'QMenuBar'):
            continue
        title = '<menu bar>' if menu.get('class') == 'QMenuBar' else texts[menu.get('name')]
        structure[menu_label(title)] = [texts[item.get('name')] for item in menu.findall('addaction')
                                        if item.get('name') != 'separator']
    return structure


def test_static_menus_have_unique_mnemonics(project_root):
    for title, labels in main_menu_structure(project_root).items():
        assert duplicate_mnemonics(labels) == [], f"in menu '{title}'"


def test_every_static_menu_item_declares_a_mnemonic(project_root):
    for title, labels in main_menu_structure(project_root).items():
        without = [menu_label(x) for x in labels if not menu_mnemonic(x)]
        assert without == [], f"in menu '{title}'"


# ----------------------------------------------------------------------------------------------------------------------
# The same two guarantees for the menus that are built at run time from whatever modules are installed
@pytest.fixture
def module_menus(prepare_db):   # a blockchain fetcher reads an account from the database as it is constructed
    reports = Reports(None, None).items
    groups = {x['group'] for x in reports if x['group']}
    menus = {'Import->Statement': [x['name'] for x in Statements(None).items],
             'Import->Blockchain': [x['name'] for x in ChainFetchers(None).items],
             'Reports': [x['name'] for x in reports if not x['group']] + sorted(groups)}
    for group in groups:
        menus[f"Reports->{menu_label(group)}"] = [x['name'] for x in reports if x['group'] == group]
    yield menus


def test_module_menus_have_unique_mnemonics(module_menus):
    for title, labels in module_menus.items():
        assert duplicate_mnemonics(labels) == [], f"in menu '{title}'"


def test_every_module_menu_item_declares_a_mnemonic(module_menus):
    for title, labels in module_menus.items():
        without = [menu_label(x) for x in labels if not menu_mnemonic(x)]
        assert without == [], f"in menu '{title}'"


# A grouped report must never sort in between the ungrouped ones: the group submenus are appended to the menu after
# every plain entry, and a group that sorted earlier would drag its submenu into the middle of the list - at a
# position that changes with the language, because the sort is on the translated name.
def test_grouped_reports_sort_after_ungrouped_ones(project_root):
    grouped = [bool(report['group']) for report in Reports(None, None).items]
    assert grouped == sorted(grouped)


# A mnemonic marker must not move an item. '&' sorts ahead of every letter, so ordering the raw labels would drop
# 'K&uCoin' behind 'VTB Investments' instead of leaving it next to 'KIT Finance'.
def test_menu_items_sort_by_what_is_displayed(project_root):
    labels = ["&VTB Investments", "K&uCoin", "&KIT Finance", "&Bitget", "A&valanche", "&arbitrum"]
    ordered = [menu_label(x) for x in sort_menu_items(labels, lambda label: label)]
    assert ordered == ["arbitrum", "Avalanche", "Bitget", "KIT Finance", "KuCoin", "VTB Investments"]


# ----------------------------------------------------------------------------------------------------------------------
def test_mnemonic_helpers():
    assert menu_label("&Income && spending") == "Income & spending"
    assert menu_mnemonic("&Income && spending") == 'I'
    assert menu_label("P&&L &by account") == "P&L by account"
    assert menu_mnemonic("P&&L &by account") == 'B'
    assert menu_mnemonic("P&&L") == ''          # only a literal ampersand, no access key
    assert menu_label("Deposits") == "Deposits" and menu_mnemonic("Deposits") == ''
    assert menu_mnemonic("Trailing marker &") == ''
