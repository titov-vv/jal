from jal.data_import.shop_receipts.continente import ReceiptContinente

JAL_RECEIPT_CLASS = "ReceiptNote"


# ----------------------------------------------------------------------------------------------------------------------
# Note!: the layout of Continente; an indented ACUMULA EM CARTAO under an item is a loyalty credit, not money paid
class ReceiptNote(ReceiptContinente):
    NIF = "517309505"
    name = "Note"
