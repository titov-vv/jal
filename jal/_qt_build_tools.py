"""Locate Qt6's uic/lupdate/lrelease across platforms for compile_ui / compile_translations.

This file might not cover all possible options, it was created for a particular setup.
So it is a subject of extention/improvement if required.
"""
import re
import shutil
import subprocess

_LINUX_QT6_DIRS = ("/usr/lib/qt6", "/usr/lib/qt6/bin", "/usr/lib64/qt6", "/usr/lib64/qt6/bin")
_QT6_VERSION = re.compile(r"\b6\.\d+(\.\d+)?\b")


def _is_qt6(path):
    try:
        out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return bool(_QT6_VERSION.search(out.stdout + out.stderr))


def find_qt_tool(pyside6_name, qt_name):
    """Return a path to a verified Qt 6.x tool: <pyside6_name> from PATH if present,
    else <qt_name> under a known Qt6 install directory, else <qt_name> from PATH -
    each candidate is only accepted once its own '-version' output confirms Qt 6.x."""
    candidates = []
    wrapper = shutil.which(pyside6_name)
    if wrapper:
        candidates.append(wrapper)
    candidates += [f"{qt_dir}/{qt_name}" for qt_dir in _LINUX_QT6_DIRS]
    on_path = shutil.which(qt_name)
    if on_path:
        candidates.append(on_path)

    for candidate in candidates:
        if _is_qt6(candidate):
            return candidate
    raise SystemExit(
        f"Could not find a Qt 6.x '{qt_name}'. Tried '{pyside6_name}' on PATH, "
        f"Qt6 install directories, and '{qt_name}' on PATH. Install PySide6 via pip "
        f"(bundles {pyside6_name}) or the system qt6-tools package."
    )
