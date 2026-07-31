from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton
from jal.widgets.helpers import center_window


# ----------------------------------------------------------------------------------------------------------------------
# Asked when a token fetched from a blockchain has no contract-address match in the database - a token JAL has never
# seen on this chain. It may be a coin the user already holds (the same token on another chain, or one RENAMED on this
# chain, as Tether's 'USDT' is called 'USD₮0' on Arbitrum), a genuinely new coin, or a scam. Only the user can tell,
# so the choice is made here, once per new token.
#
# 'candidates' is the full list of (asset_id, label) tuples the token could be merged into, best first, of which the
# leading 'suggested' ones resemble it by ticker. The rest are there because a resemblance is a suggestion and not a
# filter: a coin renamed on one chain resembles nothing, and a chooser that only offered the resemblances left the
# user with no way to say what the token really was. The search box is what makes a list of that length usable.
#
# The outcome is read from .action / .target_asset_id after exec().
class SelectTokenActionDialog(QDialog):
    Merge, CreateNew, Discard = 1, 2, 3

    def __init__(self, name: str, ticker: str, chain: str, address: str, candidates: list, suggested: int = 0):
        super().__init__()
        self.action = self.CreateNew
        self._candidates = candidates
        self._suggested = suggested
        self.target_asset_id = candidates[0][0] if candidates else 0
        self.setWindowTitle(self.tr("New crypto token"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("A token found on-chain isn't one this database knows:")))
        info = f"<b>{ticker}</b>"
        if name:
            info += f" — {name}"
        info += f"<br>{self.tr('Chain')}: {chain}<br>{self.tr('Address')}: {address}"
        info_label = QLabel(info)
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(info_label)

        layout.addWidget(QLabel(self.tr("Merge it into this existing asset, if it is one you already have:")))
        self.search = QLineEdit(self)
        self.search.setPlaceholderText(self.tr("Search by name or ticker..."))
        self.search.textChanged.connect(self._filter_candidates)
        layout.addWidget(self.search)
        self.candidate_combo = QComboBox(self)
        layout.addWidget(self.candidate_combo)
        self._fill_candidates('')

        buttons = QHBoxLayout()
        merge_button = QPushButton(self.tr("Merge"), self)
        create_button = QPushButton(self.tr("Create new asset"), self)
        discard_button = QPushButton(self.tr("Discard (blacklist)"), self)
        merge_button.clicked.connect(self._on_merge)
        create_button.clicked.connect(self._on_create)
        discard_button.clicked.connect(self._on_discard)
        buttons.addWidget(merge_button)
        buttons.addWidget(create_button)
        buttons.addWidget(discard_button)
        layout.addLayout(buttons)

        center_window(self)

    # The candidates whose label matches what has been typed, keeping the order they were given in - the ones that
    # resemble the token by ticker stay at the top, where they are the answer most of the time.
    def _fill_candidates(self, text: str) -> None:
        self.candidate_combo.clear()
        text = text.strip().lower()
        for index, (asset_id, label) in enumerate(self._candidates):
            if text and text not in label.lower():
                continue
            # A suggestion is marked as such rather than being silently first: what puts it there is a resemblance
            # between two tickers, which is a hint about this token and not a statement about it
            mark = self.tr(" (similar ticker)") if index < self._suggested else ''
            self.candidate_combo.addItem(label + mark, asset_id)

    @Slot(str)
    def _filter_candidates(self, text: str) -> None:
        self._fill_candidates(text)

    def _on_merge(self):
        self.action = self.Merge
        self.target_asset_id = self.candidate_combo.currentData()
        if not self.target_asset_id:
            self.action = self.CreateNew   # nothing is selected to merge into, so there is nothing to merge
        self.accept()

    def _on_create(self):
        self.action = self.CreateNew
        self.accept()

    def _on_discard(self):
        self.action = self.Discard
        self.accept()
