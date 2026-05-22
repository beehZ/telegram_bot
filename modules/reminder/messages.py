WATER = {
    "uz": [
        "Bro suv ichmading {h} soatdan beri \U0001f62d",
        "Suv ichish vaqti! Organizm quruq qolib ketmasin \U0001f4a7",
        "Hayot beruvchi namlik kerak \U0001f4a6",
    ],
    "ru": [
        "Бро, ты не пил воду уже {h} часов \U0001f62d",
        "Время пить воду! Организм не должен пересыхать \U0001f4a7",
        "Живительная влага нужна \U0001f4a6",
    ],
    "en": [
        "Bro you haven't had water in {h} hours \U0001f62d",
        "Time to drink water! Don't let your body dry out \U0001f4a7",
        "Life-giving moisture needed \U0001f4a6",
    ],
}

GYM = {
    "uz": [
        "Gym seni kutyapti... lekin sen yo'qsan \U0001f480",
        "Mushaklaring eslab qolganmi? Gymga bor \U0001f4aa",
        "Bugun push day yoki leg day? Qaror qil \U0001f3cb\ufe0f",
    ],
    "ru": [
        "Зал ждет тебя... а тебя нет \U0001f480",
        "Мышцы помнят тебя? Иди в зал \U0001f4aa",
        "Сегодня день груди или ног? Решай \U0001f3cb\ufe0f",
    ],
    "en": [
        "Gym is waiting for you... but you're not there \U0001f480",
        "Do your muscles still remember you? Go to the gym \U0001f4aa",
        "Push day or leg day? Make a decision \U0001f3cb\ufe0f",
    ],
}

STUDY = {
    "uz": [
        "Dars vaqti! Kelajakdagi sen rahmat aytadi \U0001f4da",
        "O'qishni boshlashga 5... 4... 3... \u23f3",
        "Kitob ochilmay kutyapti \U0001f4d6",
    ],
    "ru": [
        "Время учебы! Будущий ты скажет спасибо \U0001f4da",
        "Начать учиться через 5... 4... 3... \u23f3",
        "Книга ждет, когда ее откроют \U0001f4d6",
    ],
    "en": [
        "Study time! Future you will thank you \U0001f4da",
        "Starting study in 5... 4... 3... \u23f3",
        "The book is waiting to be opened \U0001f4d6",
    ],
}

WORK = {
    "uz": [
        "Ish vaqti! Pul o'zidan-o'zi kelmaydi \U0001f4b0",
        "FOCUS. Ishni tugat keyin dam ol \U0001f4cb",
        "Hozir ishlasang keyin rohatlanasan \U0001f60e",
    ],
    "ru": [
        "Рабочее время! Деньги сами не приходят \U0001f4b0",
        "ФОКУС. Сначала работа, потом отдых \U0001f4cb",
        "Поработай сейчас — отдохнешь потом \U0001f60e",
    ],
    "en": [
        "Work time! Money doesn't come by itself \U0001f4b0",
        "FOCUS. Finish work then rest \U0001f4cb",
        "Work now, chill later \U0001f60e",
    ],
}

SLEEP = {
    "uz": [
        "Uyqu bilan relationship buzilib ketmasin \U0001f62d",
        "Telefonni qo'y, uxlash vaqti \U0001f634",
        "Ertangi kun uchun energiya yig'ish vaqti \U0001f303",
    ],
    "ru": [
        "Не дай отношениям со сном испортиться \U0001f62d",
        "Отложи телефон, пора спать \U0001f634",
        "Время накапливать энергию для завтрашнего дня \U0001f303",
    ],
    "en": [
        "Don't let your relationship with sleep fall apart \U0001f62d",
        "Put the phone down, time to sleep \U0001f634",
        "Time to recharge for tomorrow \U0001f303",
    ],
}

SUPPLEMENT = {
    "uz": [
        "Vitaminlar esdan chiqmasin \U0001f48a",
        "Tanangga kerakli moddalar ber \U0001f9ea",
        "Supplement vaqti! Health is wealth \U0001f4aa",
    ],
    "ru": [
        "Не забудь про витамины \U0001f48a",
        "Дай телу нужные вещества \U0001f9ea",
        "Время добавок! Health is wealth \U0001f4aa",
    ],
    "en": [
        "Don't forget your vitamins \U0001f48a",
        "Give your body what it needs \U0001f9ea",
        "Supplement time! Health is wealth \U0001f4aa",
    ],
}

CUSTOM = {
    "uz": [
        "{text} \u23f0 — eslatma",
        "{text} ni unutmagan edingiz? \U0001f914",
        "Vaqt keldi: {text} \U0001f514",
    ],
    "ru": [
        "{text} \u23f0 — напоминание",
        "Не забыли про {text}? \U0001f914",
        "Время пришло: {text} \U0001f514",
    ],
    "en": [
        "{text} \u23f0 — reminder",
        "Didn't forget about {text}? \U0001f914",
        "Time has come: {text} \U0001f514",
    ],
}

REMINDER_MESSAGES = {
    "water": WATER,
    "gym": GYM,
    "study": STUDY,
    "work": WORK,
    "sleep": SLEEP,
    "supplement": SUPPLEMENT,
    "custom": CUSTOM,
}


def get_reminder_message(rtype: str, lang: str, **kwargs) -> str:
    import random
    bucket = REMINDER_MESSAGES.get(rtype, CUSTOM)
    msgs = bucket.get(lang, bucket.get("uz", []))
    if not msgs:
        return "\u23f0 Reminder!"
    msg = random.choice(msgs)
    if kwargs:
        msg = msg.format(**kwargs)
    return msg
