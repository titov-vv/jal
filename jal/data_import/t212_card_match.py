from decimal import Decimal
from jal.db.db import JalDB


# ----------------------------------------------------------------------------------------------------------------------
# Pairs the card purchases a Trading212 statement reports with the ones that are in the database already.
#
# The same purchase reaches the database from two sides - typed by hand as it happens and read from the monthly
# statement afterwards - and nothing identifies it on both. The 'actions' table has no reference number column at
# all, and the two clocks disagree: most hand-entered rows sit within a minute of what the statement says, but some
# are off by exactly an hour (a local-time reading typed as if it were UTC) and one row of the sample month by a
# quarter of an hour. What never disagrees is the amount - it is the very cent the card was charged, and a receipt
# split into several category lines sums to it exactly.
#
# So the amount is the key and the time only ranks the candidates. That is a resemblance rather than a proof, which
# is why nothing here decides anything: what it produces is a proposal the user confirms in CardImportDialog.
class CardMatcher(JalDB):
    # How far apart the two clocks may be for a candidate to be considered at all. Four hours covers the observed
    # one-hour shift with room to spare and still stays well inside a day; a wider window starts pairing purchases
    # that merely happen to cost the same.
    WINDOW = 4 * 60 * 60

    # Every spending operation stored on the account around the given period, as
    # {'oid', 'timestamp', 'peer_id', 'peer', 'amount'} with 'amount' negative - a receipt split into several
    # category lines being one operation of their sum, which is what the card was charged.
    # The period is widened by WINDOW on both sides, so a purchase near a month boundary is still a candidate.
    #
    # The lines are summed here rather than by SQL: an amount lives in a TEXT column, and SQLite's own SUM() reads
    # such a column as a float - which turns -18.40 into a value that is not equal to -18.40 any more, and the
    # whole of this matching rests on amounts being equal to the cent.
    @classmethod
    def stored_operations(cls, account_id: int, begin: int, end: int) -> list:
        operations = {}
        query = cls._exec("SELECT a.oid, a.timestamp, a.peer_id, p.name AS peer, d.amount "
                          "FROM actions AS a "
                          "LEFT JOIN action_details AS d ON d.pid=a.oid "
                          "LEFT JOIN agents AS p ON p.id=a.peer_id "
                          "WHERE a.account_id=:account_id AND a.timestamp>=:begin AND a.timestamp<=:end",
                          [(":account_id", account_id), (":begin", begin - cls.WINDOW), (":end", end + cls.WINDOW)])
        while query.next():
            line = cls._read_record(query, named=True)
            oid = int(line['oid'])
            if oid not in operations:
                operations[oid] = {'oid': oid, 'timestamp': int(line['timestamp']), 'peer_id': int(line['peer_id']),
                                   'peer': line['peer'], 'amount': Decimal('0')}
            operations[oid]['amount'] += Decimal(line['amount'])
        # An income (interest, cashback) is not something a card debit may ever be
        return [x for x in operations.values() if x['amount'] < 0]

    # Proposes a pairing between the statement rows and what is stored, and returns a list with one element per row -
    # the stored operation it was paired with, or None.
    #
    # 'rows' and 'stored' are both [{'timestamp': int, 'amount': Decimal, ...}]. Only equal amounts may pair, and of
    # the pairs that are possible the closest in time is made first, each stored operation being used once. Doing it
    # in that order (rather than row by row) is what keeps two purchases of the same amount on one day with their own
    # counterparts instead of letting the first row take whichever it happened to see first.
    @classmethod
    def propose(cls, rows: list, stored: list) -> list:
        candidates = []
        for index, row in enumerate(rows):
            for operation in stored:
                if operation['amount'] != row['amount']:
                    continue
                distance = abs(operation['timestamp'] - row['timestamp'])
                if distance <= cls.WINDOW:
                    candidates.append((distance, index, operation))
        candidates.sort(key=lambda x: (x[0], x[1], x[2]['oid']))
        matches = [None] * len(rows)
        paired = set()
        for _distance, index, operation in candidates:
            if matches[index] is not None or operation['oid'] in paired:
                continue
            matches[index] = operation
            paired.add(operation['oid'])
        return matches
