from dataclasses import dataclass
from PySide6.QtCore import QT_TRANSLATE_NOOP
from jal.data_export.tax_options import TaxOption, OptionType

DEAL_TEMPLATES = ("trade", "corporate_action")   # the rows of a section that are deals
DAY = 86400


# Levels the deals of a section are grouped at
class Grouping:
    Nothing = 0
    SaleDay = 1     # deals of a security disposed of on one day
    Security = 2    # all deals of a security
    Days = 3        # deals of a security acquired on one day and disposed of on one day: a line of a tax form


# The option of a report that groups the deals on its sheets
GROUPING_OPTION = TaxOption(
    'grouping', QT_TRANSLATE_NOOP("TaxWidget", "Group deals in Excel:"), type=OptionType.Choice, default=Grouping.Nothing,
    choices=((Grouping.Nothing, QT_TRANSLATE_NOOP("TaxWidget", "No grouping")),
             (Grouping.SaleDay, QT_TRANSLATE_NOOP("TaxWidget", "Security and sale day")),
             (Grouping.Security, QT_TRANSLATE_NOOP("TaxWidget", "Security")),
             (Grouping.Days, QT_TRANSLATE_NOOP("TaxWidget", "Security, purchase day and sale day"))))


# The names a jurisdiction's deal rows keep their values under
@dataclass
class DealFields:
    security: tuple   # what identifies the security
    qty: str          # the signed quantity, negative for a short
    opened: tuple     # dates of the opening leg
    closed: tuple     # dates of the closing leg
    figures: tuple    # the additive values: quantities and amounts
    numbers: tuple = ('o_number', 'c_number')   # the trade numbers of the two legs

    def dates(self) -> tuple:
        return self.opened + self.closed


# The deals grouped together and what they have in common, see summarize()
@dataclass
class DealGroup:
    rows: list
    summary: dict


# The key of a deal row at a level; a short is apart from a long, and is disposed of by its opening leg
def deal_key(fields: DealFields, level: int):
    def key(row: dict) -> tuple:
        short = row[fields.qty] < 0
        acquired, disposed = (fields.closed, fields.opened) if short else (fields.opened, fields.closed)
        value = tuple(row[x] for x in fields.security) + (short,)
        if level in (Grouping.SaleDay, Grouping.Days):
            value += tuple(row[x] // DAY for x in disposed)
        if level == Grouping.Days:
            value += tuple(row[x] // DAY for x in acquired)
        return value
    return key


# One row for the deals of a group: a figure is their sum, a date their earliest moment if they share the day, any
# other value is kept if they all have it the same; the rest is left out
def summarize(rows: list, fields: DealFields) -> dict:
    summary = {}
    for name in rows[0]:
        if not all(name in x for x in rows):
            continue
        values = [x[name] for x in rows]
        if name in fields.figures:
            summary[name] = sum(values)
        elif name in fields.dates():
            if len({x // DAY for x in values}) == 1:
                summary[name] = min(values)
        elif all(x == values[0] for x in values):
            summary[name] = values[0]
    return summary


# The rows of a section with its deals collected into DealGroup's by 'key', each group where its first deal was; any
# other row stays as it is. A group never leaves its account's block.
def group_deals(section: list, key, fields: DealFields) -> list:
    items, groups = [], {}
    for row in section:
        if row['report_template'] == "account":
            groups = {}
        if row['report_template'] not in DEAL_TEMPLATES:
            items.append(row)
            continue
        group = groups.get(key(row))
        if group is None:
            group = groups[key(row)] = DealGroup([], {})
            items.append(group)
        group.rows.append(row)
    for item in items:
        if isinstance(item, DealGroup):
            item.summary = summarize(item.rows, fields)
    return items


# The rows of a section with the deals of each group of a level as one row: the group's summary, with its deals
# under 'merged'
def merge_deals(section: list, fields: DealFields, level: int) -> list:
    items = group_deals(section, deal_key(fields, level), fields)
    return [dict(x.summary, report_template=x.rows[0]['report_template'], merged=x.rows) if isinstance(x, DealGroup)
            else x for x in items]


# The rows of a section with its deals grouped at a level for the sheet's outline: over each group of several deals
# a row of what they have in common, in the layout of the first of them, and the deals folded under it. A leg of
# several trades says how many in 'several', e.g. "{} trades".
def outline_deals(section: list, fields: DealFields, level: int, several: str) -> list:
    rows = []
    for item in group_deals(section, deal_key(fields, level), fields):
        if not isinstance(item, DealGroup):
            rows.append(item)
        elif len(item.rows) == 1:
            rows += item.rows
        else:
            head = {x: item.summary.get(x) for x in item.rows[0]}
            for name in fields.numbers:
                if name not in item.summary:
                    head[name] = several.format(len({x[name] for x in item.rows}))
            head.update(report_template="group", layout=item.rows[0]['report_template'], outline_head=True)
            rows.append(head)
            rows += [dict(x, outline_level=1) for x in item.rows]
    return rows
