from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
from jal.widgets.helpers import center_window


# ----------------------------------------------------------------------------------------------------------------------
# Asked when a token fetched from a blockchain has no contract-address match in the database but reuses a ticker that
# a known crypto asset already carries. The two may be the same token on different chains (e.g. USDT on Ethereum and on
# Tron) or two unrelated coins that merely share a ticker - only the user can tell, so the choice is made here, once
# per new token. 'candidates' is a list of (asset_id, label) tuples describing the existing crypto assets that share
# the ticker; the selected one is the merge target. The outcome is read from .action / .target_asset_id after exec().
class SelectTokenActionDialog(QDialog):
    Merge, CreateNew, Discard = 1, 2, 3

    def __init__(self, name: str, ticker: str, chain: str, address: str, candidates: list):
        super().__init__()
        self.action = self.CreateNew
        self.target_asset_id = candidates[0][0] if candidates else 0
        self.setWindowTitle(self.tr("New crypto token"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr("A token found on-chain shares a ticker with an asset you already have:")))
        info = f"<b>{ticker}</b>"
        if name:
            info += f" — {name}"
        info += f"<br>{self.tr('Chain')}: {chain}<br>{self.tr('Address')}: {address}"
        info_label = QLabel(info)
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(info_label)

        layout.addWidget(QLabel(self.tr("Merge it into this existing asset:")))
        self.candidate_combo = QComboBox(self)
        for asset_id, label in candidates:
            self.candidate_combo.addItem(label, asset_id)
        layout.addWidget(self.candidate_combo)

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

    def _on_merge(self):
        self.action = self.Merge
        self.target_asset_id = self.candidate_combo.currentData()
        self.accept()

    def _on_create(self):
        self.action = self.CreateNew
        self.accept()

    def _on_discard(self):
        self.action = self.Discard
        self.accept()
