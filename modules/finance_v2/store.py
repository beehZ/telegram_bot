from datetime import datetime, timezone


class UserFinanceData:
    __slots__ = ("user_id", "balance", "income_total", "expense_total", "state", "transactions", "pending_expense_desc")

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.balance = 0
        self.income_total = 0
        self.expense_total = 0
        self.state = "idle"
        self.transactions = []
        self.pending_expense_desc = ""

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "balance": self.balance,
            "income_total": self.income_total,
            "expense_total": self.expense_total,
            "state": self.state,
            "transactions": self.transactions,
        }


class FinanceStore:
    def __init__(self):
        self._users: dict[str, UserFinanceData] = {}

    def get(self, user_id: str) -> UserFinanceData:
        if user_id not in self._users:
            self._users[user_id] = UserFinanceData(user_id)
        return self._users[user_id]

    def set_state(self, user_id: str, state: str):
        self.get(user_id).state = state

    def get_state(self, user_id: str) -> str:
        return self.get(user_id).state

    def reset_state(self, user_id: str):
        self.get(user_id).state = "idle"

    def add_transaction(self, user_id: str, tx_type: str, amount: int, description: str = "") -> dict:
        user = self.get(user_id)
        tx = {
            "type": tx_type,
            "amount": amount,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        user.transactions.append(tx)
        if tx_type == "income":
            user.balance += amount
            user.income_total += amount
        else:
            user.balance -= amount
            user.expense_total += amount
        return tx

    def set_pending_desc(self, user_id: str, desc: str):
        self.get(user_id).pending_expense_desc = desc

    def get_pending_desc(self, user_id: str) -> str:
        return self.get(user_id).pending_expense_desc

    def clear_pending_desc(self, user_id: str):
        self.get(user_id).pending_expense_desc = ""

    def get_last_transactions(self, user_id: str, n: int = 5) -> list:
        user = self.get(user_id)
        return user.transactions[-n:]

    def get_today_transactions(self, user_id: str) -> list:
        user = self.get(user_id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return [tx for tx in user.transactions if tx["timestamp"].startswith(today)]

    def reset(self, user_id: str):
        self._users.pop(user_id, None)

    def count(self) -> int:
        return len(self._users)
