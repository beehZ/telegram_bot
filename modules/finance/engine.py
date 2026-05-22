from datetime import datetime, timedelta
from typing import Optional

from goal_system.database import Database
from modules.finance.parser import FinanceParser, FinanceParserResult
from modules.finance.prompts import get_category_label


class FinanceEngine:
    def __init__(self, db: Database):
        self.db = db
        self.parser = FinanceParser()

    async def process_text(self, uid: int, text: str) -> Optional[FinanceParserResult]:
        result = self.parser.parse(text)
        if not result.is_valid:
            return None
        return result

    async def confirm_and_save(self, uid: int, result: FinanceParserResult, raw_text: str = "") -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        return await self.db.add_transaction(
            uid=uid,
            amount=result.amount,
            tx_type=result.tx_type,
            category=result.category,
            description=result.description[:200],
            date=today,
            raw_text=raw_text or result.description[:200],
        )

    async def save_from_parsed(self, uid: int, data: dict) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        return await self.db.add_transaction(
            uid=uid,
            amount=data["amount"],
            tx_type=data["tx_type"],
            category=data["category"],
            description=data.get("description", data.get("raw_text", ""))[:200],
            date=today,
            raw_text=data.get("raw_text", ""),
        )

    async def get_balance(self, uid: int) -> float:
        return await self.db.get_balance(uid)

    async def get_today_summary(self, uid: int, lang: str = "uz") -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        day = await self.db.get_daily_finance(uid, today)
        balance = await self.db.get_balance(uid)

        labels = {
            "uz": {"title": "📊 *Bugungi moliyaviy hisobot*", "income": "Kirim", "expense": "Chiqim", "balance": "Balans", "count": "Tranzaksiyalar", "none": "Bugun hech qanday tranzaksiya yo'q."},
            "ru": {"title": "📊 *Финансовый отчет за сегодня*", "income": "Доход", "expense": "Расход", "balance": "Баланс", "count": "Транзакции", "none": "Сегодня нет транзакций."},
            "en": {"title": "📊 *Today's Finance Report*", "income": "Income", "expense": "Expense", "balance": "Balance", "count": "Transactions", "none": "No transactions today."},
        }
        lbl = labels.get(lang, labels["uz"])

        if not day or day["transaction_count"] == 0:
            return f"{lbl['title']}\n\n{lbl['none']}\n\n💰 {lbl['balance']}: {balance:,.0f} so'm"

        lines = [
            lbl["title"], "",
            f"💰 {lbl['balance']}: {balance:,.0f} so'm",
            f"📈 {lbl['income']}: +{day['total_income']:,.0f} so'm",
            f"📉 {lbl['expense']}: -{day['total_expense']:,.0f} so'm",
            f"🔄 {lbl['count']}: {day['transaction_count']}",
        ]
        return "\n".join(lines)

    async def get_detailed_analytics(self, uid: int, lang: str = "uz") -> str:
        today = datetime.now()
        month_start = today.replace(day=1).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        balance = await self.db.get_balance(uid)
        stats = await self.db.get_monthly_stats(uid, today.year, today.month)
        expense_cats = await self.db.get_category_breakdown(uid, "expense", month_start, today_str)
        income_cats = await self.db.get_category_breakdown(uid, "income", month_start, today_str)

        labels = {
            "uz": {
                "title": "📈 *Moliyaviy Analytics*",
                "balance": "Joriy balans",
                "month_income": "Oy boshidan kirim",
                "month_expense": "Oy boshidan chiqim",
                "net": "Sof foyda/zarar",
                "daily_avg": "O'rtacha kunlik chiqim",
                "days_left": "Oy oxiriga kun qoldi",
                "projected": "Prognoz oylik chiqim",
                "expense_breakdown": "Chiqim kategoriyalari",
                "income_breakdown": "Kirim kategoriyalari",
                "none": "Ma'lumot yo'q",
            },
            "ru": {
                "title": "📈 *Финансовая аналитика*",
                "balance": "Текущий баланс",
                "month_income": "Доход с начала месяца",
                "month_expense": "Расход с начала месяца",
                "net": "Чистая прибыль/убыток",
                "daily_avg": "Средний дневной расход",
                "days_left": "Дней до конца месяца",
                "projected": "Прогнозируемый расход",
                "expense_breakdown": "Категории расходов",
                "income_breakdown": "Категории доходов",
                "none": "Нет данных",
            },
            "en": {
                "title": "📈 *Financial Analytics*",
                "balance": "Current balance",
                "month_income": "Month-to-date income",
                "month_expense": "Month-to-date expense",
                "net": "Net profit/loss",
                "daily_avg": "Avg daily expense",
                "days_left": "Days left in month",
                "projected": "Projected monthly expense",
                "expense_breakdown": "Expense by category",
                "income_breakdown": "Income by category",
                "none": "No data",
            },
        }
        lbl = labels.get(lang, labels["uz"])
        total_income = stats["total_income"] if stats else 0
        total_expense = stats["total_expense"] if stats else 0
        net = total_income - total_expense

        lines = [lbl["title"], "",
                 f"💰 {lbl['balance']}: {balance:,.0f} so'm",
                 f"📈 {lbl['month_income']}: +{total_income:,.0f} so'm",
                 f"📉 {lbl['month_expense']}: -{total_expense:,.0f} so'm",
                 f"{'✅' if net >= 0 else '❌'} {lbl['net']}: {net:+,.0f} so'm"]

        doy = today.day
        if doy > 0 and total_expense > 0:
            avg_daily = total_expense / doy
            days_in_month = 30
            days_left = days_in_month - doy
            projected = avg_daily * days_in_month
            lines.extend([
                "",
                f"📊 {lbl['daily_avg']}: {avg_daily:,.0f} so'm",
                f"📅 {lbl['days_left']}: {days_left}",
                f"🔮 {lbl['projected']}: {projected:,.0f} so'm",
            ])

        if expense_cats:
            lines.extend(["", f"📉 *{lbl['expense_breakdown']}*:"])
            for c in expense_cats:
                cat_label = get_category_label(c["category"], lang)
                lines.append(f"  • {cat_label}: {c['total']:,.0f} so'm ({c['count']}x)")

        if income_cats:
            lines.extend(["", f"📈 *{lbl['income_breakdown']}*:"])
            for c in income_cats:
                cat_label = get_category_label(c["category"], lang)
                lines.append(f"  • {cat_label}: {c['total']:,.0f} so'm ({c['count']}x)")

        return "\n".join(lines)

    async def get_recent_transactions(self, uid: int, limit: int = 10, lang: str = "uz") -> str:
        txs = await self.db.get_transactions(uid, limit)
        if not txs:
            msgs = {
                "uz": "Hali hech qanday tranzaksiya yo'q.",
                "ru": "Пока нет транзакций.",
                "en": "No transactions yet.",
            }
            return msgs.get(lang, msgs["uz"])

        lines = []
        for tx in txs:
            sign = "+" if tx["tx_type"] == "income" else "-"
            cat_label = get_category_label(tx["category"], lang)
            lines.append(
                f"{tx['date']} | {sign}{tx['amount']:,.0f} so'm | {cat_label}"
            )
        return "\n".join(lines)

    async def format_confirmation(self, result: FinanceParserResult, lang: str = "uz") -> str:
        sign = "➕" if result.tx_type == "income" else "➖"
        type_label = {"income": "Kirim", "expense": "Chiqim"}.get(result.tx_type, "?")
        cat_label = get_category_label(result.category, lang)

        return (
            f"{sign} *{type_label}*: {result.amount:,.0f} so'm\n"
            f"📂 *Kategoriya*: {cat_label}\n"
            f"📝 {result.description[:100]}"
        )
