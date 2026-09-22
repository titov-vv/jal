from jal.data_import.receipt import ShopReceipt, AMOUNT

JAL_RECEIPT_CLASS = "ReceiptPingoDoce"


# ----------------------------------------------------------------------------------------------------------------------
# Pingo Doce: ' C NAME   0,180 X 3,39   0,61' with the VAT code first, grouped under printed departments;
# a '(0,93)' saving reduces what the item above it cost
class ReceiptPingoDoce(ShopReceipt):
    NIF = "500829993"
    name = "Pingo Doce"
    discounts_netted = True
    DepartmentPattern = r'^(?P<dept>[A-ZÀ-Ý][A-ZÀ-Ý0-9./ &,-]{3,40})$'
    DiscountPattern = r'^\s+(?P<label>Poupan\S*[^(]*?)\s*\((?P<amount>' + AMOUNT + r')\)\s*$'
    ItemPattern = r'^\s(?P<vat>[A-Z])\s(?P<name>.*?)(?:\s{2,}(?P<qty>[\d.]*\d,\d+)\s*X\s*(?P<price>[\d.]*\d,\d+))?' \
                  r'\s{2,}(?P<amount>' + AMOUNT + r')\s*$'
    DatetimePattern = r'^\s*\d{6}\s+(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\s+(?P<hour>\d{2}):' \
                      r'(?P<minute>\d{2})\s'
