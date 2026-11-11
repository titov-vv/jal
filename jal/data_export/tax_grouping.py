from dataclasses import dataclass

DEAL_TEMPLATES = ("trade", "corporate_action")   # the rows of a section that are deals
DAY = 86400


# Levels the deals of a section are grouped at
class Grouping:
    Nothing = 0
    SaleDay = 1     # deals of a security disposed of on one day
    Security = 2    # all deals of a security
    Days = 3        # deals of a security acquired on one day and disposed of on one day: a line of a tax form


# The names a jurisdiction's deal rows keep their values under
@dataclass
class DealFields:
    security: tuple   # what identifies the security
    qty: str          # the signed quantity, negative for a short
    opened: tuple     # dates of the opening leg
    closed: tuple     # dates of the closing leg
    figures: tuple    # the additive values: quantities and amounts

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
