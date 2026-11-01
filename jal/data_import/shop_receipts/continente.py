from jal.data_import.receipt import ShopReceipt, AMOUNT

JAL_RECEIPT_CLASS = "ReceiptContinente"


# ----------------------------------------------------------------------------------------------------------------------
# Continente and Note!: '(A)   NAME   1,19' under 'Department:' rows, a weighed item's '0,705 X 2,49   1,76' on a line
# of its own; an indented POUPANCA is already in its price and ACUMULA EM CARTAO is a loyalty credit, only 'Desconto'
# below SUBTOTAL is money off
class ReceiptContinente(ShopReceipt):
    NIFS = ("502011475", "517309505")     # Continente, Note!
    name = "Continente"
    discounts_netted = False
    DepartmentPattern = r'^(?P<dept>[^\s(].*?):\s*$'
    DiscountPattern = r'^(?P<label>Desconto\b.*?)\s{2,}-?(?P<amount>' + AMOUNT + r')\s*$'
    QuantityAmountPattern = r'^\s+(?P<qty>[\d.]*\d(?:,\d+)?)\s+X\s+(?P<price>' + AMOUNT + \
                            r')\s+(?P<amount>' + AMOUNT + r')\s*$'
    ItemPattern = r'^\((?P<vat>[A-Z])\)\s+(?P<name>.*?)(?:\s{2,}(?P<amount>' + AMOUNT + r'))?\s*$'
    DatetimePattern = r'^\s*Nro:.*\s(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})\s+(?P<hour>\d{2}):' \
                      r'(?P<minute>\d{2})\s*$'
    SlipDatetimePattern = r'^\s*(?P<year>\d{2})-(?P<month>\d{2})-(?P<day>\d{2})\s+(?P<hour>\d{2}):(?P<minute>\d{2}):' \
                          r'(?P<second>\d{2})\s+Per\d+'
