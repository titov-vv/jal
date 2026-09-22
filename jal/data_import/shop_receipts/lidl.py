from jal.data_import.receipt import ShopReceipt, AMOUNT

JAL_RECEIPT_CLASS = "ReceiptLidl"


# ----------------------------------------------------------------------------------------------------------------------
# Lidl: 'NAME   1,41 B' with the VAT code last; a discount line reduces what the item above it cost
class ReceiptLidl(ShopReceipt):
    NIF = "503340855"
    name = "Lidl"
    discounts_netted = True
    DiscountPattern = r'^\s*(?P<label>Promo\S*[^\d]*?)\s{2,}-(?P<amount>' + AMOUNT + r')\s*$'
    # A multi-unit item prints its name alone, then '0,85  x 2    1,70 A'
    QuantityAmountPattern = r'^\s+(?P<price>' + AMOUNT + r')\s+x\s+(?P<qty>\d+)\s+(?P<amount>' + AMOUNT + \
                            r')\s+(?P<vat>[A-Z])\s*$'
    QuantityPattern = r'^\s*(?P<qty>[\d.]*\d,\d+)\s*(?:kg|un)?\s*x\s*(?P<price>[\d.]*\d,\d+)'
    ItemPattern = r'^(?P<name>\S.*?)(?:\s{2,}(?P<amount>' + AMOUNT + r')\s+(?P<vat>[A-Z]))?\s*$'
    DatetimePattern = r'^\s*\d+\s+(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{2})\s+(?P<hour>\d{2}):' \
                      r'(?P<minute>\d{2})\s*$'
