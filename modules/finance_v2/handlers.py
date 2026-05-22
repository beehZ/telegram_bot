from aiogram import types, Dispatcher, F
from aiogram.filters import Command, BaseFilter
from aiogram.types import InlineKeyboardMarkup

from .engine import FinanceBotEngine
from .store import FinanceStore
from .keyboards import finance_kb


class _FinanceStateFilter(BaseFilter):
    def __init__(self, store: FinanceStore):
        self.store = store

    async def __call__(self, message: types.Message) -> bool:
        if not message.text or message.text.startswith("/"):
            return False
        uid = str(message.from_user.id)
        state = self.store.get_state(uid)
        return state in ("awaiting_income", "awaiting_expense")


def register_handlers(dp: Dispatcher, engine: FinanceBotEngine, store: FinanceStore):

    @dp.message(Command("money"))
    async def cmd_money(message: types.Message):
        uid = str(message.from_user.id)
        store.reset_state(uid)
        text = engine.build_dashboard(uid)
        await message.answer(text, reply_markup=finance_kb())

    @dp.callback_query(F.data == "fin:income")
    async def on_income_btn(callback: types.CallbackQuery):
        uid = str(callback.from_user.id)
        store.set_state(uid, "awaiting_income")
        prompt = "👉 Kirim miqdorini kiriting (faqat raqam yoki k formatida)"
        await _update_or_answer(callback, prompt)
        await callback.answer()

    @dp.callback_query(F.data == "fin:expense")
    async def on_expense_btn(callback: types.CallbackQuery):
        uid = str(callback.from_user.id)
        store.set_state(uid, "awaiting_expense")
        prompt = "👉 Pulni nima uchun ishlatdingiz va qancha? (misol: 50000 gas uchun)"
        await _update_or_answer(callback, prompt)
        await callback.answer()

    @dp.callback_query(F.data == "fin:calc")
    async def on_calc_btn(callback: types.CallbackQuery):
        uid = str(callback.from_user.id)
        text = engine.build_analytics(uid)
        await _update_or_answer(callback, text, finance_kb())
        await callback.answer()

    @dp.message(F.text, _FinanceStateFilter(store))
    async def finance_input_handler(message: types.Message):
        uid = str(message.from_user.id)
        state = store.get_state(uid)
        if state == "awaiting_income":
            result = engine.handle_income_input(uid, message.text)
        else:
            result = engine.handle_expense_input(uid, message.text)
        await message.answer(result)


async def _update_or_answer(
    callback: types.CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)
