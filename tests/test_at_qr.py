from datetime import date
from decimal import Decimal

from jal.data_import.receipt_api.pt_at_qr import AtQr

# Fabricated after the layout of a real Lidl receipt; B:999999990 is the 'final consumer' placeholder
LIDL = "A:503340855*B:999999990*C:PT*D:FS*E:N*F:20260814*G:FS 0421/000317*H:JFXK7T2P-317*I1:PT*I3:6.92*I4:0.42*" \
       "I7:3.74*I8:0.86*N:1.28*O:11.94*Q:aB3d*R:9999"


# ----------------------------------------------------------------------------------------------------------------------
def test_fields_of_a_simplified_invoice():
    qr = AtQr.parse(LIDL)
    assert qr is not None
    assert qr.nif == "503340855"
    assert qr.doc_type == "FS"
    assert qr.status == "N"
    assert qr.date == date(2026, 8, 14)
    assert qr.doc_id == "FS 0421/000317"
    assert qr.atcud == "JFXK7T2P-317"
    assert qr.value('I3') == "6.92"
    assert qr.value('J1') == ''
    assert not qr.is_return


def test_amounts_are_exact_decimals():
    qr = AtQr.parse(LIDL)
    assert qr.total == Decimal('11.94') and isinstance(qr.total, Decimal)
    assert qr.tax_total == Decimal('1.28') and isinstance(qr.tax_total, Decimal)


def test_number_is_unique_across_issuers():
    assert AtQr.parse(LIDL).number == "503340855:FS 0421/000317"


def test_credit_note_is_a_return():
    qr = AtQr.parse(LIDL.replace("D:FS", "D:NC").replace("G:FS ", "G:NC "))
    assert qr.is_return
    assert qr.doc_id == "NC 0421/000317"


def test_malformed_codes_are_refused():
    assert AtQr.parse("") is None
    assert AtQr.parse("https://example.com/receipt?id=1") is None
    assert AtQr.parse(LIDL[:LIDL.index("*N:")]) is None                    # truncated: mandatory N, O, Q, R missing
    assert AtQr.parse(LIDL.replace("A:503340855", "A:PT503340855")) is None  # NIF with a country prefix
    assert AtQr.parse(LIDL.replace("O:11.94", "O:11,94")) is None            # decimal comma
    assert AtQr.parse(LIDL.replace("O:11.94", "O:11.9")) is None             # always two decimals
    assert AtQr.parse(LIDL.replace("F:20260814", "F:20261314")) is None      # no such date
    assert AtQr.parse(LIDL + "*O:12.00") is None                             # repeated field
    assert AtQr.parse(LIDL.replace("*I1:PT*", "*I1PT*")) is None             # field without a separator
