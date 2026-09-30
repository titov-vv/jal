from jal.data_import.receipt import ShopReceipt, AMOUNT

JAL_RECEIPT_CLASS = "ReceiptPingoDoce"


# ----------------------------------------------------------------------------------------------------------------------
# Pingo Doce: ' C NAME   0,180 X 3,39   0,61' with the VAT code first, grouped under printed departments;
# a '(0,93)' saving reduces what the item above it cost, one under 'Descontos Extra' the whole receipt
class ReceiptPingoDoce(ShopReceipt):
    NIF = "500829993"
    name = "Pingo Doce"
    discounts_netted = True
    DepartmentPattern = r'^(?P<dept>[A-ZÀ-Ý][A-ZÀ-Ý0-9./ &,+-]{3,40})$'
    DiscountPattern = r'^\s+(?P<label>(?:Poupan\S*|Saldo\s)[^(]*?)\s*\((?P<amount>' + AMOUNT + r')\)\s*$'
    ItemPattern = r'^\s(?P<vat>[A-Z])\s(?P<name>.*?)(?:\s{2,}(?P<qty>[\d.]*\d,\d+)\s*X\s*(?P<price>[\d.]*\d,\d+))?' \
                  r'\s{2,}(?P<amount>' + AMOUNT + r')\s*$'
    SubtotalPattern = r'^Descontos\s+Extra\s*$'
    VoucherLabel = r'V\.\s|Saldo\s+Dep'   # ' V. Deposito Volta   0,60' or ' Saldo Depósito Volta   0,10' in the payments
    DatetimePattern = r'^\s*\d{6}\s+(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\s+(?P<hour>\d{2}):' \
                      r'(?P<minute>\d{2})\s'
