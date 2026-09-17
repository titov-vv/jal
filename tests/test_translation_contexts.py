# A string may be translated in 'ru.ts' and still reach the user in English: 'lupdate' reads the source without
# running it and files a string under the context it SEES (the enclosing class for self.tr, the literal name for
# X.tr), while the code asks for the context its tr() hard-codes. Qt has no fallback between contexts - it answers
# with the source text - and 'lrelease' reports nothing wrong, so the whole family of classes that carry their own
# tr() (LedgerTransaction, JalDB, ReceiptAPI, TaxReport, ...) went untranslated for releases without a sign.
#
# These tests are that missing sign. They compare what 'lupdate' would collect with what the code looks up, and
# they guard the two other ways a string goes missing quietly: hidden inside an f-string, and stored with an empty
# translation that is not marked unfinished.
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import importlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from PySide6.QtWidgets import QApplication

JAL_DIR = Path(__file__).resolve().parent.parent / "jal"


def _sources():
    return sorted(p for p in JAL_DIR.rglob("*.py") if "__pycache__" not in p.parts)


# Every tr() call with a literal string, and every context a 'def tr' hard-codes, as the source states them.
def _parse():
    tr_contexts = {}    # (module, class) -> the context its own tr() passes to QApplication.translate()
    calls = []          # (file, line, module, enclosing class, what was named before '.tr', the string)
    f_string_calls = []
    for path in _sources():
        module = str(path.relative_to(JAL_DIR.parent)).replace(os.sep, ".")[:-3]
        tree = ast.parse(path.read_text(), str(path))
        stack = []

        class Visitor(ast.NodeVisitor):
            def visit_ClassDef(self, node):
                stack.append(node.name)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "tr":
                        for inner in ast.walk(item):
                            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                                    and inner.func.attr == "translate" and inner.args \
                                    and isinstance(inner.args[0], ast.Constant):
                                tr_contexts[(module, node.name)] = inner.args[0].value
                self.generic_visit(node)
                stack.pop()

            def visit_JoinedStr(self, node):   # an f-string: lupdate does not look inside one
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                            and inner.func.attr == "tr" and inner.args \
                            and isinstance(inner.args[0], ast.Constant) and isinstance(inner.args[0].value, str):
                        f_string_calls.append((path, inner.lineno, inner.args[0].value))
                self.generic_visit(node)

            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "tr" and node.args \
                        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) \
                        and isinstance(node.func.value, ast.Name) and stack:
                    calls.append((path, node.lineno, module, stack[-1], node.func.value.id, node.args[0].value))
                self.generic_visit(node)

        Visitor().visit(tree)
    return tr_contexts, calls, f_string_calls


# The context this class really asks for: the first tr() in its MRO decides, and a class that inherits Qt's own
# answers under its own name.
def _runtime_context(cls, tr_contexts):
    for base in cls.__mro__:
        if "tr" in base.__dict__:
            return tr_contexts.get((base.__module__, base.__name__)) or cls.__name__
    return cls.__name__


@pytest.fixture(scope="module")
def audit():
    _ = QApplication.instance() or QApplication([])
    tr_contexts, calls, f_string_calls = _parse()
    resolved, unimportable = {}, set()
    for _path, _line, module, cls_name, holder, _text in calls:
        named = holder if holder not in ("self", "cls") else cls_name
        for wanted in (named, cls_name):
            if (module, wanted) in resolved or (module, wanted) in unimportable:
                continue
            try:
                cls = getattr(importlib.import_module(module), wanted)
            except Exception:      # an optional dependency, or a name imported from elsewhere - not this test's job
                unimportable.add((module, wanted))
                continue
            resolved[(module, wanted)] = _runtime_context(cls, tr_contexts)
    return calls, resolved, f_string_calls


# What lupdate collects has to be what the code looks up. 'cls.tr(...)' is the worst of these: lupdate files the
# string under the literal context "cls", which nothing ever asks for.
def test_a_string_is_collected_under_the_context_it_is_looked_up_in(audit):
    calls, resolved, _f_strings = audit
    mismatched = []
    for path, line, module, cls_name, holder, text in calls:
        named = holder if holder not in ("self", "cls") else cls_name
        runtime = resolved.get((module, named))
        if runtime is None:
            continue
        collected = "cls" if holder == "cls" else named
        if collected != runtime:
            mismatched.append(f"{path.name}:{line} {holder}.tr({text[:40]!r}) is collected under '{collected}' "
                              f"but looked up in '{runtime}' - name the class that owns the context")
    assert mismatched == []


# lupdate never sees a tr() written inside an f-string, so the string reaches no .ts file at all
def test_no_tr_call_hides_inside_an_f_string(audit):
    _calls, _resolved, f_string_calls = audit
    hidden = [f"{path.name}:{line} tr({text[:40]!r}) - name it before the f-string" for path, line, text in f_string_calls]
    assert hidden == []


# An empty translation that is NOT marked unfinished counts as finished: lrelease reports a complete file and the
# user gets the English source. The two below are deliberate - they read the same in both languages.
TRANSLATED_AS_IS = (" - ", "+351---")


# Every language but the one the strings are written in - 'en.ts' is the source itself, where an empty translation
# IS the translation (its own header states en_US as both the language and the source language).
def _translated_languages():
    for path in sorted((JAL_DIR / "languages").glob("*.ts")):
        root = ET.parse(path).getroot()
        if root.get("language") != root.get("sourcelanguage"):
            yield path.stem


@pytest.mark.parametrize("language", list(_translated_languages()))
def test_no_translation_is_empty_and_marked_finished(language):
    root = ET.parse(JAL_DIR / "languages" / f"{language}.ts").getroot()
    silent = []
    for context in root.findall("context"):
        for message in context.findall("message"):
            translation = message.find("translation")
            if translation is None or translation.get("type") == "unfinished":
                continue    # an honest "not translated yet" - this test is about the ones that claim to be done
            if not (translation.text or "") and message.findtext("source") not in TRANSLATED_AS_IS:
                silent.append(f"{context.findtext('name')}: {message.findtext('source')[:60]!r}")
    assert silent == []
