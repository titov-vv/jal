from jal.db.helpers import executeSQL


# ----------------------------------------------------------------------------------------------------------------------
# Helper functions for unification

# ----------------------------------------------------------------------------------------------------------------------
# Fill actions into DB. actions is a list of tuples:
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
