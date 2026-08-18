import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pathlib
import xml.etree.ElementTree as ET

import pytest

from jal.widgets.helpers import menu_mnemonic

UI_ROOT = pathlib.Path(__file__).resolve().parent.parent / "jal" / "ui"
LANGUAGES = UI_ROOT.parent / "languages"


# Every form declares its buddy links, but a buddy only becomes an Alt+letter jump once the label text marks the
# letter with '&'. The letters are chosen per form, which is as far as the guarantee can go: the main window keeps
# several MDI children alive at once and a duplicate between two of them does not cycle - the later one simply
# wins and the earlier label stops answering. Inside one form nothing may collide, and no form shown inside the
# main window may take a letter the menu bar already answers to.
MENU_BAR_LETTERS = set("LDIRTSH")            # &Ledger &Data &Import &Reports &Tax &Settings &Help
MENU_BAR_LETTERS_RU = set("НДОИ") | set("LTH")   # &Ledger, &Tax and &Help have no Russian translation yet


def _in_main_window(relative):
    return (relative.parts[0] in ("widgets", "reports")
            or relative.name in ("operations_widget.ui", "tax_export_widget.ui",
                                 "flow_export_widget.ui", "main_window.ui"))


# A label whose text holds no letter to spare. The four '#' columns have no letter at all; the other two ran out
# of them - every letter they could have used was already taken inside their own form.
NO_LETTER_LEFT = {("AssetPaymentOperation", "#"), ("AssetPaymentOperation", "Ex-Date"),
                  ("BridgeOperation", "To"), ("CorporateActionOperation", "#"),
                  ("TradeOperation", "#"), ("TransferOperation", "#")}
NO_RUSSIAN_LETTER_LEFT = {("AssetPaymentOperation", "№"), ("AssetPaymentOperation", "Дивиденд"),
                          ("CorporateActionOperation", "№"), ("TradeOperation", "№"),
                          ("TransferOperation", "№"), ("TransferOperation", "С")}


def _forms():
    for path in sorted(UI_ROOT.rglob("*.ui")):
        yield pytest.param(path, id=str(path.relative_to(UI_ROOT)))


def _texts(path):
    """(context, buddy labels with their text, every other text that claims a letter) for one form."""
    root = ET.parse(path).getroot()
    labels, others = [], []
    for widget in root.iter("widget"):
        text = widget.find('./property[@name="text"]/string')
        if text is None or not text.text:
            continue
        if widget.get("class") == "QLabel" and widget.find('./property[@name="buddy"]/cstring') is not None:
            labels.append(text.text)
        elif menu_mnemonic(text.text):
            others.append(text.text)
    return root.find("class").text, labels, others


@pytest.mark.parametrize("path", list(_forms()))
def test_no_two_widgets_in_a_form_claim_the_same_letter(path):
    context, labels, others = _texts(path)
    claimed = {}
    for text in labels + others:
        letter = menu_mnemonic(text)
        if not letter:
            continue
        assert letter not in claimed, f"{path.name}: {text!r} and {claimed[letter]!r} both answer to Alt+{letter}"
        claimed[letter] = text


@pytest.mark.parametrize("path", list(_forms()))
def test_forms_in_the_main_window_leave_the_menu_bar_its_letters(path):
    if not _in_main_window(path.relative_to(UI_ROOT)) or path.name == "main_window.ui":
        pytest.skip("not shown inside the main window")
    _context, labels, _others = _texts(path)
    for text in labels:
        letter = menu_mnemonic(text)
        assert letter not in MENU_BAR_LETTERS, \
            f"{path.name}: {text!r} takes Alt+{letter}, which opens a menu instead"


@pytest.mark.parametrize("path", list(_forms()))
def test_every_buddy_label_marks_a_letter(path):
    context, labels, _others = _texts(path)
    unmarked = [text for text in labels if not menu_mnemonic(text)]
    assert all((context, text) in NO_LETTER_LEFT for text in unmarked), \
        f"{path.name}: {[t for t in unmarked if (context, t) not in NO_LETTER_LEFT]} lost their access key"


# ----------------------------------------------------------------------------------------------------------------------
# The '&' travels inside the source string, so the Russian text needs its own letter - and it is a different
# alphabet, so nothing about the English choice carries over. These translations were derived mechanically from
# the ones that were already there, and this is what keeps that derivation honest.
def _russian():
    translations = {}
    for context in ET.parse(LANGUAGES / "ru.ts").getroot().iter("context"):
        name = context.find("name").text
        for message in context.iter("message"):
            source, translation = message.find("source"), message.find("translation")
            if source is not None and source.text and translation is not None and translation.text:
                translations[(name, source.text)] = translation.text
    return translations


@pytest.mark.parametrize("path", list(_forms()))
def test_the_russian_labels_carry_a_letter_of_their_own(path):
    context, labels, others = _texts(path)
    translations = _russian()
    claimed, in_window = {}, _in_main_window(path.relative_to(UI_ROOT))
    for text in labels + others:
        russian = translations.get((context, text))
        if russian is None:
            continue
        letter = menu_mnemonic(russian)
        if not letter:
            assert (context, russian) in NO_RUSSIAN_LETTER_LEFT, \
                f"{path.name}: russian {russian!r} for {text!r} lost its access key"
            continue
        assert letter not in claimed, \
            f"{path.name}: russian {russian!r} and {claimed[letter]!r} both answer to Alt+{letter}"
        claimed[letter] = russian
        if in_window and path.name != "main_window.ui" and text in labels:
            assert letter not in MENU_BAR_LETTERS_RU, \
                f"{path.name}: russian {russian!r} takes Alt+{letter}, which opens a menu instead"
