from datetime import datetime
from dateutil import tz

from jal.constants import TransactionType
from PySide2.QtCore import Qt, QObject, Signal, Slot
from jal.db.helpers import executeSQL

INIT_NULL = 0
INIT_VALUE = 1
INIT_TIMESTAMP = 2
INIT_ACCOUNT = 3

IV_COPY = 0
IV_TYPE = 1
IV_VALUE = 2

LedgerInitValues = {
    TransactionType.Action: {
    # FieldName, True-Copy, TypeOfInitialization, DefaultValue
        'id': (False, INIT_NULL, None),
        'timestamp': (False, INIT_TIMESTAMP, None),
        'account_id': (True, INIT_ACCOUNT, None),
        'peer_id': (True, INIT_VALUE, 0),
        'alt_currency_id': (True, INIT_VALUE, None)
    },
    TransactionType.Trade: {
        'id': (False, INIT_NULL, None),
        'timestamp': (False, INIT_TIMESTAMP, None),
        'settlement': (True, INIT_VALUE, 0),
        'number': (False, INIT_VALUE, ''),
        'account_id': (True, INIT_ACCOUNT, None),
        'asset_id': (True, INIT_VALUE, 0),
        'qty': (True, INIT_VALUE, 0),
        'price': (True, INIT_VALUE, 0),
        'coupon': (True, INIT_VALUE, 0),
        'fee': (True, INIT_VALUE, 0)
    },
    TransactionType.Dividend: {
        'id': (False, INIT_NULL, None),
        'timestamp': (False, INIT_TIMESTAMP, None),
        'number': (False, INIT_VALUE, ''),
        'account_id': (True, INIT_ACCOUNT, None),
        'asset_id': (True, INIT_VALUE, 0),
        'sum': (True, INIT_VALUE, 0),
        'sum_tax': (True, INIT_VALUE, 0),
        'note': (True, INIT_VALUE, None)
    },
    TransactionType.Transfer: {
        'id': (False, INIT_NULL, None),
        'withdrawal_timestamp': (False, INIT_TIMESTAMP, None),
        'withdrawal_account': (True, INIT_ACCOUNT, None),
        'withdrawal': (True, INIT_VALUE, 0),
        'deposit_timestamp': (False, INIT_TIMESTAMP, None),
        'deposit_account': (True, INIT_ACCOUNT, None),
        'deposit': (True, INIT_VALUE, 0),
        'fee_account': (True, INIT_NULL, None),
        'fee': (True, INIT_VALUE, 0),
        'asset': (True, INIT_NULL, None),
        'note': (True, INIT_VALUE, '')
    },
    TransactionType.CorporateAction: {
        'id': (False, INIT_NULL, None),
        'timestamp': (False, INIT_TIMESTAMP, None),
        'number': (False, INIT_VALUE, ''),
        'account_id': (True, INIT_ACCOUNT, None),
        'type': (True, INIT_VALUE, 1),
        'asset_id': (True, INIT_VALUE, 0),
        'qty': (True, INIT_VALUE, 0),
        'asset_id_new': (True, INIT_VALUE, 0),
        'qty_new': (True, INIT_VALUE, 0),
        'note': (True, INIT_VALUE, '')
    }
}


class LedgerOperationsView(QObject):
    activateOperationView = Signal(int)
    stateIsCommitted = Signal()
    stateIsModified = Signal()

    OP_NAME = 0
    OP_MAPPER = 1
    OP_MAPPER_TABLE = 2
    OP_CHILD_VIEW = 3
    OP_CHILD_TABLE = 4
    OP_INIT = 5
    
    def __init__(self, operations_table_view, main_window):
        super().__init__()

        self.p_account_id = 0
        self.p_search_text = ''
        self.start_date_of_view = 0
        self.main_window = main_window
        self.table_view = operations_table_view
        self.operations = None
        self.modified_operation_type = None

    def addNewOperation(self, operation_type):
        self.checkForUncommittedChanges()
        self.activateOperationView.emit(operation_type)   # self.ShowOperationTab in Main_Window
        mapper = self.operations[operation_type][self.OP_MAPPER]
        mapper.submit()
        mapper.model().setFilter(f"{self.operations[operation_type][self.OP_MAPPER_TABLE]}.id = 0")
        new_record = mapper.model().record()
        new_record = self.prepareNewOperation(operation_type, new_record, copy_mode=False)
        assert mapper.model().insertRows(0, 1)
        mapper.model().setRecord(0, new_record)
        mapper.toLast()
        self.initChildDetails(operation_type)

    @Slot()
    def copyOperation(self):
        self.checkForUncommittedChanges()
        index = self.table_view.currentIndex()
        operations_model = self.table_view.model()
        operation_type = operations_model.get_operation_type(index.row())
        mapper = self.operations[operation_type][self.OP_MAPPER]
        row = mapper.currentIndex()
        old_id = mapper.model().record(row).value(mapper.model().fieldIndex("id"))
        new_record = mapper.model().record(row)
        new_record = self.prepareNewOperation(operation_type, new_record, copy_mode=True)
        mapper.model().setFilter(f"{self.operations[operation_type][self.OP_MAPPER_TABLE]}.id = 0")
        assert mapper.model().insertRows(0, 1)
        mapper.model().setRecord(0, new_record)
        mapper.toLast()

        if self.operations[operation_type][self.OP_CHILD_VIEW]:
            child_view = self.operations[operation_type][self.OP_CHILD_VIEW]
            child_view.model().setFilter(f"{self.operations[operation_type][self.OP_CHILD_TABLE]}.pid = 0")
            query = executeSQL(mapper.model().database(),
                               f"SELECT * FROM {self.operations[operation_type][self.OP_CHILD_TABLE]} "
                               "WHERE pid = :pid ORDER BY id DESC", [(":pid", old_id)])
            while query.next():
                new_record = query.record()
                new_record.setNull("id")
                new_record.setNull("pid")
                assert child_view.model().insertRows(0, 1)
                child_view.model().setRecord(0, new_record)
                
    def initChildDetails(self, operation_type):
        view = self.operations[operation_type][self.OP_CHILD_VIEW]
        if view:
            view.model().setFilter(f"{self.operations[operation_type][self.OP_CHILD_TABLE]}.pid = 0")
            
    def prepareNewOperation(self, operation_type, new_operation_record, copy_mode=False):
        init_values = self.operations[operation_type][self.OP_INIT]
        for field in init_values:
            if copy_mode and init_values[field][IV_COPY]:
                continue
            if init_values[field][IV_TYPE] == INIT_NULL:
                new_operation_record.setNull(field)
            if init_values[field][IV_TYPE] == INIT_TIMESTAMP:
                new_operation_record.setValue(field, int(datetime.now().replace(tzinfo=tz.tzutc()).timestamp()))
            if init_values[field][IV_TYPE] == INIT_ACCOUNT:
                new_operation_record.setValue(field, self.p_account_id)
            if init_values[field][IV_TYPE] == INIT_VALUE:
                new_operation_record.setValue(field, init_values[field][IV_VALUE])
        return new_operation_record





