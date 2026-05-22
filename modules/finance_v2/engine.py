from typing import Optional

from .store import FinanceStore
from .parser import NumberParser
from .keyboards import finance_kb, yana_boldi_kb
from modules.translations import t, LANGUAGES


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _lang(l: str) -> str:
    return l if l in LANGUAGES else "uz"


class FinanceBotEngine:
    def __init__(self, store: FinanceStore):
        self.store = store
        self.parser = NumberParser()

    # ── Dashboard (response to /money) ──

    def build_dashboard(self, user_id: str, lang: str = "uz") -> str:
        L = _lang(lang)
        user = self.store.get(user_id)
        today_txs = self.store.get_today_transactions(user_id)
        last_txs = self.store.get_last_transactions(user_id, 5)
        net = user.income_total - user.expense_total
        net_sign = "+" if net >= 0 else ""

        lines = [t("finance", "dashboard_heading", L) + "\n"]

        lines.append(t("finance", "today_report", L))
        if today_txs:
            today_income = sum(tx["amount"] for tx in today_txs if tx["type"] == "income")
            today_expense = sum(tx["amount"] for tx in today_txs if tx["type"] == "expense")
            if today_income:
                lines.append(t("finance", "income_today", L, amount=_fmt(today_income)))
            if today_expense:
                lines.append(t("finance", "expense_today", L, amount=_fmt(today_expense)))
        else:
            lines.append(t("finance", "no_tx_today", L))

        lines.append("")
        lines.append(t("finance", "balance", L, amount=_fmt(user.balance)))
        lines.append("")

        lines.append(t("finance", "analytics", L))
        lines.append(t("finance", "current_balance", L, amount=_fmt(user.balance)))
        lines.append(t("finance", "month_income", L, amount=_fmt(user.income_total)))
        lines.append(t("finance", "month_expense", L, amount=_fmt(user.expense_total)))
        net_label = "✅" if net >= 0 else "❌"
        key = "profit_net" if net >= 0 else "loss_net"
        lines.append(t("finance", key, L, sign=net_sign, amount=_fmt(net)))
        lines.append("")

        lines.append(t("finance", "last_tx", L))
        if last_txs:
            for tx in reversed(last_txs):
                sign = "+" if tx["type"] == "income" else "-"
                ts = tx["timestamp"][:19].replace("T", " ")
                desc = tx.get("description", "")
                if desc and desc != "No description":
                    lines.append(f"• {ts} | {sign}{_fmt(tx['amount'])} so'm | {desc}")
                else:
                    lines.append(f"• {ts} | {sign}{_fmt(tx['amount'])} so'm")
        else:
            lines.append(t("finance", "no_tx_yet", L))

        lines.append("")
        lines.append(t("finance", "pick_option", L))

        return "\n".join(lines)

    # ── Analytics (response to Hisoblash button) ──

    def build_analytics(self, user_id: str, lang: str = "uz") -> str:
        L = _lang(lang)
        user = self.store.get(user_id)
        net = user.income_total - user.expense_total
        last_txs = self.store.get_last_transactions(user_id, 10)

        lines = [t("finance", "today_report_title", L) + "\n"]
        lines.append(t("finance", "total_income", L))
        lines.append(f"+{_fmt(user.income_total)} so'm\n")
        lines.append(t("finance", "total_expense", L))
        lines.append(f"-{_fmt(user.expense_total)} so'm\n")
        lines.append(t("finance", "net_profit", L))
        lines.append(f"{_fmt(net)} so'm\n")
        lines.append(t("finance", "balance", L, amount=_fmt(user.balance)))
        lines.append("")

        lines.append(t("finance", "last_tx", L))
        if last_txs:
            for tx in reversed(last_txs):
                sign = "+" if tx["type"] == "income" else "-"
                desc = tx.get("description", "")
                if desc and desc != "No description":
                    lines.append(f"• {sign}{_fmt(tx['amount'])} so'm | {desc}")
                else:
                    lines.append(f"• {sign}{_fmt(tx['amount'])} so'm")
        else:
            lines.append(t("finance", "no_tx_yet", L))

        return "\n".join(lines)

    # ── Daily Summary (response to Bo'ldi) ──

    def build_daily_summary(self, user_id: str, lang: str = "uz") -> str:
        L = _lang(lang)
        user = self.store.get(user_id)
        today_txs = self.store.get_today_transactions(user_id)
        net = user.income_total - user.expense_total

        lines = [t("finance", "today_report_title", L) + "\n"]
        lines.append(t("finance", "total_income", L))
        lines.append(f"+{_fmt(user.income_total)} so'm\n")
        lines.append(t("finance", "total_expense", L))
        lines.append(f"-{_fmt(user.expense_total)} so'm\n")
        lines.append(t("finance", "net_profit", L))
        lines.append(f"{_fmt(net)} so'm\n")
        lines.append(t("finance", "final_balance", L, amount=_fmt(user.balance)))

        lines.append("")
        lines.append(t("finance", "today_tx", L))
        if today_txs:
            for tx in today_txs:
                sign = "+" if tx["type"] == "income" else "-"
                desc = tx.get("description", "")
                if desc and desc != "No description":
                    lines.append(f"• {sign}{_fmt(tx['amount'])} so'm | {desc}")
                else:
                    lines.append(f"• {sign}{_fmt(tx['amount'])} so'm")
        else:
            lines.append(t("finance", "no_tx_yet", L))

        return "\n".join(lines)

    # ── Income Input Handler ──

    def handle_income_input(self, user_id: str, text: str, lang: str = "uz") -> dict:
        L = _lang(lang)
        amount = self.parser.parse_amount(text)
        if amount is None:
            return {
                "ok": False,
                "message": t("finance", "income_error", L),
            }
        self.store.add_transaction(user_id, "income", amount, "")
        user = self.store.get(user_id)
        msg = (
            t("finance", "income_success", L, amount=_fmt(amount)) + "\n"
            + t("finance", "new_balance", L, amount=_fmt(user.balance))
        )
        return {
            "ok": True,
            "message": msg,
            "amount": amount,
            "balance": user.balance,
        }

    # ── Expense Input Handler ──

    def handle_expense_input(self, user_id: str, text: str, lang: str = "uz") -> dict:
        L = _lang(lang)
        amount, description = self.parser.parse_expense(text)

        if amount is None and not description:
            return {
                "ok": False,
                "message": t("finance", "expense_error", L),
            }

        if amount is None and description:
            self.store.set_pending_desc(user_id, description)
            return {
                "ok": False,
                "need_amount": True,
                "pending_desc": description,
                "message": t("finance", "need_amount", L, desc=description),
            }

        pending_desc = self.store.get_pending_desc(user_id)
        if pending_desc:
            description = pending_desc
            self.store.clear_pending_desc(user_id)

        self.store.add_transaction(user_id, "expense", amount, description)
        user = self.store.get(user_id)

        lines = [t("finance", "expense_success", L, amount=_fmt(amount))]
        if description and description != "No description":
            lines.append(t("finance", "reason", L, desc=description))
        lines.append(t("finance", "balance", L, amount=_fmt(user.balance)))

        return {
            "ok": True,
            "amount": amount,
            "balance": user.balance,
            "description": description,
            "message": "\n".join(lines),
        }

    # ── Keyboards ──

    def get_kb(self):
        return finance_kb()

    def get_yana_kb(self, action: str = "income"):
        return yana_boldi_kb(action)
