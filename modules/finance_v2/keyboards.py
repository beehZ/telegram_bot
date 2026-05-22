from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def finance_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Kirim", callback_data="fin:income"),
            InlineKeyboardButton(text="➖ Chiqim", callback_data="fin:expense"),
            InlineKeyboardButton(text="📊 Hisoblash", callback_data="fin:calc"),
        ],
    ])


def yana_boldi_kb(action: str = "income") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Yana", callback_data=f"fin:yana:{action}"),
            InlineKeyboardButton(text="✅ Bo'ldi", callback_data=f"fin:boldi:{action}"),
        ],
    ])
