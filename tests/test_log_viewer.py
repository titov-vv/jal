import logging

from tests.fixtures import project_root
from jal.widgets.custom.log_viewer import LogViewer


# Reads back the color and the weight every line of the log pane is drawn with
def _line_formats(viewer) -> list:
    formats = []
    block = viewer.document().begin()
    while block.isValid():
        for iterator in block:
            fragment = iterator.fragment()
            if fragment.isValid():
                formats.append((fragment.charFormat().foreground().color().name(),
                                fragment.charFormat().fontWeight()))
        block = block.next()
    return formats


# A line keeps the color it was logged with even if the user has selected the text of the pane, e.g. to copy it
def test_selection_keeps_message_colors(project_root):
    viewer = LogViewer()
    viewer.displayMessage(logging.CRITICAL, "Database schema is newer than this version")
    viewer.displayMessage(logging.ERROR, "Failed to download quotes from Stooq")
    logged = _line_formats(viewer)
    assert len(logged) == 2
    assert logged[0] != logged[1]     # a critical message is bold, an error is not

    viewer.selectAll()
    viewer.displayMessage(logging.WARNING, "No quote for AAPL on 01/03/2021")
    assert _line_formats(viewer)[:2] == logged
