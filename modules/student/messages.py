EXAM_URGENT = {
    "uz": [
        "Exam yaqinlashyapti... lekin sen hali start qilmagansan \U0001f480",
        "{subject} examiga {days} kun qoldi! \u23f0",
        "Vaqt kamayyapti. {subject} ni takrorlash vaqti \U0001f4da",
    ],
    "ru": [
        "Экзамен приближается... а ты еще не начал \U0001f480",
        "До экзамена по {subject} осталось {days} дней! \u23f0",
        "Время уходит. Пора повторять {subject} \U0001f4da",
    ],
    "en": [
        "Exam is coming... and you haven't started yet \U0001f480",
        "{days} days left until {subject} exam! \u23f0",
        "Time is running out. Time to review {subject} \U0001f4da",
    ],
}

EXAM_ACTIVE = {
    "uz": [
        "This is the discipline arc starting \U0001f525",
        "{subject} uchun tayyorgarlik ketyapti \U0001f4c8",
        "Har bir kun muhim. {subject} ni birga yengamiz \U0001f4aa",
    ],
    "ru": [
        "Это начало дисциплины \U0001f525",
        "Подготовка к {subject} идет полным ходом \U0001f4c8",
        "Каждый день важен. Вместе мы осилим {subject} \U0001f4aa",
    ],
    "en": [
        "This is the discipline arc starting \U0001f525",
        "Preparation for {subject} is in full swing \U0001f4c8",
        "Every day counts. We'll conquer {subject} together \U0001f4aa",
    ],
}

STUDY_LOW = {
    "uz": [
        "Bugun atigi {hours} soat... ko'proq bo'lishi mumkin edi \U0001f914",
        "Kechagi kun samarasiz. Ertaga 2x harakat qil \U0001f4aa",
        "{hours} soat? Bo'lishi mumkin edi \U0001f62e",
    ],
    "ru": [
        "Всего {hours} часов сегодня... могло быть больше \U0001f914",
        "Вчерашний день был непродуктивным. Завтра старайся в 2 раза больше \U0001f4aa",
        "{hours} часов? Могло бы быть лучше \U0001f62e",
    ],
    "en": [
        "Only {hours} hours today... could be more \U0001f914",
        "Yesterday was unproductive. Try 2x harder tomorrow \U0001f4aa",
        "{hours} hours? Could be better \U0001f62e",
    ],
}

STUDY_GOOD = {
    "uz": [
        "{hours} soat o'qish. Solid \U0001f4aa",
        "Yaxshi natija. Shu tezlikda davom et \U0001f525",
        "Discipline level increasing 📈",
    ],
    "ru": [
        "{hours} часов учебы. Солидно \U0001f4aa",
        "Хороший результат. Продолжай в том же темпе \U0001f525",
        "Уровень дисциплины растет 📈",
    ],
    "en": [
        "{hours} hours of study. Solid \U0001f4aa",
        "Good result. Keep the pace \U0001f525",
        "Discipline level increasing 📈",
    ],
}

HOMEWORK_PROMPT = {
    "uz": [
        "{task} — buni bugun qilish kerak \U0001f4cb",
        "Unutmagan bo'lsang kerak: {task} \U0001f514",
    ],
    "ru": [
        "{task} — это нужно сделать сегодня \U0001f4cb",
        "Надеюсь, ты не забыл: {task} \U0001f514",
    ],
    "en": [
        "{task} — need to do this today \U0001f4cb",
        "Hope you didn't forget: {task} \U0001f514",
    ],
}

FOCUS_START = {
    "uz": [
        "\U0001f9e0 Focus mode. 25 daqiqa. Hech narsa chalg'itmasin",
        "Pomodoro boshlandi \u23f1\ufe0f 25 min focus",
    ],
    "ru": [
        "\U0001f9e0 Режим фокуса. 25 минут. Ничто не должно отвлекать",
        "Помодоро началось \u23f1\ufe0f 25 мин фокуса",
    ],
    "en": [
        "\U0001f9e0 Focus mode. 25 minutes. Nothing should distract you",
        "Pomodoro started \u23f1\ufe0f 25 min focus",
    ],
}

FOCUS_DONE = {
    "uz": [
        "Focus session tugadi! 5 min break \u23f3",
        "\u2705 Pomodoro completed! Dam olish vaqti \U0001f60c",
    ],
    "ru": [
        "Сессия фокуса завершена! 5 мин перерыв \u23f3",
        "\u2705 Помодоро завершен! Время отдыхать \U0001f60c",
    ],
    "en": [
        "Focus session done! 5 min break \u23f3",
        "\u2705 Pomodoro completed! Time to rest \U0001f60c",
    ],
}


def get_exam_message(user_id: int, subject: str, days_left: int, has_studied: bool, lang: str) -> str:
    import random
    if days_left <= 3 and not has_studied:
        bucket = EXAM_URGENT
    else:
        bucket = EXAM_ACTIVE
    msgs = bucket.get(lang, bucket["uz"])
    msg = random.choice(msgs)
    return msg.format(subject=subject, days=days_left)


def get_study_message(hours: float, lang: str) -> str:
    import random
    bucket = STUDY_GOOD if hours >= 3 else STUDY_LOW
    msgs = bucket.get(lang, bucket["uz"])
    msg = random.choice(msgs)
    return msg.format(hours=hours)


def get_homework_reminder(task: str, lang: str) -> str:
    import random
    msgs = HOMEWORK_PROMPT.get(lang, HOMEWORK_PROMPT["uz"])
    msg = random.choice(msgs)
    return msg.format(task=task)


def get_focus_message(key: str, lang: str) -> str:
    import random
    bucket = FOCUS_START if key == "start" else FOCUS_DONE
    msgs = bucket.get(lang, bucket["uz"])
    return random.choice(msgs)
