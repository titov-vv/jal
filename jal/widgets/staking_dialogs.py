from PySide6.QtWidgets import QDialog, QDialogButtonBox, QComboBox, QFormLayout, QLineEdit, QMessageBox

from jal.constants import AssetLocation
from jal.db.db import JalDB
from jal.db.account import JalAccount
from jal.db.asset import JalAsset
from jal.db.staking import JalStakingBox
from jal.db.token_blacklist import is_valid_address, normalize_address


# ----------------------------------------------------------------------------------------------------------------------
# Asks for what a new staking box needs and creates it. The box is an account of a hidden type, but the word
# "account" never appears here: the user stakes an asset into a validator, a venue or a protocol, and the account
# behind that is an implementation detail - exactly as it is for a term deposit (see NewDepositDialog).
#
# Everything but the name is optional and is usually filled in already: the dialog is opened from a pending transfer
# leg that names the address the asset went to, the chain it moved on and - in the description a custody import
# writes - the protocol holding it. Stating the address is what makes the box settle by itself afterwards, so it is
# offered even though nothing forces it: a venue's internal staking balance has no address to give.
class NewStakingBoxDialog(QDialog):
    # 'source' is the account the asset is staked FROM: the box takes its currency and its decimal precision, so
    # that what moves between the two is booked by both of them identically (see JalStakingBox.create).
    def __init__(self, source: JalAccount, protocol: str = '', chain: int = AssetLocation.UNDEFINED,
                 address: str = '', parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("New staked position"))
        self.setMinimumWidth(450)
        self.box = None
        self._source = source
        layout = QFormLayout(self)

        self._name = QLineEdit(self)
        self._name.setText(self._suggested_name(protocol))
        layout.addRow(self.tr("Name"), self._name)
        self._protocol = QLineEdit(self)
        self._protocol.setText(protocol)
        layout.addRow(self.tr("Protocol"), self._protocol)
        self._chain = QComboBox(self)
        locations = AssetLocation()
        self._chain.addItem('', userData=AssetLocation.UNDEFINED)
        for location_id in AssetLocation.BLOCKCHAINS:
            self._chain.addItem(locations.get_name(location_id), userData=location_id)
        self._chain.setCurrentIndex(max(self._chain.findData(chain), 0))
        layout.addRow(self.tr("Blockchain"), self._chain)
        self._address = QLineEdit(self)
        self._address.setText(address)
        layout.addRow(self.tr("Address"), self._address)
        # Not editable: the box takes the currency of the account the asset comes from, because an asset transfer
        # between two currencies needs a cost basis restated in the destination's currency - which nothing here
        # knows. Shown all the same, so what the box's value will be measured in is never a surprise.
        self._currency = QLineEdit(self)
        self._currency.setText(JalAsset(source.currency()).symbol())
        self._currency.setReadOnly(True)
        layout.addRow(self.tr("Valued in"), self._currency)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    # A name that says what the position is, taken from the protocol the import recognized. It has to be unique
    # among ALL accounts, so a second box of the same protocol (a second validator, a second lock) is numbered.
    @staticmethod
    def _suggested_name(protocol: str) -> str:
        if not protocol:
            return ''
        name = protocol
        index = 2
        while JalDB._read("SELECT id FROM accounts WHERE name=:name", [(":name", name)]) is not None:
            name = f"{protocol} #{index}"
            index += 1
        return name

    def accept(self):
        name = self._name.text().strip()
        if not name:
            return self._warn(self.tr("A staked position needs a name"))
        if JalDB._read("SELECT id FROM accounts WHERE name=:name", [(":name", name)]) is not None:
            return self._warn(self.tr("An account or a position with this name already exists"))
        chain = self._chain.currentData()
        address = self._address.text().strip()
        if address:
            if chain == AssetLocation.UNDEFINED:
                return self._warn(self.tr("An address belongs to a blockchain - choose the one it is on"))
            address = normalize_address(chain, address)
            if not is_valid_address(chain, address):
                return self._warn(self.tr("This is not a valid address of the selected blockchain: ") + address)
            # Two boxes sharing an address make every leg naming it unresolvable (JalAccount.at_address refuses a
            # multiple match), which silently turns the automatic settlement off instead of failing visibly.
            if JalAccount.at_address(chain, address) is not None:
                return self._warn(self.tr("Another account already holds this address on this blockchain"))
        self.box = JalStakingBox.create(self._source, name, protocol=self._protocol.text().strip(),
                                        chain=chain, address=address)
        super().accept()

    def _warn(self, text: str) -> None:
        QMessageBox().warning(self, self.tr("Incomplete data"), text, QMessageBox.Ok)
