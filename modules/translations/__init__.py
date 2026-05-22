from typing import Optional


LANGUAGES = ("uz", "ru", "en")

T = {
    "finance": {
        "uz": {
            "dashboard_heading": "💰 Moliya boshqaruvi",
            "today_report": "📊 Bugungi moliyaviy hisobot",
            "no_tx_today": "Bugun hech qanday tranzaksiya yo'q.",
            "income_today": "📈 Kirim: +{amount} so'm",
            "expense_today": "📉 Chiqim: -{amount} so'm",
            "balance": "💰 Balans: {amount} so'm",
            "analytics": "📊 Analytics:",
            "current_balance": "💰 Joriy balans: {amount} so'm",
            "month_income": "📈 Oy boshidan kirim: +{amount} so'm",
            "month_expense": "📉 Oy boshidan chiqim: -{amount} so'm",
            "profit_net": "✅ Sof foyda/zarar: {sign}{amount} so'm",
            "loss_net": "❌ Sof foyda/zarar: {sign}{amount} so'm",
            "last_tx": "📜 Oxirgi tranzaksiyalar:",
            "no_tx_yet": "Hali hech qanday tranzaksiya yo'q.",
            "pick_option": "👇 Quyidagidan birini tanlang:",
            "today_report_title": "📊 Bugungi hisobot",
            "total_income": "💰 Jami kirim:",
            "total_expense": "📉 Jami chiqim:",
            "net_profit": "💵 Sof foyda:",
            "final_balance": "💰 Yakuniy balans:",
            "today_tx": "📜 Bugungi tranzaksiyalar:",
            "income_success": "✅ Kirim qo'shildi: +{amount} so'm",
            "expense_success": "✅ Xarajat qo'shildi: -{amount} so'm",
            "reason": "🧾 Sabab: {desc}",
            "new_balance": "💰 Yangi balans: {amount} so'm",
            "income_error": "❌ Format noto'g'ri.\n\n✅ Misol:\n• 100k\n• 100000\n• 100000 so'm\n• 1m",
            "expense_error": "❌ Noto'g'ri format.\n\n✅ Misol:\n• 50k\n• 50k gas\n• 100000\n• gaz\n• 120k ovqat",
            "need_amount": "📝 \"{desc}\" uchun qancha pul ishlatdingiz?\n\n✅ Misol:\n• 50k\n• 100000\n• 25000",
            "tx_prefix_income": "+",
            "tx_prefix_expense": "-",
            "income_label": "Kirim",
            "expense_label": "Chiqim",
            "btn_income": "➕ Kirim",
            "btn_expense": "➖ Chiqim",
            "btn_calc": "📊 Hisoblash",
            "btn_yana": "🔄 Yana",
            "btn_boldi": "✅ Bo'ldi",
            "yana_income": "👇 Yana kirim qo'shasizmi?",
            "yana_expense": "👇 Yana chiqim qo'shasizmi?",
        },
        "ru": {
            "dashboard_heading": "💰 Управление финансами",
            "today_report": "📊 Сегодняшний финансовый отчет",
            "no_tx_today": "Сегодня нет транзакций.",
            "income_today": "📈 Доход: +{amount} сум",
            "expense_today": "📉 Расход: -{amount} сум",
            "balance": "💰 Баланс: {amount} сум",
            "analytics": "📊 Аналитика:",
            "current_balance": "💰 Текущий баланс: {amount} сум",
            "month_income": "📈 Доход с начала месяца: +{amount} сум",
            "month_expense": "📉 Расход с начала месяца: -{amount} сум",
            "profit_net": "✅ Чистая прибыль/убыток: {sign}{amount} сум",
            "loss_net": "❌ Чистая прибыль/убыток: {sign}{amount} сум",
            "last_tx": "📜 Последние транзакции:",
            "no_tx_yet": "Пока нет транзакций.",
            "pick_option": "👇 Выберите один из вариантов:",
            "today_report_title": "📊 Сегодняшний отчет",
            "total_income": "💰 Общий доход:",
            "total_expense": "📉 Общий расход:",
            "net_profit": "💵 Чистая прибыль:",
            "final_balance": "💰 Итоговый баланс:",
            "today_tx": "📜 Сегодняшние транзакции:",
            "income_success": "✅ Доход добавлен: +{amount} сум",
            "expense_success": "✅ Расход добавлен: -{amount} сум",
            "reason": "🧾 Причина: {desc}",
            "new_balance": "💰 Новый баланс: {amount} сум",
            "income_error": "❌ Неверный формат.\n\n✅ Пример:\n• 100k\n• 100000\n• 100000 сум\n• 1m",
            "expense_error": "❌ Неверный формат.\n\n✅ Пример:\n• 50k\n• 50k gas\n• 100000\n• gaz\n• 120k ovqat",
            "need_amount": "📝 Сколько потратили на \"{desc}\"?\n\n✅ Пример:\n• 50k\n• 100000\n• 25000",
            "tx_prefix_income": "+",
            "tx_prefix_expense": "-",
            "income_label": "Доход",
            "expense_label": "Расход",
            "btn_income": "➕ Доход",
            "btn_expense": "➖ Расход",
            "btn_calc": "📊 Анализ",
            "btn_yana": "🔄 Еще",
            "btn_boldi": "✅ Готово",
            "yana_income": "👇 Добавите еще доход?",
            "yana_expense": "👇 Добавите еще расход?",
        },
        "en": {
            "dashboard_heading": "💰 Finance Management",
            "today_report": "📊 Today's Financial Report",
            "no_tx_today": "No transactions today.",
            "income_today": "📈 Income: +{amount} UZS",
            "expense_today": "📉 Expense: -{amount} UZS",
            "balance": "💰 Balance: {amount} UZS",
            "analytics": "📊 Analytics:",
            "current_balance": "💰 Current Balance: {amount} UZS",
            "month_income": "📈 Month income: +{amount} UZS",
            "month_expense": "📉 Month expense: -{amount} UZS",
            "profit_net": "✅ Net profit/loss: {sign}{amount} UZS",
            "loss_net": "❌ Net profit/loss: {sign}{amount} UZS",
            "last_tx": "📜 Last transactions:",
            "no_tx_yet": "No transactions yet.",
            "pick_option": "👇 Choose an option:",
            "today_report_title": "📊 Today's Report",
            "total_income": "💰 Total Income:",
            "total_expense": "📉 Total Expense:",
            "net_profit": "💵 Net Profit:",
            "final_balance": "💰 Final Balance:",
            "today_tx": "📜 Today's Transactions:",
            "income_success": "✅ Income added: +{amount} UZS",
            "expense_success": "✅ Expense added: -{amount} UZS",
            "reason": "🧾 Reason: {desc}",
            "new_balance": "💰 New Balance: {amount} UZS",
            "income_error": "❌ Invalid format.\n\n✅ Example:\n• 100k\n• 100000\n• 100000 UZS\n• 1m",
            "expense_error": "❌ Invalid format.\n\n✅ Example:\n• 50k\n• 50k gas\n• 100000\n• gaz\n• 120k ovqat",
            "need_amount": "📝 How much did you spend on \"{desc}\"?\n\n✅ Example:\n• 50k\n• 100000\n• 25000",
            "tx_prefix_income": "+",
            "tx_prefix_expense": "-",
            "income_label": "Income",
            "expense_label": "Expense",
            "btn_income": "➕ Income",
            "btn_expense": "➖ Expense",
            "btn_calc": "📊 Analyze",
            "btn_yana": "🔄 Again",
            "btn_boldi": "✅ Done",
            "yana_income": "👇 Add more income?",
            "yana_expense": "👇 Add more expense?",
        },
    },
    "general": {
        "uz": {
            "income_prompt": "👉 Kirim miqdorini kiriting\n\n✅ Misollar:\n• 100k\n• 100000\n• 100000 so'm\n• 1m\n• 1 million",
            "expense_prompt": "👉 Xarajatni kiriting\n\n✅ Misollar:\n• 50k\n• 100000\n• 50k gas\n• 120k ovqat\n• 25000 taxi\n\n💡 Sabab yozish ixtiyoriy.",
            "level": "\U0001f3c6 Level {level} — {title}",
            "xp": "\u26a1 XP: {xp}",
            "streak": "\U0001f525 Streak: {streak} days",
            "achievements": "\U0001f3c5 Achievements: {achievements}",
            "first_time_prompt": "🇺🇿 Tilni tanlang:\n🇷🇺 Выберите язык:\n🇺🇸 Choose language:",
            "confirm_lang": {
                "uz": "✅ Til o'zbek tili qilib belgilandi!",
                "ru": "✅ Язык установлен: русский!",
                "en": "✅ Language set to English!",
            },
            "session_expired": "⏰ Vaqt o'tdi. Yangi buyruq yuboring.",
            "validator_warning": "\u26a0\ufe0f Javob faqat o'zbek tilida bo'lishi kerak edi.",
        },
        "ru": {
            "income_prompt": "👉 Введите сумму дохода\n\n✅ Примеры:\n• 100k\n• 100000\n• 100000 сум\n• 1m\n• 1 million",
            "expense_prompt": "👉 Введите расход\n\n✅ Примеры:\n• 50k\n• 100000\n• 50k gas\n• 120k ovqat\n• 25000 taxi\n\n💡 Указывать причину необязательно.",
            "level": "\U0001f3c6 Уровень {level} — {title}",
            "xp": "\u26a1 XP: {xp}",
            "streak": "\U0001f525 Серия: {streak} дней",
            "achievements": "\U0001f3c5 Достижения: {achievements}",
            "first_time_prompt": "🇺🇿 Tilni tanlang:\n🇷🇺 Выберите язык:\n🇺🇸 Choose language:",
            "confirm_lang": {
                "uz": "✅ Til o'zbek tili qilib belgilandi!",
                "ru": "✅ Язык установлен: русский!",
                "en": "✅ Language set to English!",
            },
            "session_expired": "⏰ Время истекло. Отправьте новую команду.",
            "validator_warning": "\u26a0\ufe0f Ответ должен был быть только на русском языке.",
        },
        "en": {
            "income_prompt": "👉 Enter income amount\n\n✅ Examples:\n• 100k\n• 100000\n• 100000 UZS\n• 1m\n• 1 million",
            "expense_prompt": "👉 Enter expense\n\n✅ Examples:\n• 50k\n• 100000\n• 50k gas\n• 120k ovqat\n• 25000 taxi\n\n💡 Reason is optional.",
            "level": "\U0001f3c6 Level {level} — {title}",
            "xp": "\u26a1 XP: {xp}",
            "streak": "\U0001f525 Streak: {streak} days",
            "achievements": "\U0001f3c5 Achievements: {achievements}",
            "first_time_prompt": "🇺🇿 Tilni tanlang:\n🇷🇺 Выберите язык:\n🇺🇸 Choose language:",
            "confirm_lang": {
                "uz": "✅ Til o'zbek tili qilib belgilandi!",
                "ru": "✅ Язык установлен: русский!",
                "en": "✅ Language set to English!",
            },
            "session_expired": "⏰ Session expired. Send a new command.",
            "validator_warning": "",
        },
    },
    "commentary": {
        "uz": {
            "income": {
                "small": [
                    "Ajoyib, cho'ntak pullari \U0001f60e",
                    "Har bir tiyin hisobga olinadi \U0001f4aa",
                    "Yig'ishda davom et \U0001f4b0",
                ],
                "medium": [
                    "Yaxshi kirim kelib tushdi \U0001f4c8",
                    "Hamyonga zo'r qo'shimcha \U0001f911",
                    "Toza kirim. Respekt \U0001f4af",
                ],
                "large": [
                    "Voy, bu jiddiy pul \U0001f92f",
                    "Katta harakatlar \U0001f525",
                    "Hamyoningiz daraja ko'tardi \U0001f4aa",
                ],
                "huge": [
                    "KATTA kirim ogohlantirishi \U0001f6a8",
                    "Rahbarlik energiyasi \U0001f451",
                    "Bu kirim emas, bu bayonot \U0001f60e",
                ],
            },
            "expense": {
                "tiny": [
                    "Kichik xarajat, tashvishlanma \U0001f44c",
                    "Zo'rg'a seziladi \U0001f60c",
                ],
                "small": [
                    "O'rtacha xarajat \U0001f44d",
                    "Umid qilamanki arzigandi \U0001f60a",
                ],
                "medium": [
                    "Do'stim, bu jiddiy xarajat \U0001f62e",
                    "Hamyoningiz buni his qildi \U0001f480",
                    "Pul yaxshi sarflandimi? Umid qilamiz \U0001f914",
                ],
                "large": [
                    "Bu tezlikda Ferrari yana bir yil kechikdi \U0001f62d",
                    "Hamyon omon qolish uchun kurashmoqda \U0001f92a",
                    "Bu katta bo'lak \U0001f628",
                ],
                "huge": [
                    "Do'stim... bugungi xarajat xavfli bo'lyapti \U0001f630",
                    "Hamyoningiz jiddiy zarba oldi \U0001f480",
                    "Moliyaviy barqarorlik ketdi \U0001f4a8",
                ],
                "food": [
                    "Hech bo'lmasa mazali taom bo'lgan bo'lsa \U0001f60b",
                    "Ovqat har doim kerak \U0001f372",
                    "Ovqatlanish kerak, to'g'ri xarajat ✅",
                ],
                "transport": [
                    "Harakatlanish narxi \U0001f698",
                    "Transport solig'i \U0001f6b2",
                    "Harakat uchun pul \U0001f697",
                ],
                "game_entertainment": [
                    "O'yin - o'z-o'zini parvarish qilish \U0001f3ae",
                    "Ko'ngilochar byudjet ishlayapti \U0001f3b5",
                    "O'zingizni siylang \U0001f381",
                ],
                "health": [
                    "Salomatlik > boylik \U0001f4aa",
                    "O'zingizga aqlli sarmoya \U000e001f",
                    "Tana va aql birinchi o'rinda \U0001f9cd",
                ],
            },
            "balance": {
                "critical": [
                    "Balans omon qolish uchun kurashmoqda \U0001f6c8",
                    "Do'stim balansingiz yig'layapti \U0001f97a",
                ],
                "low": [
                    "Oqilona ishlating \U0001f914",
                    "Ehtiyot bo'ling \U0001f6b8",
                ],
                "good": [
                    "Sog'lom ko'rinadi \U0001f4b0",
                    "Balans holati a'lo \U0001f60e",
                ],
                "great": [
                    "Bank hisobingiz maqtanmoqda \U0001f4aa",
                    "To'plangan \U0001f4b8",
                    "Kelajakdagi siz g'alaba qozonadi \U0001f947",
                ],
            },
            "streak": {
                3: ["3-kun. O'zingizni ko'rsatyapsiz \U0001f525", "3 kun kuchli \U0001f4aa"],
                5: ["5-kun! Barqarorlik muvaffaqiyat kaliti \U0001f511", "5 kunlik streak. Respekt \U0001f4af"],
                7: ["Bir hafta! Moliyaviy jihatdan xavfli bo'lyapsiz \U0001f92f", "7 kun. To'xtatib bo'lmas energiya \U0001f680"],
                10: ["10 kun. Afsona yaratilmoqda \U0001f451", "Ikki xonali streak! \U0001f389"],
                14: ["14 kun. Moliyaviy intizom xudosi \U0001f64f", "Ikki hafta kuchli! \U0001f4c8"],
                21: ["21 kun. Odat mustahkamlandi \U0001f512", "Uch hafta. Siz boshqachasiz \U0001f60e"],
                30: ["30 kun. Oylik afsona \U0001f3c6", "To'liq oylik streak. Siz hukmronlik qilyapsiz \U0001f451"],
            },
            "achievements": {
                "first_tx": "\U0001f389 Achievement: Birinchi qadam",
                "first_income": "\U0001f389 Achievement: Pul kelyapti",
                "first_expense": "\U0001f389 Achievement: Pul ketyapti",
                "streak_3": "\U0001f525 Achievement: Yonmoqda (3 kun)",
                "streak_7": "\U0001f451 Achievement: To'xtatib bo'lmas (7 kun)",
                "streak_14": "\U0001f3c6 Achievement: Afsonaviy (14 kun)",
                "big_spender": "\U0001f92f Achievement: Katta sarf",
                "big_earner": "\U0001f911 Achievement: Katta topuvchi",
                "transactions_5": "\U0001f4cb Achievement: Tejamkor (5 tranzaksiya)",
                "transactions_10": "\U0001f4ca Achievement: Kuzatuvchi (10 tranzaksiya)",
                "transactions_20": "\U0001f4c8 Achievement: Bag'ishlangan (20 tranzaksiya)",
            },
            "level_up": [
                "\U0001f389 LEVEL UP! Siz hozir {title}!",
                "\U0001f4c8 Level up: {title}! Davom eting!",
                "\u2b50 Yangi daraja: {title}",
            ],
        },
        "ru": {
            "income": {
                "small": [
                    "Отлично, карманные деньги \U0001f60e",
                    "Каждая копейка на счету \U0001f4aa",
                    "Копите дальше \U0001f4b0",
                ],
                "medium": [
                    "Хороший доход поступил \U0001f4c8",
                    "Отличное пополнение кошелька \U0001f911",
                    "Чистый доход. Респект \U0001f4af",
                ],
                "large": [
                    "Ого, это серьезные деньги \U0001f92f",
                    "Большие движения \U0001f525",
                    "Ваш кошелек повысил уровень \U0001f4aa",
                ],
                "huge": [
                    "СЕРЬЕЗНЫЙ доход \U0001f6a8",
                    "Энергия директора \U0001f451",
                    "Это не доход, это заявление \U0001f60e",
                ],
            },
            "expense": {
                "tiny": [
                    "Маленькая трата, не волнуйтесь \U0001f44c",
                    "Едва заметно \U0001f60c",
                ],
                "small": [
                    "Разумный расход \U0001f44d",
                    "Надеюсь, оно того стоило \U0001f60a",
                ],
                "medium": [
                    "Бро, это приличная трата \U0001f62e",
                    "Ваш кошелек это почувствовал \U0001f480",
                    "Деньги потрачены с умом? Надеемся \U0001f914",
                ],
                "large": [
                    "Такими темпами Ferrari откладывается еще на год \U0001f62d",
                    "Кошелек борется за выживание \U0001f92a",
                    "Это большой кусок \U0001f628",
                ],
                "huge": [
                    "Бро... сегодняшние траты становятся опасными \U0001f630",
                    "Ваш кошелек получил критический урон \U0001f480",
                    "Финансовая стабильность покинула чат \U0001f4a8",
                ],
                "food": [
                    "Надеюсь, еда была вкусной \U0001f60b",
                    "Еда — это святое \U0001f372",
                    "Надо есть, оправданный расход ✅",
                ],
                "transport": [
                    "Передвижение стоит денег \U0001f698",
                    "Транспортный налог \U0001f6b2",
                    "Деньги на мобильность \U0001f697",
                ],
                "game_entertainment": [
                    "Игры — это забота о себе \U0001f3ae",
                    "Развлекательный бюджет работает \U0001f3b5",
                    "Побалуйте себя \U0001f381",
                ],
                "health": [
                    "Здоровье > богатство \U0001f4aa",
                    "Умная инвестиция в себя \U000e001f",
                    "Тело и разум прежде всего \U0001f9cd",
                ],
            },
            "balance": {
                "critical": [
                    "Баланс борется за жизнь \U0001f6c8",
                    "Бро, твой баланс плачет \U0001f97a",
                ],
                "low": [
                    "Используйте с умом \U0001f914",
                    "Действуйте осторожно \U0001f6b8",
                ],
                "good": [
                    "Выглядит здорово \U0001f4b0",
                    "Баланс в порядке \U0001f60e",
                ],
                "great": [
                    "Ваш банковский счет красуется \U0001f4aa",
                    "Накоплено \U0001f4b8",
                    "Будущий вы побеждаете \U0001f947",
                ],
            },
            "streak": {
                3: ["3-й день. Вы показываете себя \U0001f525", "3 дня силы \U0001f4aa"],
                5: ["5-й день! Постоянство — ключ к успеху \U0001f511", "5-дневная серия. Респект \U0001f4af"],
                7: ["Неделя! Вы становитесь финансово опасным \U0001f92f", "7 дней. Неостановимая энергия \U0001f680"],
                10: ["10 дней. Легенда в процессе \U0001f451", "Двузначная серия! \U0001f389"],
                14: ["14 дней. Бог финансовой дисциплины \U0001f64f", "Две недели силы! \U0001f4c8"],
                21: ["21 день. Привычка закреплена \U0001f512", "Три недели. Вы особенный \U0001f60e"],
                30: ["30 дней. Месячная легенда \U0001f3c6", "Полный месяц серии. Вы рулите \U0001f451"],
            },
            "achievements": {
                "first_tx": "\U0001f389 Achievement: Первый шаг",
                "first_income": "\U0001f389 Achievement: Деньги приходят",
                "first_expense": "\U0001f389 Achievement: Деньги уходят",
                "streak_3": "\U0001f525 Achievement: В огне (3 дня)",
                "streak_7": "\U0001f451 Achievement: Неостановимый (7 дней)",
                "streak_14": "\U0001f3c6 Achievement: Легендарный (14 дней)",
                "big_spender": "\U0001f92f Achievement: Большой трата",
                "big_earner": "\U0001f911 Achievement: Большой заработок",
                "transactions_5": "\U0001f4cb Achievement: Экономный (5 транзакций)",
                "transactions_10": "\U0001f4ca Achievement: Наблюдатель (10 транзакций)",
                "transactions_20": "\U0001f4c8 Achievement: Преданный (20 транзакций)",
            },
            "level_up": [
                "\U0001f389 LEVEL UP! Теперь вы {title}!",
                "\U0001f4c8 Level up: {title}! Продолжайте в том же духе!",
                "\u2b50 Новый уровень: {title}",
            ],
        },
        "en": {
            "income": {
                "small": [
                    "Nice, pocket money vibes \U0001f60e",
                    "Every bit counts \U0001f4aa",
                    "Stack it up \U0001f4b0",
                ],
                "medium": [
                    "Solid income coming in \U0001f4c8",
                    "Good addition to the wallet \U0001f911",
                    "Clean income. Respect \U0001f4af",
                ],
                "large": [
                    "Damn, that's serious money \U0001f92f",
                    "Big moves \U0001f525",
                    "Your wallet just leveled up \U0001f4aa",
                ],
                "huge": [
                    "MAJOR income alert \U0001f6a8",
                    "CEO energy right there \U0001f451",
                    "That's not income, that's a statement \U0001f60e",
                ],
            },
            "expense": {
                "tiny": [
                    "Tiny spend, no worries \U0001f44c",
                    "Barely a dent \U0001f60c",
                ],
                "small": [
                    "Reasonable expense \U0001f44d",
                    "Hope it was worth it \U0001f60a",
                ],
                "medium": [
                    "Bro that's a decent spend \U0001f62e",
                    "Your wallet felt that one \U0001f480",
                    "Money well spent? Hope so \U0001f914",
                ],
                "large": [
                    "At this rate Ferrari delayed another year \U0001f62d",
                    "Wallet fighting for survival right now \U0001f92a",
                    "That's a big chunk \U0001f628",
                ],
                "huge": [
                    "Bro... today's spending is getting dangerous \U0001f630",
                    "Your wallet just took critical damage \U0001f480",
                    "Financial stability left the chat \U0001f4a8",
                ],
                "food": [
                    "Hope it was good food at least \U0001f60b",
                    "Food is always valid \U0001f372",
                    "Gotta eat, valid expense ✅",
                ],
                "transport": [
                    "Getting places costs \U0001f698",
                    "Transport tax \U0001f6b2",
                    "Mobility money \U0001f697",
                ],
                "game_entertainment": [
                    "Gaming is self-care \U0001f3ae",
                    "Entertainment budget doing work \U0001f3b5",
                    "Treat yourself \U0001f381",
                ],
                "health": [
                    "Health > wealth \U0001f4aa",
                    "Smart investment in yourself \U000e001f",
                    "Body and mind first \U0001f9cd",
                ],
            },
            "balance": {
                "critical": [
                    "Balance fighting for its life \U0001f6c8",
                    "Bro your balance is crying \U0001f97a",
                ],
                "low": [
                    "Use it wisely \U0001f914",
                    "Tread carefully \U0001f6b8",
                ],
                "good": [
                    "Looking healthy \U0001f4b0",
                    "Solid balance vibes \U0001f60e",
                ],
                "great": [
                    "Your bank account is flexing \U0001f4aa",
                    "Stacked \U0001f4b8",
                    "Future you is winning \U0001f947",
                ],
            },
            "streak": {
                3: ["Day 3 streak. You're showing up \U0001f525", "3 days strong \U0001f4aa"],
                5: ["Day 5! Consistency is key \U0001f511", "5-day streak. Respect \U0001f4af"],
                7: ["One week strong! You're becoming financially dangerous \U0001f92f", "7 days. Unstoppable energy \U0001f680"],
                10: ["10 days. Legend in the making \U0001f451", "Double digits streak! \U0001f389"],
                14: ["14 days. Financial discipline god \U0001f64f", "Two weeks strong! \U0001f4c8"],
                21: ["21 days. Habit locked in \U0001f512", "Three weeks. You're different \U0001f60e"],
                30: ["30 days. Monthly legend \U0001f3c6", "Full month streak. You run this \U0001f451"],
            },
            "achievements": {
                "first_tx": "\U0001f389 Achievement: First Step",
                "first_income": "\U0001f389 Achievement: Money Coming",
                "first_expense": "\U0001f389 Achievement: Money Going",
                "streak_3": "\U0001f525 Achievement: On Fire (3-day streak)",
                "streak_7": "\U0001f451 Achievement: Unstoppable (7-day streak)",
                "streak_14": "\U0001f3c6 Achievement: Legendary (14-day streak)",
                "big_spender": "\U0001f92f Achievement: Big Spender",
                "big_earner": "\U0001f911 Achievement: Big Earner",
                "transactions_5": "\U0001f4cb Achievement: Saver (5 transactions)",
                "transactions_10": "\U0001f4ca Achievement: Tracker (10 transactions)",
                "transactions_20": "\U0001f4c8 Achievement: Dedicated (20 transactions)",
            },
            "level_up": [
                "\U0001f389 LEVEL UP! You're now {title}!",
                "\U0001f4c8 Level up: {title}! Keep grinding!",
                "\u2b50 New level unlocked: {title}",
            ],
        },
    },
    "validator": {
        "uz": "\u26a0\ufe0f Unfortunately, I need to respond in English as requested.",
        "ru": "\u26a0\ufe0f К сожалению, я вынужден ответить на русском, как запрошено.",
        "en": "",
    },
}


def t(category: str, key: str, lang: str = "uz", **kwargs) -> str:
    lang = lang if lang in LANGUAGES else "uz"
    text = T[category][lang][key]
    if kwargs:
        text = text.format(**kwargs)
    return text


def t_nested(category: str, sub: str, key: str, lang: str = "uz") -> str:
    lang = lang if lang in LANGUAGES else "uz"
    return T[category][lang][sub][key]


def confirm_lang_text(lang: str, selected_lang: str) -> str:
    return T["general"][lang]["confirm_lang"][selected_lang]


def fin_income_prompt(lang: str) -> str:
    return t("general", "income_prompt", lang)


def fin_expense_prompt(lang: str) -> str:
    return t("general", "expense_prompt", lang)


LANG_LOCK_RULES = {
    "uz": (
        "IMPORTANT: "
        "You MUST reply ONLY in Uzbek language (lotin). "
        "NEVER use English. NEVER use Russian. "
        "All responses must be fully Uzbek. "
        "Never include translations. Never switch languages."
    ),
    "ru": (
        "IMPORTANT: "
        "You MUST reply ONLY in Russian language. "
        "NEVER use Uzbek. NEVER use English. "
        "All responses must be fully Russian. "
        "Never include translations. Never switch languages."
    ),
    "en": (
        "IMPORTANT: "
        "You MUST reply ONLY in English language. "
        "NEVER use Uzbek. NEVER use Russian. "
        "All responses must be fully English. "
        "Never include translations. Never switch languages."
    ),
}


def get_ai_lang_rule(lang: str) -> str:
    return LANG_LOCK_RULES.get(lang, LANG_LOCK_RULES["uz"])


def validate_language(text: str, lang: str) -> Optional[str]:
    if lang == "uz":
        cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
        latin_en = sum(1 for c in text if 'a' <= c.lower() <= 'z')
        if cyrillic > 10 and latin_en > 10:
            return f"\n\n{t('general', 'validator_warning', 'uz')}"
    elif lang == "ru":
        latin = sum(1 for c in text if 'a' <= c.lower() <= 'z')
        if latin > len(text) * 0.3:
            return None
    return None


def lang_suffix(lang: str) -> str:
    return {"uz": "uz", "ru": "ru", "en": "en"}.get(lang, "uz")
