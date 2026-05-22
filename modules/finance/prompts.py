CATEGORY_LABELS = {
    "food": "🍽️ Ovqat",
    "transport": "🚗 Transport",
    "shopping": "🛍️ Shopping",
    "health": "🏥 Sog'liq",
    "education": "📚 Ta'lim",
    "rent": "🏠 Ijara",
    "gaming": "🎮 Gaming",
    "family": "👨‍👩‍👧 Oila",
    "phone": "📱 Telefon",
    "other": "📦 Boshqa",
    "salary": "💼 Maosh",
    "business": "🏢 Biznes",
    "gift": "🎁 Sovg'a",
    "freelance": "💻 Freelance",
    "debt_return": "🔄 Qarz",
}

CATEGORY_LABELS_RU = {
    "food": "🍽️ Еда",
    "transport": "🚗 Транспорт",
    "shopping": "🛍️ Покупки",
    "health": "🏥 Здоровье",
    "education": "📚 Образование",
    "rent": "🏠 Аренда",
    "gaming": "🎮 Игры",
    "family": "👨‍👩‍👧 Семья",
    "phone": "📱 Телефон",
    "other": "📦 Другое",
    "salary": "💼 Зарплата",
    "business": "🏢 Бизнес",
    "gift": "🎁 Подарок",
    "freelance": "💻 Фриланс",
    "debt_return": "🔄 Долг",
}

CATEGORY_LABELS_EN = {
    "food": "🍽️ Food",
    "transport": "🚗 Transport",
    "shopping": "🛍️ Shopping",
    "health": "🏥 Health",
    "education": "📚 Education",
    "rent": "🏠 Rent",
    "gaming": "🎮 Gaming",
    "family": "👨‍👩‍👧 Family",
    "phone": "📱 Phone",
    "other": "📦 Other",
    "salary": "💼 Salary",
    "business": "🏢 Business",
    "gift": "🎁 Gift",
    "freelance": "💻 Freelance",
    "debt_return": "🔄 Debt",
}


def get_category_label(cat: str, lang: str = "uz") -> str:
    if lang == "ru":
        return CATEGORY_LABELS_RU.get(cat, cat)
    if lang == "en":
        return CATEGORY_LABELS_EN.get(cat, cat)
    return CATEGORY_LABELS.get(cat, cat)
