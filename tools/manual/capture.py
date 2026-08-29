#!/usr/bin/env python
# Takes every screenshot the manual uses, from the demo database that make_demo_db.py builds.
# Runs head-less (offscreen Qt platform), so it needs no desktop session and always produces the same images.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from demo_env import prepare_environment, assert_demo_database, MANUAL_DIR, DOCS_DIR, REPO_DIR

# NB: the environment is prepared in main() and not here, so that importing this module (capture_first_run.py
# does) can't silently re-point the configuration at another database.

from PySide6.QtCore import Qt, QDate, QPoint
from PySide6.QtWidgets import QApplication

IMG_DIR = os.path.join(MANUAL_DIR, "img")        # pictures the manual uses
README_IMG_DIR = os.path.join(DOCS_DIR, "img")   # the few the project README needs on top of those
WINDOW_SIZE = (1440, 860)


def store(pixmap, name: str, directory: str) -> None:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name + ".png")
    pixmap.save(path)
    print("saved", os.path.relpath(path, REPO_DIR))


def save(widget, name: str, directory: str = IMG_DIR) -> None:
    widget.ensurePolished()
    QApplication.processEvents()
    store(widget.grab(), name, directory)


def save_menu(menu, name: str) -> None:
    menu.ensurePolished()
    menu.adjustSize()
    QApplication.processEvents()
    save(menu, name)


# The README shows a dialog standing over the main window, which a screenshot of a real desktop gets for free.
# Off-screen there is no desktop and every window is grabbed alone, so the two are composed by hand. The offsets
# are fractions of the free space, so the dialog stays inside the picture whatever size it turns out to be.
def save_over(base, overlay, name: str, directory: str, offset=(0.5, 0.6)) -> None:
    from PySide6.QtGui import QPainter, QColor
    base.ensurePolished()
    overlay.ensurePolished()
    QApplication.processEvents()
    canvas, top = base.grab(), overlay.grab()
    x = int((canvas.width() - top.width()) * offset[0])
    y = int((canvas.height() - top.height()) * offset[1])
    painter = QPainter(canvas)
    painter.fillRect(x + 5, y + 5, top.width(), top.height(), QColor(0, 0, 0, 50))   # a shadow, so that the
    painter.drawPixmap(x, y, top)                                                    # dialog reads as being on top
    painter.setPen(QColor(0, 0, 0, 130))
    painter.drawRect(x, y, top.width() - 1, top.height() - 1)
    painter.end()
    store(canvas, name, directory)


# ----------------------------------------------------------------------------------------------------------------------
def operations_window(window):
    from jal.widgets.operations_widget import OperationsWidget
    for opened in window.ui.windowArea.windows():
        if isinstance(opened, OperationsWidget):
            return opened
    return None


def select_operation(operations, predicate) -> bool:
    model = operations.operations_model
    view = operations.ui.OperationsTableView
    for row in range(model.rowCount()):
        otype, oid = model.get_operation(row)
        if predicate(otype, oid):
            view.selectRow(row)
            QApplication.processEvents()
            return True
    return False


def to_ts(text: str) -> int:
    from datetime import datetime, timezone
    return int(datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def set_range(selector, first: str, last: str) -> None:
    selector.setRange(to_ts(first), to_ts(last))
    QApplication.processEvents()


# ----------------------------------------------------------------------------------------------------------------------
def capture_main_window(window, operations):
    from jal.db.operations import LedgerTransaction
    operations.ui.ChooseAccountBtn.account_id = 2          # 'Isarbank Current'
    set_range(operations.ui.DateRange, "2026-06-01", "2026-08-31")
    QApplication.processEvents()
    select_operation(operations, lambda otype, oid: otype == LedgerTransaction.IncomeSpending)
    save(window, "main_window")
    save(operations.ui.BalanceBox, "balances_panel")


# An operation editor sits in the lower half of the operations window and is only as wide as that split allows,
# which crops its fields. For a picture of the editor itself it is stretched to a width where nothing is cut.
def save_editor(widget, name: str) -> None:
    widget.setMinimumWidth(980)
    widget.adjustSize()
    QApplication.processEvents()
    save(widget, name)
    widget.setMinimumWidth(0)


def capture_operation_editors(window, operations):
    from jal.db.operations import LedgerTransaction, AssetPayment, IncomeSpending

    def split_spending(otype, oid) -> bool:
        return otype == LedgerTransaction.IncomeSpending and len(IncomeSpending(oid)._details) > 1

    editors = [
        (3, "2025-01-01", "2026-12-31", split_spending, "op_income_spending"),
        (2, "2026-06-01", "2026-08-31",
         lambda otype, oid: otype == LedgerTransaction.Transfer, "op_transfer"),
        (4, "2025-01-01", "2026-12-31",
         lambda otype, oid: otype == LedgerTransaction.Trade, "op_trade"),
        (4, "2025-01-01", "2026-12-31",
         lambda otype, oid: otype == LedgerTransaction.AssetPayment, "op_dividend"),
        (6, "2025-01-01", "2026-12-31",
         lambda otype, oid: otype == LedgerTransaction.Swap, "op_swap"),
    ]
    for account_id, first, last, predicate, name in editors:
        operations.ui.ChooseAccountBtn.account_id = account_id
        set_range(operations.ui.DateRange, first, last)
        if select_operation(operations, predicate):
            save_editor(operations.ui.OperationsTabs.currentWidget(), name)
        else:
            print("!! no operation found for", name)
    save_menu(operations.NewOperationMenu, "new_operation_menu")


# The context menus are built and popped up inside the widget that owns them, so the menu object never reaches
# the caller. It is caught here by intercepting the popup that shows it.
def capture_context_menu(call, name: str) -> None:
    from PySide6.QtWidgets import QMenu
    captured = []
    original = QMenu.popup

    def intercept(menu, *args, **kwargs):
        captured.append(menu)
        return original(menu, *args, **kwargs)

    QMenu.popup = intercept
    try:
        call()
    finally:
        QMenu.popup = original
    if captured:
        save_menu(captured[0], name)
        captured[0].close()
    else:
        print("!! no context menu captured for", name)


def capture_blank_editors(window, operations):
    from jal.db.operations import LedgerTransaction
    blanks = [(LedgerTransaction.CorporateAction, "op_corporate_action"),
              (LedgerTransaction.Conversion, "op_conversion"),
              (LedgerTransaction.Bridge, "op_bridge")]
    operations.ui.ChooseAccountBtn.account_id = 4
    for operation_type, name in blanks:
        operations.ui.OperationsTabs.new_operation(operation_type, 4)
        QApplication.processEvents()
        save_editor(operations.ui.OperationsTabs.currentWidget(), name)
        operations.ui.OperationsTabs.widgets[operation_type].revertChanges()


def capture_menus(window):
    for menu, name in [(window.ui.menuLedger, "menu_ledger"), (window.ui.menu_Data, "menu_data"),
                       (window.ui.menuImport, "menu_import"), (window.ui.menuReports, "menu_reports"),
                       (window.ui.menuTax, "menu_tax"), (window.ui.menuSettings, "menu_settings"),
                       (window.ui.menuHelp, "menu_help"), (window.ui.menuStatement, "menu_statements"),
                       (window.ui.menuBlockchain, "menu_blockchain")]:
        save_menu(menu, name)


def capture_reference_dialogs(window):
    from jal.widgets.reference_dialogs import (AccountListDialog, TagsListDialog, CategoryListDialog,
                                               PeerListDialog, QuotesListDialog, ResidenceDialog)
    from jal.widgets.assets_dialogs import SymbolListDialog
    dialogs = [(AccountListDialog, "dlg_accounts", (860, 420)),
               (CategoryListDialog, "dlg_categories", (620, 540)),
               (TagsListDialog, "dlg_tags", (520, 280)),
               (PeerListDialog, "dlg_peers", (620, 400)),
               (SymbolListDialog, "dlg_assets", (1000, 420)),
               (QuotesListDialog, "dlg_quotes", (760, 400)),
               (ResidenceDialog, "dlg_residence", (700, 300))]
    for dialog_class, name, size in dialogs:
        dialog = dialog_class(window)
        dialog.resize(*size)
        dialog.show()
        if getattr(dialog, "tree_view", False):
            dialog.ui.TreeView.expandAll()
        QApplication.processEvents()
        save(dialog, name)
        dialog.close()


def capture_reports(window):
    reports = [("PortfolioReportWindow", "report_portfolio", None, (1120, 420)),
               ("IncomeSpendingReportWindow", "report_income_spending", None, (1340, 480)),
               ("DealsReportWindow", "report_deals", 4, (1240, 250)),
               ("ProfitLossReportWindow", "report_profit_loss", 4, (1340, 580)),
               ("DepositsReportWindow", "report_deposits", None, (1120, 330)),
               ("AccountBalanceHistoryReportWindow", "report_balance_history", 2, (1120, 420)),
               ("AssetsPaymentsReportWindow", "report_payments", 4, (1120, 260)),
               ("CategoryReportWindow", "report_by_category", None, (1120, 420)),
               ("TagReportWindow", "report_by_tag", None, (1120, 420)),
               ("UnsettledTransfersReportWindow", "report_unsettled", None, (960, 220))]
    for window_class, name, account_id, size in reports:
        found = [x for x in window.reports.items if x['window_class'] == window_class]
        if not found:
            print("!! report not found:", window_class)
            continue
        module = found[0]['module']
        report = getattr(module, found[0]['window_class'])(window.reports)
        window.ui.windowArea.addWindow(report, floating=True, size=size)
        # The three 'operations by ...' reports show nothing until they are told what to look for
        from jal.db.db import JalDB
        selectors = {
            "ReportCategoryEdit": ("SELECT id FROM categories WHERE name='Groceries'", None),
            "ReportPeerEdit": ("SELECT id FROM agents WHERE name='Sonnenmarkt'", None),
            "ReportTagEdit": ("SELECT id FROM tags WHERE tag='Holiday'", None)}
        for editor_name, (query, _) in selectors.items():
            editor = getattr(report.ui, editor_name, None)
            if editor is not None:
                editor.selected_id = JalDB._read(query)
                report.updateReport()
        if account_id is not None:
            if hasattr(report.ui, "ReportAccountButton"):
                report.ui.ReportAccountButton.account_id = account_id
            elif hasattr(report.ui, "ReportAccountEdit"):
                report.ui.ReportAccountEdit.selected_id = account_id
                report.onAccountChange()
        for range_name in ("ReportRange", "DateRange"):
            if hasattr(report.ui, range_name):
                set_range(getattr(report.ui, range_name), "2025-01-01", "2026-08-31")
        # The focus starts in the date editor, where it paints a selection over the date - move it to the table
        for view_name in ("ReportTreeView", "ReportTableView", "PortfolioTreeView"):
            view = getattr(report.ui, view_name, None)
            if view is not None:
                view.setFocus()
                break
        QApplication.processEvents()
        # A report with a master/detail layout shows nothing below until a row above is picked
        for view_name in ("ReportTableView", "ReportTreeView"):
            view = getattr(report.ui, view_name, None)
            if view is not None and hasattr(report.ui, "DetailsTableView"):
                view.selectRow(0)
                QApplication.processEvents()
        save(report, name)
        report.close()


def capture_edit_dialogs(window):
    from jal.widgets.account_dialog import AccountDialog
    account = AccountDialog(window)
    account.setSelectedId(4)              # 'Northgate Trading'
    account.resize(560, 400)
    account.show()
    QApplication.processEvents()
    save(account, "dlg_account_edit")
    account.reject()

    from jal.db.db import JalDB
    wallet_id = JalDB._read("SELECT id FROM accounts WHERE name='Cold Wallet'")
    wallet = AccountDialog(window)
    wallet.setSelectedId(wallet_id)
    wallet.resize(560, 400)
    wallet.show()
    QApplication.processEvents()
    save(wallet, "dlg_account_wallet")
    wallet.reject()

    from jal.widgets.symbol_dialog import SymbolDialog
    symbol = SymbolDialog(window)
    symbol.setSelectedId(4)               # the 'ACME' listing
    symbol.show()
    QApplication.processEvents()
    save(symbol, "dlg_asset_edit")
    symbol.reject()


def capture_tax_windows(window):
    from jal.widgets.tax_widget import TaxWidget, MoneyFlowWidget
    from jal.data_export.taxes import TaxReport
    for country, name in ((TaxReport.PORTUGAL, "tax_forms_pt"), (TaxReport.RUSSIA, "tax_forms_ru")):
        widget = TaxWidget(window.ui.windowArea)
        widget.ui.Year.setValue(2025)
        widget.ui.Country.setCurrentIndex(country)
        widget.resize(720, 300)
        widget.show()
        QApplication.processEvents()
        save(widget, name)
        widget.close()
    flow = MoneyFlowWidget(window.ui.windowArea)
    flow.resize(720, 200)
    flow.show()
    QApplication.processEvents()
    save(flow, "tax_money_flow")
    flow.close()


# The price chart and the tax estimate are opened from the portfolio report, on the row of one position.
def capture_position_windows(window):
    from jal.widgets.price_chart import ChartWindow
    from jal.db.tax_estimator import TaxEstimator
    from jal.db.helpers import now_ts
    chart = ChartWindow(4, 4, 2, now_ts())     # ACME held on the trading account, priced in USD
    window.ui.windowArea.addWindow(chart, floating=True, size=(900, 500))
    QApplication.processEvents()
    save(chart, "price_chart")
    chart.close()

    estimator = TaxEstimator('pt', 4, 4, 15)   # 15 shares of ACME held on the trading account
    window.ui.windowArea.addWindow(estimator, floating=True, size=(900, 300))
    QApplication.processEvents()
    save(estimator, "tax_estimate")
    estimator.close()


def capture_deposit_dialogs(window):
    from jal.widgets.deposit_dialogs import NewDepositDialog, DepositInterestDialog
    from jal.db.deposit import JalDepositBox
    from jal.db.db import JalDB
    new_deposit = NewDepositDialog(window)
    new_deposit.show()
    QApplication.processEvents()
    save(new_deposit, "dlg_deposit_new")
    new_deposit.reject()

    box_id = JalDB._read("SELECT id FROM accounts WHERE name='Isarbank 12M Savings'")
    interest = DepositInterestDialog(JalDepositBox(box_id), window)
    interest.show()
    QApplication.processEvents()
    save(interest, "dlg_deposit_interest")
    interest.reject()


def capture_dialogs(window):
    from jal.widgets.preferences_dialog import PreferencesDialog
    preferences = PreferencesDialog(window)
    preferences.show()
    QApplication.processEvents()
    save(preferences, "dlg_preferences")
    preferences.close()

    window.showAboutWindow()
    QApplication.processEvents()
    for child in window.children():
        if child.__class__.__name__ == "QMessageBox":
            child.adjustSize()
            QApplication.processEvents()
            save(child, "dlg_about")
            child.close()
            break

    from jal.db.ledger import RebuildDialog
    rebuild = RebuildDialog(window, to_ts("2026-08-01"))
    rebuild.show()
    QApplication.processEvents()
    save(rebuild, "dlg_rebuild")
    rebuild.close()

    from jal.data_import.shop_receipt import ImportReceiptDialog
    receipt = ImportReceiptDialog(window)
    receipt.resize(900, 520)
    receipt.show()
    QApplication.processEvents()
    save(receipt, "dlg_receipt")
    receipt.close()

    from jal.net.downloader import QuotesUpdateDialog
    quotes = QuotesUpdateDialog(window)
    quotes.resize(330, 380)
    quotes.show()
    QApplication.processEvents()
    save(quotes, "dlg_update_quotes")
    quotes.close()



# The project README needs two pictures the manual has no use for: an account being edited over the account it
# belongs to, and the same for an asset over an investment account. Every other picture the README shows is one
# of the manual's own, referenced where it already lives.
def capture_readme(window, operations):
    from jal.widgets.account_dialog import AccountDialog
    from jal.widgets.assets_dialogs import SymbolListDialog

    operations.ui.ChooseAccountBtn.account_id = 3          # 'Everyday Card'
    set_range(operations.ui.DateRange, "2026-06-01", "2026-08-31")
    operations.ui.OperationsTableView.selectRow(0)
    account = AccountDialog(window)
    account.setSelectedId(3)
    account.resize(560, 400)
    account.show()
    save_over(window, account, "one_account_view", README_IMG_DIR)
    account.reject()

    operations.ui.ChooseAccountBtn.account_id = 4          # 'Northgate Trading'
    set_range(operations.ui.DateRange, "2025-01-01", "2026-08-31")
    operations.ui.OperationsTableView.selectRow(0)
    assets = SymbolListDialog(window)
    assets.resize(1000, 420)
    assets.show()
    save_over(window, assets, "stocks_and_investment_account", README_IMG_DIR, offset=(0.5, 0.75))
    assets.close()


def main():
    prepare_environment()
    app = QApplication.instance() or QApplication([])
    from jal.db.db import JalDB, JalDBError
    error = JalDB().init_db()
    if error.code != JalDBError.NoError:
        raise RuntimeError(f"Demo database is not ready: {error.message}")
    assert_demo_database()

    from jal.widgets.main_window import MainWindow
    window = MainWindow(None)
    window.resize(*WINDOW_SIZE)
    window.show()
    QApplication.processEvents()
    operations = operations_window(window)
    operations.ui.OperationsTableView.setColumnWidth(0, 170)
    operations.ui.BalanceOperationsSplitter.setSizes([430, WINDOW_SIZE[0] - 430])
    operations.ui.OperationsDetailsSplitter.setSizes([440, 260])
    QApplication.processEvents()

    capture_main_window(window, operations)
    capture_operation_editors(window, operations)
    capture_menus(window)
    operations.ui.ChooseAccountBtn.account_id = 2
    set_range(operations.ui.DateRange, "2026-06-01", "2026-08-31")
    operations.ui.OperationsTableView.selectRow(0)
    QApplication.processEvents()
    capture_context_menu(lambda: operations.operation_context_menu(QPoint(20, 20)), "operation_context_menu")
    capture_context_menu(lambda: operations.balances_context_menu(QPoint(20, 20)), "balances_context_menu")
    capture_blank_editors(window, operations)
    capture_reference_dialogs(window)
    capture_reports(window)
    capture_edit_dialogs(window)
    capture_tax_windows(window)
    capture_position_windows(window)
    capture_deposit_dialogs(window)
    capture_dialogs(window)
    capture_readme(window, operations)
    window.close()


if __name__ == "__main__":
    main()
