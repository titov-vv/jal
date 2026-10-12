from jal.db.lending_interest import stored_welded_interest, book_welded_interest


# Takes the interest a rebasing receipt token welded onto a supply or a withdrawal out of every stored conversion
# and books it as an AssetIncome.LendingInterest - what the statement import does for a new one.
def update() -> None:
    book_welded_interest(stored_welded_interest())
