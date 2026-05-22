MOOD_RESPONSES = {
    "good": {
        "uz": [
            "Nice \U0001f525 momentum yaxshi ketayapti",
            "Zo'r! Bugun ajoyib kun bo'lgan \U0001f44c",
            "Shu energiya bilan davom et \U0001f680",
        ],
        "ru": [
            "Круто \U0001f525 импульс хороший",
            "Отлично! Сегодня был прекрасный день \U0001f44c",
            "Продолжай в том же духе \U0001f680",
        ],
        "en": [
            "Nice \U0001f525 momentum is going strong",
            "Great! Today was an amazing day \U0001f44c",
            "Keep that energy going \U0001f680",
        ],
    },
    "mid": {
        "uz": [
            "Stable day. Lekin ko'proq potential bor \U0001f4c8",
            "O'rtacha kun. Ertaga yaxshiroq bo'ladi \U0001f60a",
            "Normal. Barqarorlik ham muvaffaqiyat \U0001f4aa",
        ],
        "ru": [
            "Стабильный день. Но потенциал больше \U0001f4c8",
            "Средний день. Завтра будет лучше \U0001f60a",
            "Нормально. Стабильность — тоже успех \U0001f4aa",
        ],
        "en": [
            "Stable day. But there's more potential \U0001f4c8",
            "Average day. Tomorrow will be better \U0001f60a",
            "Normal. Stability is also success \U0001f4aa",
        ],
    },
    "bad": {
        "uz": [
            "Bro bugun og'ir bo'lgan ekan... lekin bu normal \U0001f4aa",
            "Yomon kunlar ham bo'ladi. Ertaga yangi kun \U0001f31e",
            "Tushkunlikka tushma. Har bir kun yangi imkoniyat \U0001f525",
        ],
        "ru": [
            "Бро, сегодня был тяжелый день... но это нормально \U0001f4aa",
            "Бывают плохие дни. Завтра новый день \U0001f31e",
            "Не унывай. Каждый день — новая возможность \U0001f525",
        ],
        "en": [
            "Bro today was rough... but that's normal \U0001f4aa",
            "Bad days happen. Tomorrow is a new day \U0001f31e",
            "Don't be down. Every day is a new chance \U0001f525",
        ],
    },
}

STREAK_MESSAGES = {
    "uz": {
        3: "3 kunlik check-in streak \U0001f525 consistency boshlanyapti",
        7: "Bir hafta! 7-day streak \U0001f451",
        14: "14 kun. Bu endi odat bo'lyapti \U0001f4c8",
        21: "21 kun. Siz boshqachasiz \U0001f60e",
        30: "Bir oylik streak! Legend \U0001f3c6",
    },
    "ru": {
        3: "3-дневная серия \U0001f525 последовательность начинается",
        7: "Неделя! 7-дневная серия \U0001f451",
        14: "14 дней. Это становится привычкой \U0001f4c8",
        21: "21 день. Вы особенный \U0001f60e",
        30: "Месячная серия! Легенда \U0001f3c6",
    },
    "en": {
        3: "3-day check-in streak \U0001f525 consistency is starting",
        7: "One week! 7-day streak \U0001f451",
        14: "14 days. This is becoming a habit \U0001f4c8",
        21: "21 days. You're different \U0001f60e",
        30: "Monthly streak! Legend \U0001f3c6",
    },
}


def get_mood_response(mood: str, lang: str) -> str:
    import random
    bucket = MOOD_RESPONSES.get(mood, MOOD_RESPONSES["mid"])
    msgs = bucket.get(lang, bucket.get("uz", []))
    return random.choice(msgs)


def get_streak_message(streak: int, lang: str) -> str:
    milestones = sorted(STREAK_MESSAGES.get(lang, STREAK_MESSAGES["uz"]).keys())
    for m in reversed(milestones):
        if streak >= m:
            return STREAK_MESSAGES.get(lang, STREAK_MESSAGES["uz"])[m]
    return ""
