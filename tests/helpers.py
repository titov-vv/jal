from jal.db.helpers import executeSQL
from constants import PredefinedAsset


# ----------------------------------------------------------------------------------------------------------------------
# Helper functions for unification

# ----------------------------------------------------------------------------------------------------------------------
# Create assets in database with PredefinedAsset.Stock type : assets is a list of tuples (asset_id, symbol, full_name)
def create_stocks(assets):
    for asset in assets:
        assert executeSQL("INSERT INTO assets (id, name, type_id, full_name) "
                          "VALUES (:id, :name, :type, :full_name)",
                          [(":id", asset[0]), (":name", asset[1]),
                           (":type", PredefinedAsset.Stock), (":full_name", asset[2])], commit=True) is not None

# ----------------------------------------------------------------------------------------------------------------------
# Create actions in database: actions is a list of tuples
# (timestamp, account, peer, [(category, amount), (category, amount), ...])
def create_actions(actions):
    for action in actions:
        query = executeSQL("INSERT INTO actions (timestamp, account_id, peer_id) "
                           "VALUES (:timestamp, :account, :peer)",
                           [(":timestamp", action[0]), (":account", action[1]), (":peer", action[2])], commit=True)
        assert query is not None
        action_id = query.lastInsertId()
        for detail in action[3]:
            assert executeSQL("INSERT INTO action_details (pid, category_id, amount) "
                              "VALUES (:pid, :category, :amount)",
                              [(":pid", action_id), (":category", detail[0]), (":amount", detail[1])],
                              commit=True) is not None
