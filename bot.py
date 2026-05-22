import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from enum import Enum
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
import requests
from PIL import Image
from aiogram import Bot, Dispatcher, F, types, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionSender
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

from goal_system.database import Database
from goal_system.handlers import GoalHandlers
from goal_system.reminders import ReminderManager
from goal_system.progress import ProgressTracker
from goal_system.prompts import MAIN_SYSTEM_PROMPT, lang_rule
from goal_system.discipline_engine import DisciplineEngine
from goal_system.reminder_engine import ReminderEngine
from goal_system.report_service import build_daily_report, build_weekly_report
from goal_system.discipline_keyboards import quick_complete_kb
from goal_system.task_activation import ManualTaskTracker
from modules.finance.engine import FinanceEngine
from modules.finance.prompts import get_category_label
from modules.finance.parser import FinanceParserResult
from modules.finance_v2 import FinanceStore, FinanceBotEngine
from modules.personality import PersonalityEngine, ProfileStore, GamificationStore
from modules.food.engine import NutritionEngine
from modules.food.parser import FoodParser
from modules.food.ai_engine import AINutritionEngine, format_result as ai_format_result
from modules.db import LifeDB
from modules.scheduler import SchedulerCoordinator
from modules.reminder import ReminderEngine as LifeReminderEngine
from modules.checkin import CheckinEngine
from modules.student import StudentEngine

from aiogram.exceptions import TelegramBadRequest


async def safe_edit_text(message, text, reply_markup=None, **kwargs):
    try:
        await message.edit_text(text, reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


load_dotenv()

logger = logging.getLogger("hf_bot")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
logger.addHandler(handler)

TOKEN_FILE = Path(__file__).parent / "tg_api.txt"
FALLBACK_TOKEN = "8251454340:AAHZMwMGlB72tqZmG2mWhSVdhe1F2bCVXAs"

HF_API_KEY = os.getenv("HF_API_KEY")
if not HF_API_KEY:
    logger.critical("HF_API_KEY is not set in .env file")
    sys.exit(1)

HF_BASE_URL = "https://router.huggingface.co/v1/chat/completions"
MAIN_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
FALLBACK_MODEL = "NousResearch/Hermes-2-Pro-Llama-3-8B"
VISION_MODEL = "meta-llama/Llama-3.2-11B-Vision-Instruct"
VISION_FALLBACK_MODEL = "Qwen/Qwen2-VL-7B-Instruct"

MAX_HISTORY_ROUNDS = 10
MAX_MESSAGE_LENGTH = 3500

SYSTEM_PROMPT = "You are a helpful AI assistant. Respond concisely and accurately."

from modules.translations import get_ai_lang_rule, fin_income_prompt, fin_expense_prompt, t as tr


def _build_locked_prompt(lang: str) -> str:
    rule = get_ai_lang_rule(lang)
    return MAIN_SYSTEM_PROMPT.format(language_rule=rule)

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
DEFAULT_LIMIT = 2000

FOOD_STATE_IDLE = "idle"

MAIN_KBD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/goal"), KeyboardButton(text="/missions")],
        [KeyboardButton(text="/food_calorie"), KeyboardButton(text="/money")],
        [KeyboardButton(text="/progress"), KeyboardButton(text="/profile")],
        
    ],
    resize_keyboard=True,
)

LANG_KBD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🇺🇿 Uzbek", callback_data="lang_uz")],
    [InlineKeyboardButton(text="🇷🇺 Russian", callback_data="lang_ru")],
    [InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")],
])


def get_token() -> str:
    try:
        if TOKEN_FILE.exists():
            token = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if token:
                return token
    except OSError as e:
        logger.warning("Failed to read token file: %s", e)
    return FALLBACK_TOKEN


def split_message(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts = []
    while len(text) > max_len:
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = text.rfind(". ", 0, max_len)
        if split_at == -1:
            split_at = text.rfind(" ", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        parts.append(text)
    return parts


def query_hf(messages: list[dict], model: str, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    resp = requests.post(HF_BASE_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


async def download_image(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.read()


def compress_image(image_bytes: bytes, max_size: int = 1024, quality: int = 80) -> bytes:
    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P", "PA"):
        img = img.convert("RGB")
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def image_to_data_uri(image_bytes: bytes) -> str:
    compressed = compress_image(image_bytes)
    b64 = base64.b64encode(compressed).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def query_vision(
    history: list[dict],
    image_data_uri: str,
    user_prompt: str,
    api_key: str,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    content = [
        {"type": "image_url", "image_url": {"url": image_data_uri}},
        {"type": "text", "text": user_prompt},
    ]
    messages = list(history) + [{"role": "user", "content": content}]

    models = [VISION_MODEL, VISION_FALLBACK_MODEL]
    for model in models:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500,
            }
            resp = requests.post(HF_BASE_URL, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.HTTPError as e:
            logger.warning(
                "Vision model %s failed (HTTP %d): %s",
                model, e.response.status_code, e.response.text,
            )
            if e.response.status_code == 401:
                raise
        except requests.exceptions.Timeout:
            logger.warning("Vision model %s timed out", model)
        except requests.exceptions.ConnectionError as e:
            logger.warning("Vision model %s connection error: %s", model, e)

    raise RuntimeError("All vision models failed")


class UserMemory:
    def __init__(self):
        self._data: dict[int, list[dict]] = defaultdict(list)

    def get(self, user_id: int) -> list[dict]:
        return self._data[user_id]

    def add(self, user_id: int, entry: dict):
        self._data[user_id].append(entry)

    def reset(self, user_id: int, lang: str = "uz"):
        prompt = _build_locked_prompt(lang)
        self._data[user_id] = [{"role": "system", "content": prompt}]

    def ensure_system(self, user_id: int, lang: str = "uz"):
        if not self._data[user_id]:
            prompt = _build_locked_prompt(lang)
            self._data[user_id] = [{"role": "system", "content": prompt}]

    def update_language(self, user_id: int, lang: str):
        prompt = _build_locked_prompt(lang)
        if self._data[user_id]:
            self._data[user_id][0] = {"role": "system", "content": prompt}
        else:
            self._data[user_id] = [{"role": "system", "content": prompt}]

    def trim(self, user_id: int):
        messages = self._data[user_id]
        while len(messages) > MAX_HISTORY_ROUNDS * 2 + 1:
            sys_prompt = messages[0]
            rest = messages[1:]
            dropped = rest[:2]
            messages = [sys_prompt] + rest[2:]
            logger.debug("Trimmed %d old messages for user %s", len(dropped), user_id)
        self._data[user_id] = messages


memory = UserMemory()

# ── User Session Manager ──────────────────────

FOOD_MODE_TIMEOUT = 120


class UserSession:
    def __init__(self):
        self.active_mode = "idle"
        self.mode_started_at = 0.0
        self.last_message_at = 0.0
        self.awaiting_food_input = False
        self.awaiting_food_clarification = False
        self.awaiting_mission_number = False
        self.awaiting_finance_input = False
        self.pending_finance: dict | None = None

    def reset(self):
        self.__init__()


class UserSessionManager:
    def __init__(self):
        self._sessions: dict[int, UserSession] = defaultdict(UserSession)

    def get(self, user_id: int) -> UserSession:
        return self._sessions[user_id]

    def reset(self, user_id: int):
        self._sessions[user_id] = UserSession()

    def set_mode(self, user_id: int, mode: str):
        s = self.get(user_id)
        s.active_mode = mode
        s.mode_started_at = time.time()
        s.last_message_at = time.time()

    def touch(self, user_id: int):
        self._sessions[user_id].last_message_at = time.time()

    def is_expired(self, user_id: int) -> bool:
        s = self._sessions.get(user_id)
        if s is None or s.active_mode == "idle":
            return False
        return time.time() - s.last_message_at > FOOD_MODE_TIMEOUT


class FoodTracker:
    def __init__(self):
        self._data: dict[int, dict] = defaultdict(self._fresh)

    def _fresh(self) -> dict:
        return {"date": "", "meals": [], "total_cal": 0, "limit": DEFAULT_LIMIT, "_state": FOOD_STATE_IDLE}

    def _today(self, uid: int):
        today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        if self._data[uid]["date"] != today:
            self._data[uid] = self._fresh()
            self._data[uid]["date"] = today

    def state(self, uid: int) -> str:
        return self._data[uid].get("_state", FOOD_STATE_IDLE)

    def set_state(self, uid: int, s: str):
        self._data[uid]["_state"] = s

    def reset_state(self, uid: int):
        self._data[uid]["_state"] = FOOD_STATE_IDLE
        self._data[uid].pop("_pending", None)

    def pending(self, uid: int) -> dict | None:
        return self._data[uid].get("_pending")

    def set_pending(self, uid: int, d: dict):
        self._data[uid]["_pending"] = d

    def remain(self, uid: int) -> int:
        self._today(uid)
        return self._data[uid]["limit"] - self._data[uid]["total_cal"]

    def add_meal(self, uid: int, meal: dict):
        self._today(uid)
        self._data[uid]["meals"].append(meal)
        self._data[uid]["total_cal"] += meal.get("calories", 0)

    def set_limit(self, uid: int, val: int):
        self._today(uid)
        self._data[uid]["limit"] = val

    def summary(self, uid: int, lang: str = "uz") -> str:
        self._today(uid)
        d = self._data[uid]
        rem = d["limit"] - d["total_cal"]
        labels = {
            "uz": {"title": "📊 *Kunlik hisobot*", "ate": f"🔥 Yeyilgan: {d['total_cal']} / {d['limit']} kcal", "left": f"✅ Qolgan: {rem} kcal", "meals": "*Ovqatlar:*", "none": "Hali hech narsa yemadingiz."},
            "ru": {"title": "📊 *Дневной отчет*", "ate": f"🔥 Съедено: {d['total_cal']} / {d['limit']} ккал", "left": f"✅ Осталось: {rem} ккал", "meals": "*Приемы пищи:*", "none": "Вы еще ничего не ели."},
            "en": {"title": "📊 *Daily Summary*", "ate": f"🔥 Consumed: {d['total_cal']} / {d['limit']} kcal", "left": f"✅ Remaining: {rem} kcal", "meals": "*Meals:*", "none": "No meals logged yet."},
        }
        lbl = labels.get(lang, labels["uz"])
        lines = [lbl["title"], "", lbl["ate"], lbl["left"], ""]
        if d["meals"]:
            lines.append(lbl["meals"])
            for m in d["meals"]:
                lines.append(f"• {m.get('name', '?')} — {m.get('calories', 0)} kcal")
        else:
            lines.append(lbl["none"])
        return "\n".join(lines)


food_tracker = FoodTracker()
db = Database()
session_manager = UserSessionManager()

# ── Intent Classification ─────────────────────


class Intent(str, Enum):
    COMMAND = "command"
    FOOD_INPUT = "food_input"
    GOAL_COMPLETION = "goal_completion"
    MISSION_NUMBER = "mission_number"
    NUMERIC_INPUT = "numeric_input"
    FINANCE_EXPENSE = "finance_expense"
    FINANCE_INCOME = "finance_income"
    GENERAL_CHAT = "general_chat"
    UNKNOWN = "unknown"


GOAL_COMPLETION_MARKERS = [
    "bajarildi", "done", "completed", "finished",
    "tugadi", "bitdi", "yakunlandi", "tayyor",
]

FOOD_KEYWORDS = [
    "osh", "non", "tuxum", "coffee", "tea", "choy", "suv", "water",
    "cola", "manti", "somsa", "shashlik", "burger", "pizza",
    "shurva", "lagman", "plov", "kebab", "salat", "soup",
    "mastava", "chuchvara", "norin", "dimlama", "shovla",
    "moshxo'rda", "do'lma", "go'ja", "bo'g'irsoq", "xonim",
    "bishtak", "hasib", "qozon kabob", "qovurma", "moshkichiri",
    "mantar", "qovoq somsa", "ko'k somsa", "hot-dog", "sendvich",
    "tako", "burrito", "pasta", "spagetti", "lazanya", "steyk",
    "sushi", "ramen", "selyodka", "forel", "sazan", "sudak",
    "losos", "tunets", "krab", "krevetka", "kalmar", "lobster",
    "olivye", "vinegret", "shakarob", "achchiq-chuchuk",
    "mimoza", "chizkeyk", "tiramisu", "brauni", "ekler",
    "napoleon", "asalli tort", "shokoladli tort", "panna kotta",
    "falafel", "xumus", "shavarma", "doner", "pita",
    "baba ganush", "tabbule", "baklava", "lukum", "omlet",
    "glazunya", "skrebl", "frittata", "quiche",
    "qaynatilgan tuxum", "guruch", "grechka", "perlovka",
    "yachmen", "kinoa", "bulgur", "banan", "olma", "nok",
    "uzum", "anjir", "anor", "pistirma", "qovurdoq", "jiz-biz",
    "beshmarmok", "ugra", "chalop", "atala", "halim", "sumalak",
    "nisholda", "pashmak", "holva", "chak-chak", "qatlama",
    "lochira", "patir", "obinon", "gijda", "zog'ora",
    "go'sht", "tovuq", "baliq", "sabzi", "kartoshka",
    "guruch", "makaron", "shokolad", "cake", "cookie",
    "sut", "milk", "yogurt", "pishloq", "cheese",
    "sariyog'", "yog'", "non", "bread", "egg", "banana",
    "apple", "rice", "chicken", "fish", "meat",
    "juice", "sharbat", "sok", "watermelon", "tarvuz",
    "qovun", "shaftoli", "peach", "qulupnay", "strawberry",
    "apelsin", "orange", "mandarin", "gilos", "cherry",
    "beetroot", "lavlagi", "karam", "cabbage", "piyoz", "onion",
    "qalampir", "bodring", "cucumber", "pomidor", "tomato",
    "sabzi", "carrot", "mosh", "loviya", "no'xat",
    "kolbasa", "sosiska", "chips", "qazi", "kazi",
    "muesli", "oatmeal", "suli", "yorma",
    "asal", "honey", "murabbo", "jam", "konfet", "pechenye",
    "pirog", "tort", "spaghetti", "steak", "sandwich", "wrap",
    "noodle", "porridge", "cereal", "toast", "avocado", "broccoli",
    "spinach", "carrot", "potato", "chocolate", "donut",
    "ice cream", "smoothie", "protein shake",
]

NON_FOOD_INDICATORS = [
    "bajarildi", "done", "completed", "finished", "tugadi",
    "mission", "progress", "streak", "goal", "profile",
    "hello", "salom", "hi", "hey",
    "math", "english", "programming", "fitness",
    "gain muscle", "lose weight", "social",
]


class IntentClassifier:
    @staticmethod
    def classify(text: str, session: UserSession) -> Intent:
        t = text.lower().strip()

        for marker in GOAL_COMPLETION_MARKERS:
            if marker in t:
                return Intent.GOAL_COMPLETION

        if t.isdigit():
            if session.active_mode == "food_tracking":
                return Intent.FOOD_INPUT
            return Intent.MISSION_NUMBER

        if t.replace(".", "", 1).isdigit():
            return Intent.FOOD_INPUT

        # ── Finance detection (passive, before general/food) ──
        from modules.finance.parser import FinanceParser
        fp_result = FinanceParser.parse(text)
        if fp_result.is_valid:
            return Intent.FINANCE_INCOME if fp_result.tx_type == "income" else Intent.FINANCE_EXPENSE

        for nf in NON_FOOD_INDICATORS:
            if nf in t:
                return Intent.GENERAL_CHAT

        for fk in FOOD_KEYWORDS:
            if fk in t:
                return Intent.FOOD_INPUT

        if session.active_mode == "food_tracking":
            words = t.split()
            if len(words) <= 5:
                return Intent.FOOD_INPUT

        return Intent.GENERAL_CHAT

    @staticmethod
    def looks_like_food(text: str) -> bool:
        return FoodParser.is_likely_food(text)

storage = MemoryStorage()
bot = Bot(token=get_token())
dp = Dispatcher(storage=storage)


class CommandStateCleaner(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: dict):
        if event.text and event.text.startswith("/"):
            state = data.get("state")
            if state:
                await state.clear()
        return await handler(event, data)


dp.message.middleware(CommandStateCleaner())


def meal_type() -> str:
    h = datetime.now(TASHKENT_TZ).hour
    if 6 <= h < 12:
        return "breakfast"
    if 12 <= h < 17:
        return "lunch"
    if 17 <= h < 22:
        return "dinner"
    return "snack"


def greeting(lang: str = "uz") -> str:
    m = meal_type()
    msgs = {
        "uz": {
            "breakfast": "🌅 Hayrli tong!\n\nErtalabki nonushta vaqtida nimalar yedingiz?",
            "lunch": "☀️ Hayrli kun!\n\nHozir tushlik vaqtida nimalar yedingiz?",
            "dinner": "🌆 Hayrli kech!\n\nKechki ovqat vaqtida nimalar yedingiz?",
            "snack": "🌙 Kech bo'ldi!\n\nKechki snack vaqtida nimalar yedingiz?",
        },
        "ru": {
            "breakfast": "🌅 Доброе утро!\n\nЧто вы ели на завтрак?",
            "lunch": "☀️ Добрый день!\n\nЧто вы ели на обед?",
            "dinner": "🌆 Добрый вечер!\n\nЧто вы ели на ужин?",
            "snack": "🌙 Уже поздно!\n\nЧто вы ели на перекус?",
        },
        "en": {
            "breakfast": "🌅 Good morning!\n\nWhat did you have for breakfast?",
            "lunch": "☀️ Good afternoon!\n\nIt is lunch time! What did you eat?",
            "dinner": "🌆 Good evening!\n\nWhat did you have for dinner?",
            "snack": "🌙 Late night!\n\nWhat did you have for a snack?",
        },
    }
    return msgs.get(lang, msgs["en"]).get(m, msgs["en"]["breakfast"])





# ── Language System ───────────────────────────────

async def get_lang_or_prompt(uid: int, msg_obj, is_start: bool = False):
    lang = await db.get_language(uid)
    if not lang or lang not in ("uz", "ru", "en"):
        # first time — ask language
        await msg_obj.answer(
            "🇺🇿 Tilni tanlang:\n🇷🇺 Выберите язык:\n🇺🇸 Choose language:",
            reply_markup=LANG_KBD,
        )
        return None
    return lang


@dp.callback_query(F.data.startswith("lang_"))
async def on_lang_select(callback: types.CallbackQuery, state=None):
    uid = callback.from_user.id
    lang = callback.data.split("_")[1]
    await db.set_language(uid, lang)
    memory.update_language(uid, lang)
    await callback.answer()
    from modules.translations import confirm_lang_text
    await callback.message.edit_text(confirm_lang_text(lang, lang))
    if state:
        await state.clear()
    await cmd_start_logic(callback.message, uid)


async def cmd_start_logic(message: types.Message, uid: int):
    lang = await db.get_language(uid)
    memory.reset(uid, lang)
    food_tracker.reset_state(uid)
    session_manager.reset(uid)
    msgs = {
        "uz": "🚀 *AI LIFE OPERATING SYSTEM*\n\n"
              "*Sizning shaxsiy AI hayot tizimingiz!*\n\n"
              "🏋️ AI Fitness & Nutrition Coach\n"
              "📚 AI Study & Learning Mentor\n"
              "🧠 AI Discipline & Productivity System\n"
              "💼 AI Career & Growth Strategist\n\n"
               "Asosiy buyruqlar:\n"
               "🎯 /goal — Maqsadlarni belgilash va tizim yaratish\n"
               "🔥 /missions — Kunlik missiyalar\n"
               "🧠 /profile — AI profilingiz\n"
               "🍽️ /food_calorie — Kaloriya hisoblash\n"
               "💰 /money — Moliya boshqaruvi\n"
               "📊 /progress — Haftalik hisobot\n"
               "🔥 /streak — Streyklaringiz\n"
               "📋 /summary — Kunlik ovqat hisoboti\n\n"
               "_AI Life Coach doim siz bilan — maqsadlaringizni boshlang!_",

        "ru": "🚀 *AI LIFE OPERATING SYSTEM*\n\n"
               "*Ваша персональная AI система жизни!*\n\n"
               "🏋️ ИИ Фитнес и Нутрициолог\n"
               "📚 ИИ Учебный и Научный Наставник\n"
               "🧠 ИИ Система Дисциплины и Продуктивности\n"
               "💼 ИИ Карьерный Стратег\n\n"
               "Основные команды:\n"
               "🎯 /goal — Постановка целей и создание системы\n"
               "🔥 /missions — Ежедневные миссии\n"
               "🧠 /profile — AI профиль\n"
               "🍽️ /food_calorie — Подсчет калорий\n"
               "💰 /money — Управление финансами\n"
               "📊 /progress — Еженедельный отчет\n"
               "🔥 /streak — Ваши серии\n"
               "📋 /summary — Дневной отчет по еде\n\n"
               "_AI Life Coach всегда с вами — начните свои цели!_",

        "en": "🚀 *AI LIFE OPERATING SYSTEM*\n\n"
               "*Your personal AI life system is ready!*\n\n"
               "🏋️ AI Fitness & Nutrition Coach\n"
               "📚 AI Study & Learning Mentor\n"
               "🧠 AI Discipline & Productivity System\n"
               "💼 AI Career & Growth Strategist\n\n"
               "Core commands:\n"
               "🎯 /goal — Set goals & build your system\n"
               "🔥 /missions — Today's daily missions\n"
               "🧠 /profile — View your AI profile\n"
               "🍽️ /food_calorie — Track calories\n"
               "💰 /money — Finance management\n"
               "📊 /progress — Weekly progress report\n"
               "🔥 /streak — Your streaks\n"
               "📋 /summary — Daily food summary\n\n"
               "_Your AI Life Coach is always with you — start your transformation!_",
    }
    await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state=None):
    uid = message.from_user.id
    if state:
        await state.clear()
    lang = await get_lang_or_prompt(uid, message)
    if lang is None:
        return
    await cmd_start_logic(message, uid)


@dp.message(Command("language"))
async def cmd_language(message: types.Message):
    await message.answer(
        "🇺🇿 Tilni tanlang:\n🇷🇺 Выберите язык:\n🇺🇸 Choose language:",
        reply_markup=LANG_KBD,
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    msgs = {
        "uz": (
            "🚀 *AI LIFE OPERATING SYSTEM*\n\n"
            "🎯 *MAQSADLAR & TIZIM:*\n"
            "/goal — Maqsadlarni belgilash (4 kategoriya)\n"
            "/missions — Kunlik AI missiyalar 🔥\n"
            "/profile — AI profilingiz 🧠\n"
            "/progress — Haftalik hisobot 📊\n"
            "/streak — Streyklaringiz 🔥\n\n"
             "🍽️ *OVQATLANISH:*\n"
             "/food_calorie — Ovqat yozish 🍽️\n"
             "/summary — Bugungi kaloriya hisobi\n"
             "/limit <kcal> — Kunlik limit belgilash\n\n"
             "💰 *MOLIYA:*\n"
             "/money — Moliya boshqaruvi 💰\n\n"
             "⏰ *LIFE TIZIMI:*\n"
             "/reminder — Reminderlarni boshqarish ⏰\n"
             "/checkin — Kunlik check-in 📝\n"
             "/study — Dars vaqtini yozish 📚\n"
             "/exam — Imtihonlarni boshqarish 📋\n"
             "/focus — Pomodoro fokus 🎯\n"
             "/homework — Topshiriqlarni boshqarish 📝\n\n"
             "💬 *UMUMIY:*\n"
             "/start — Boshlash\n"
             "/language — Tilni o'zgartirish 🌐\n"
             "/clear — Tarix va holatlarni tozalash\n"
             "/cancel — Jarayonlarni bekor qilish ⛔\n"
             "/help — Yordam"
        ),
        "ru": (
            "🚀 *AI LIFE OPERATING SYSTEM*\n\n"
            "🎯 *ЦЕЛИ И СИСТЕМЫ:*\n"
            "/goal — Постановка целей (4 категории)\n"
            "/missions — Ежедневные AI миссии 🔥\n"
            "/profile — AI профиль 🧠\n"
            "/progress — Еженедельный отчет 📊\n"
            "/streak — Ваши серии 🔥\n\n"
            "🍽️ *ПИТАНИЕ:*\n"
            "/food_calorie — Запись еды 🍽️\n"
            "/summary — Дневной отчет по калориям\n"
            "/limit <ккал> — Установить дневной лимит\n\n"
            "💰 *ФИНАНСЫ:*\n"
             "/money — Управление финансами 💰\n\n"
             "⏰ *LIFE СИСТЕМА:*\n"
             "/reminder — Управление напоминаниями ⏰\n"
             "/checkin — Ежедневный чек-ин 📝\n"
             "/study — Запись времени учебы 📚\n"
             "/exam — Управление экзаменами 📋\n"
             "/focus — Pomodoro фокус 🎯\n"
             "/homework — Управление заданиями 📝\n\n"
            "💬 *ОБЩЕЕ:*\n"
            "/start — Начать\n"
            "/language — Сменить язык 🌐\n"
            "/clear — Сбросить историю и состояния\n"
            "/cancel — Остановить процессы ⛔\n"
            "/help — Помощь"
        ),
        "en": (
            "🚀 *AI LIFE OPERATING SYSTEM*\n\n"
            "🎯 *GOALS & SYSTEMS:*\n"
            "/goal — Set goals (4 categories)\n"
            "/missions — Daily AI missions 🔥\n"
            "/profile — Your AI profile 🧠\n"
            "/progress — Weekly report 📊\n"
            "/streak — Your streaks 🔥\n\n"
            "🍽️ *NUTRITION:*\n"
            "/food_calorie — Log a meal 🍽️\n"
            "/summary — Today's calorie summary\n"
            "/limit <kcal> — Set daily limit\n\n"
            "💰 *FINANCE:*\n"
             "/money — Finance dashboard 💰\n\n"
             "⏰ *LIFE SYSTEM:*\n"
             "/reminder — Manage reminders ⏰\n"
             "/checkin — Daily mood check-in 📝\n"
             "/study — Log study hours 📚\n"
             "/exam — Manage exams 📋\n"
             "/focus — Pomodoro focus timer 🎯\n"
             "/homework — Manage homework 📝\n\n"
            "💬 *GENERAL:*\n"
            "/start — Welcome screen\n"
            "/language — Change language 🌐\n"
            "/clear — Reset history & states\n"
            "/cancel — Cancel all processes ⛔\n"
            "/help — This message"
        ),
    }
    await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)


@dp.message(Command("clear"))
async def cmd_clear(message: types.Message, state=None):
    if state:
        await state.clear()
    uid = message.from_user.id
    memory.reset(uid)
    food_tracker.reset_state(uid)
    session_manager.reset(uid)
    await message.answer("All states and history cleared.")


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state=None):
    if state:
        await state.clear()
    uid = message.from_user.id
    session_manager.reset(uid)
    lang = await db.get_language(uid)
    msgs = {
        "uz": "✅ Barcha jarayonlar to'xtatildi. Asosiy menyuga qaytingiz.\n\nYangi buyruq yuboring yoki tugmalardan foydalaning.",
        "ru": "✅ Все процессы остановлены. Вы вернулись в главное меню.\n\nОтправьте новую команду или используйте кнопки.",
        "en": "✅ All processes cancelled. Returned to main menu.\n\nSend a new command or use the buttons.",
    }
    await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)


@dp.message(Command("summary"))
async def cmd_summary(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    await message.answer(food_tracker.summary(uid, lang), reply_markup=MAIN_KBD)


@dp.message(Command("limit"))
async def cmd_limit(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    parts = message.text.split()
    msgs = {
        "uz": {"set": "✅ Kundalik norma {} kcal qilib belgilandi!", "usage": "Ishlatish: /limit <kaloriya>\nMisol: /limit 2200"},
        "ru": {"set": "✅ Дневная норма установлена: {} ккал!", "usage": "Использование: /limit <ккал>\nПример: /limit 2200"},
        "en": {"set": "✅ Daily limit set to {} kcal!", "usage": "Usage: /limit <kcal>\nExample: /limit 2200"},
    }
    lbl = msgs.get(lang, msgs["uz"])
    if len(parts) == 2 and parts[1].isdigit():
        val = int(parts[1])
        food_tracker.set_limit(uid, val)
        await message.answer(lbl["set"].format(val), reply_markup=MAIN_KBD)
    else:
        await message.answer(lbl["usage"], reply_markup=MAIN_KBD)


@dp.message(Command("food_calorie"))
async def cmd_food_calorie(message: types.Message, state=None):
    if state:
        await state.clear()
    uid = message.from_user.id
    lang = await db.get_language(uid)
    session_manager.set_mode(uid, "food_tracking")
    session_manager.get(uid).awaiting_food_input = True
    food_tracker.reset_state(uid)
    await message.answer(greeting(lang), reply_markup=MAIN_KBD)


# ── Photo Handler ──────────────────────────────────

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    user_prompt = message.caption or "What's in this image? Describe it in detail."

    memory.ensure_system(user_id)

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        try:
            image_bytes = await download_image(bot, message.photo[-1].file_id)
            data_uri = image_to_data_uri(image_bytes)
            history = memory.get(user_id)
            reply = query_vision(history, data_uri, user_prompt, HF_API_KEY)
        except requests.exceptions.HTTPError as e:
            logger.error("Vision API HTTP %d | Full response: %s", e.response.status_code, e.response.text)
            if e.response.status_code == 401:
                await message.answer("Invalid HuggingFace API key.")
            elif e.response.status_code == 429:
                await message.answer("Rate limited. Please wait and try again.")
            else:
                await message.answer(f"Vision API error (HTTP {e.response.status_code}).")
            return
        except aiohttp.ClientError as e:
            logger.error("Image download failed: %s", e)
            await message.answer("Failed to download the image. Please try again.")
            return
        except RuntimeError as e:
            logger.error("Vision models all failed: %s", e)
            await message.answer("Image analysis is currently unavailable. All vision models failed.")
            return
        except Exception as e:
            logger.exception("Vision handler error: %s", e)
            await message.answer("An unexpected error occurred while analyzing the image.")
            return

    memory.add(user_id, {"role": "user", "content": f"[User sent an image] {user_prompt}"})
    memory.add(user_id, {"role": "assistant", "content": reply})
    memory.trim(user_id)

    for part in split_message(reply):
        await message.answer(part)


# ── Food Nutrition ─────────────────────────────────

def query_with_fallback(user_id: int) -> str | None:
    models = [MAIN_MODEL, FALLBACK_MODEL]
    messages = memory.get(user_id)
    for model in models:
        try:
            reply = query_hf(messages, model, HF_API_KEY)
            if reply:
                return reply
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            logger.warning("Model %s HTTP %s: %s", model, status, e.response.text[:200])
            if status == 401:
                raise
        except requests.exceptions.Timeout:
            logger.warning("Model %s timed out", model)
        except requests.exceptions.ConnectionError as e:
            logger.warning("Model %s connection error: %s", model, e)
        except Exception as e:
            logger.exception("Model %s error: %s", model, e)
    return None





# ── Discipline Engine ────────────────────────────────
discipline_engine = DisciplineEngine(db)

# ── Manual Task Activation ────────────────────────────────
task_tracker = ManualTaskTracker(db, bot, discipline_engine)

# ── Goal System Registration (must be BEFORE catch-all) ──
goal_handlers = GoalHandlers(dp, db, bot, HF_API_KEY, food_tracker, MAIN_SYSTEM_PROMPT, session_manager, discipline_engine=discipline_engine)
logger.info("Goal handlers registered at module level")

# ── Discipline Reminder Engine ────────────────────────
reminder_engine = ReminderEngine(db, bot, discipline_engine)
reminder_engine.set_task_tracker(task_tracker)

# ── Discipline Callback Handlers ──────────────────────

@dp.callback_query(F.data.startswith("disc_complete:"))
async def on_disc_complete(callback: types.CallbackQuery):
    uid = callback.from_user.id
    rid = int(callback.data.split(":")[1])
    text = await reminder_engine.handle_complete(uid, rid)
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("disc_delay:"))
async def on_disc_delay(callback: types.CallbackQuery):
    uid = callback.from_user.id
    rid = int(callback.data.split(":")[1])
    text, kb = await reminder_engine.handle_delay_request(uid, rid)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("disc_delay_set:"))
async def on_disc_delay_set(callback: types.CallbackQuery):
    uid = callback.from_user.id
    parts = callback.data.split(":")
    rid = int(parts[1])
    minutes = int(parts[2])
    text, kb = await reminder_engine.handle_delay_set(uid, rid, minutes)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("disc_full:"))
async def on_disc_full(callback: types.CallbackQuery):
    uid = callback.from_user.id
    rid = int(callback.data.split(":")[1])
    text = await reminder_engine.handle_complete(uid, rid)
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("disc_partial:"))
async def on_disc_partial(callback: types.CallbackQuery):
    uid = callback.from_user.id
    rid = int(callback.data.split(":")[1])
    text = await reminder_engine.handle_partial(uid, rid)
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("disc_skip:"))
async def on_disc_skip(callback: types.CallbackQuery):
    uid = callback.from_user.id
    rid = int(callback.data.split(":")[1])
    text = await reminder_engine.handle_skip(uid, rid)
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data == "disc_report")
async def on_disc_report(callback: types.CallbackQuery):
    uid = callback.from_user.id
    text = await reminder_engine.handle_report(uid)
    await callback.message.edit_text(text)
    await callback.answer()

# ── /report and /routine commands ─────────────────────

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    text = await build_daily_report(db, uid, lang)
    await message.answer(text, reply_markup=quick_complete_kb(0))

@dp.message(Command("routine"))
async def cmd_routine(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    routines = await db.get_routines(uid)
    labels = {
        "uz": "📋 *Kunlik Tartibingiz*",
        "ru": "📋 *Ваш Ежедневный Распорядок*",
        "en": "📋 *Your Daily Routine*",
    }
    lines = [labels.get(lang, labels["en"]), ""]
    if not routines:
        none_lbl = {
            "uz": "Hali tartib yaratilmagan. /goal orqali maqsadlaringizni belgilang!",
            "ru": "Распорядок еще не создан. Установите цели через /goal!",
            "en": "No routine yet. Set your goals with /goal!",
        }
        await message.answer(none_lbl.get(lang, none_lbl["en"]))
        return
    for r in routines:
        emoji = "🟢" if r["active"] else "🔴"
        lines.append(f"{emoji} {r['scheduled_time']} — *{r['title']}* ({r['duration_minutes']} min)")
    await message.answer("\n".join(lines))

@dp.message(Command("weekly"))
async def cmd_weekly(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    text = await build_weekly_report(db, uid, lang)
    await message.answer(text)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    disc = await db.get_discipline(uid)
    labels = {
        "uz": [
            "📈 *Statistikangiz*",
            f"⭐ Daraja: {disc['level']}",
            f"🔥 XP: {disc['xp']}",
            f"📈 Streak: {disc['streak']} kun",
            f"🏆 Eng uzoq streak: {disc['longest_streak']} kun",
            f"🎯 Intizom ball: {disc['discipline_score']}/100",
            f"✅ Bajarilgan: {disc['total_completed']}",
            f"⏰ Kechiktirilgan: {disc['total_delayed']}",
            f"❌ O'tkazib yuborilgan: {disc['total_skipped']}",
        ],
        "ru": [
            "📈 *Ваша Статистика*",
            f"⭐ Уровень: {disc['level']}",
            f"🔥 XP: {disc['xp']}",
            f"📈 Серия: {disc['streak']} дн.",
            f"🏆 Рекорд: {disc['longest_streak']} дн.",
            f"🎯 Балл дисциплины: {disc['discipline_score']}/100",
            f"✅ Выполнено: {disc['total_completed']}",
            f"⏰ Отложено: {disc['total_delayed']}",
            f"❌ Пропущено: {disc['total_skipped']}",
        ],
        "en": [
            "📈 *Your Stats*",
            f"⭐ Level: {disc['level']}",
            f"🔥 XP: {disc['xp']}",
            f"📈 Streak: {disc['streak']} days",
            f"🏆 Longest streak: {disc['longest_streak']} days",
            f"🎯 Discipline score: {disc['discipline_score']}/100",
            f"✅ Completed: {disc['total_completed']}",
            f"⏰ Delayed: {disc['total_delayed']}",
            f"❌ Skipped: {disc['total_skipped']}",
        ],
    }
    await message.answer("\n".join(labels.get(lang, labels["en"])))

# ── Today Dashboard Command ────────────────────────────

@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    text, kb = await task_tracker.get_today_dashboard(uid, lang)
    await message.answer(text, reply_markup=kb)

# ── Manual Task Activation Callbacks ───────────────────

@dp.callback_query(F.data.startswith("task_start:"))
async def on_task_start(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    text, kb = await task_tracker.start_task(uid, rid, lang)
    if kb:
        await callback.message.edit_text(text, reply_markup=kb)
    else:
        await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("task_finish:"))
async def on_task_finish(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    text = await task_tracker.finish_task(uid, rid, lang)
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("task_pause:"))
async def on_task_pause(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    text, kb = await task_tracker.pause_task(uid, rid, lang)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("task_resume:"))
async def on_task_resume(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    text, kb = await task_tracker.resume_task(uid, rid, lang)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("task_cancel:"))
async def on_task_cancel(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    text = await task_tracker.cancel_task(uid, rid, "", lang)
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("task_details:"))
async def on_task_details(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    routine = await db.get_routine(rid)
    goals = await db.get_goals(uid)
    goal_name = ""
    for g in goals:
        if g["id"] == routine.get("goal_id", 0):
            goal_name = g["name"]
            break
    labels = {
        "uz": {
            "title": f"📊 *{routine['title']}*",
            "time": f"⏰ Vaqt: {routine['scheduled_time']}",
            "duration": f"⏳ Davomiylik: {routine['duration_minutes']} daqiqa",
            "difficulty": f"🎯 Qiyinchilik: {routine['difficulty']}",
            "goal": f"🎯 Maqsad: {goal_name}" if goal_name else "",
            "desc": f"📝 {routine['description']}" if routine.get("description") else "",
        },
        "ru": {
            "title": f"📊 *{routine['title']}*",
            "time": f"⏰ Время: {routine['scheduled_time']}",
            "duration": f"⏳ Длительность: {routine['duration_minutes']} мин",
            "difficulty": f"🎯 Сложность: {routine['difficulty']}",
            "goal": f"🎯 Цель: {goal_name}" if goal_name else "",
            "desc": f"📝 {routine['description']}" if routine.get("description") else "",
        },
        "en": {
            "title": f"📊 *{routine['title']}*",
            "time": f"⏰ Time: {routine['scheduled_time']}",
            "duration": f"⏳ Duration: {routine['duration_minutes']} min",
            "difficulty": f"🎯 Difficulty: {routine['difficulty']}",
            "goal": f"🎯 Goal: {goal_name}" if goal_name else "",
            "desc": f"📝 {routine['description']}" if routine.get("description") else "",
        },
    }
    lbl = labels.get(lang, labels["en"])
    lines = [lbl["title"], "", lbl["time"], lbl["duration"], lbl["difficulty"]]
    if lbl.get("goal"):
        lines.append(lbl["goal"])
    if lbl.get("desc"):
        lines.append(lbl["desc"])
    from goal_system.discipline_keyboards import task_action_kb
    await callback.message.edit_text("\n".join(lines), reply_markup=task_action_kb(rid))
    await callback.answer()

@dp.callback_query(F.data.startswith("task_reschedule:"))
async def on_task_reschedule(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    labels = {
        "uz": "Qancha vaqtga kechiktirmoqchisiz?",
        "ru": "На сколько отложить?",
        "en": "How long would you like to delay?",
    }
    from goal_system.discipline_keyboards import delay_options_kb
    await callback.message.edit_text(labels.get(lang, labels["en"]), reply_markup=delay_options_kb(rid))
    await callback.answer()

@dp.callback_query(F.data.startswith("task_focus:"))
async def on_task_focus(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    labels = {
        "uz": "🎯 Fokus rejimi\n\nQancha vaqt?",
        "ru": "🎯 Режим фокуса\n\nСколько времени?",
        "en": "🎯 Focus Mode\n\nSelect duration:",
    }
    from goal_system.discipline_keyboards import focus_options_kb
    await callback.message.edit_text(labels.get(lang, labels["en"]), reply_markup=focus_options_kb(rid))
    await callback.answer()

@dp.callback_query(F.data.startswith("task_focus_start:"))
async def on_task_focus_start(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    parts = callback.data.split(":")
    rid = int(parts[1])
    minutes = int(parts[2])
    text = await task_tracker.start_focus_mode(uid, rid, minutes, lang)
    from goal_system.discipline_keyboards import active_task_kb
    await callback.message.edit_text(text, reply_markup=active_task_kb(rid))
    await callback.answer()

@dp.callback_query(F.data == "task_keep_current")
async def on_task_keep_current(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    active = await db.get_active_session(uid)
    labels = {
        "uz": "✅ Joriy vazifa davom etmoqda.",
        "ru": "✅ Текущая задача продолжается.",
        "en": "✅ Current task continues.",
    }
    if active:
        from goal_system.discipline_keyboards import active_task_kb
        await callback.message.edit_text(labels.get(lang, labels["en"]), reply_markup=active_task_kb(active["routine_id"]))
    else:
        await callback.message.edit_text(labels.get(lang, labels["en"]))
    await callback.answer()

@dp.callback_query(F.data.startswith("task_switch_confirm:"))
async def on_task_switch_confirm(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    parts = callback.data.split(":")
    new_rid = int(parts[1])
    active = await db.get_active_session(uid)
    old_rid = active["routine_id"] if active else new_rid
    text, kb = await task_tracker.switch_task(uid, old_rid, new_rid, lang)
    if kb:
        await callback.message.edit_text(text, reply_markup=kb)
    else:
        await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("task_mid_yes:"))
async def on_task_mid_yes(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    labels = {
        "uz": "✅ Ajoyib! Davom eting!",
        "ru": "✅ Отлично! Продолжайте!",
        "en": "✅ Great! Keep going!",
    }
    await callback.message.edit_text(labels.get(lang, labels["en"]))
    await callback.answer()

@dp.callback_query(F.data.startswith("task_mid_no:"))
async def on_task_mid_no(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    text = await task_tracker.cancel_task(uid, rid, "", lang)
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("task_active_menu:"))
async def on_task_active_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    routine = await db.get_routine(rid)
    title = routine["title"] if routine else "Task"
    labels = {
        "uz": f"🔥 *{title}* — Aktiv vazifa",
        "ru": f"🔥 *{title}* — Активная задача",
        "en": f"🔥 *{title}* — Active Task",
    }
    from goal_system.discipline_keyboards import active_task_kb
    await callback.message.edit_text(labels.get(lang, labels["en"]), reply_markup=active_task_kb(rid))
    await callback.answer()

@dp.callback_query(F.data == "task_dashboard")
async def on_task_dashboard(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    text, kb = await task_tracker.get_today_dashboard(uid, lang)
    await safe_edit_text(callback.message, text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("task_back:"))
async def on_task_back(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    rid = int(callback.data.split(":")[1])
    from goal_system.discipline_keyboards import task_action_kb
    routine = await db.get_routine(rid)
    labels = {
        "uz": f"📋 *{routine['title']}*",
        "ru": f"📋 *{routine['title']}*",
        "en": f"📋 *{routine['title']}*",
    }
    await callback.message.edit_text(labels.get(lang, labels["en"]), reply_markup=task_action_kb(rid))
    await callback.answer()

@dp.callback_query(F.data == "task_focus_done")
async def on_task_focus_done(callback: types.CallbackQuery):
    await callback.answer("✅ Focus session acknowledged.")
    await callback.message.delete()

# ── Goal Completion Handler ─────────────────────────

async def handle_goal_completion(uid: int, text: str, message: types.Message, lang: str):
    goals = await db.get_goals(uid)
    if not goals:
        msgs = {
            "uz": "Avval /goal orqali maqsadlaringizni belgilang.",
            "ru": "Сначала установите цели через /goal.",
            "en": "First set your goals with /goal.",
        }
        await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)
        return

    t_lower = text.lower()
    matched_goal = None
    goals_sorted = sorted(goals, key=lambda g: len(g["name"]), reverse=True)
    for g in goals_sorted:
        if g["name"].lower() in t_lower:
            matched_goal = g
            break

    if not matched_goal:
        goal_list = "\n".join(f"• {g['name']}" for g in goals)
        msgs = {
            "uz": f"Qaysi maqsad bajarildi?\n\nMaqsadlaringiz:\n{goal_list}\n\nMasalan: \"english bajarildi\"",
            "ru": f"Какая цель выполнена?\n\nВаши цели:\n{goal_list}\n\nНапример: \"английский выполнено\"",
            "en": f"Which goal was completed?\n\nYour goals:\n{goal_list}\n\nExample: \"english done\"",
        }
        await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)
        return

    pt = ProgressTracker(db)
    await pt.check_in(uid, matched_goal["id"])

    msgs = {
        "uz": f"✅ *{matched_goal['name']}* bajarildi deb belgilandi!",
        "ru": f"✅ *{matched_goal['name']}* отмечено как выполненное!",
        "en": f"✅ *{matched_goal['name']}* marked as done!",
    }
    await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)


async def general_chat_handler(message: types.Message, uid: int, txt: str, lang: str = "uz"):
    memory.ensure_system(uid, lang)
    memory.add(uid, {"role": "user", "content": txt})
    memory.trim(uid)

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        try:
            reply = query_with_fallback(uid)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                await message.answer("Invalid HuggingFace API key. Check your HF_API_KEY in .env file.")
            elif e.response.status_code == 403:
                await message.answer("Access denied. Your HF API key may not have access to this model.")
            elif e.response.status_code == 429:
                await message.answer("Rate limited. Please wait a moment and try again.")
            else:
                await message.answer(f"API error (HTTP {e.response.status_code}). Please try again.")
            return
        except Exception as e:
            logger.exception("Unhandled error: %s", e)
            await message.answer("An unexpected error occurred. Please try again.")
            return

    if reply is None:
        await message.answer("AI model is currently unavailable. Both models failed. Please try again later.")
        return

    memory.add(uid, {"role": "assistant", "content": reply})
    memory.trim(uid)

    parts = split_message(reply)
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            await message.answer(part, reply_markup=MAIN_KBD)
        else:
            await message.answer(part)


# ── Finance Engine ────────────────────────────────────

finance_engine = FinanceEngine(db)
reminder_engine.finance_engine = finance_engine
finance_v2_store = FinanceStore()
finance_v2_engine = FinanceBotEngine(finance_v2_store)
personality_profile_store = ProfileStore()
personality_game_store = GamificationStore()
personality_engine = PersonalityEngine(personality_profile_store, personality_game_store)
personality_engine.set_balance_provider(
    lambda uid: finance_v2_store.get(uid).balance
)
nutrition_engine = NutritionEngine()
ai_nutrition_engine = AINutritionEngine(HF_API_KEY)

# ── Life Modules (Reminder / Check-in / Student) ──────────
life_db = LifeDB()
life_scheduler = SchedulerCoordinator()
life_reminder_engine = LifeReminderEngine(life_db, life_scheduler, bot)
checkin_engine = CheckinEngine(life_db, life_scheduler, bot)
student_engine = StudentEngine(life_db, life_scheduler, bot)

from services.nlp_parser import init_parser as init_nlp_parser
init_nlp_parser(HF_API_KEY)

# ── Pending Transaction Storage ────────────────────────

import threading
_pending_lock = threading.Lock()

pending_transactions: dict[int, dict] = {}
PENDING_TTL_SECONDS = 300


def set_pending(uid: int, data: dict):
    with _pending_lock:
        data["timestamp"] = datetime.now()
        pending_transactions[uid] = data
        logger.info("Pending TX stored for user %s: %.0f %s", uid, data.get("amount", 0), data.get("tx_type", "?"))


def get_pending(uid: int) -> dict | None:
    with _pending_lock:
        entry = pending_transactions.get(uid)
        if entry is None:
            return None
        elapsed = (datetime.now() - entry["timestamp"]).total_seconds()
        if elapsed > PENDING_TTL_SECONDS:
            del pending_transactions[uid]
            logger.info("Pending TX expired for user %s", uid)
            return None
        return entry


def pop_pending(uid: int) -> dict | None:
    with _pending_lock:
        entry = pending_transactions.pop(uid, None)
        if entry:
            logger.info("Pending TX popped for user %s", uid)
        return entry


def clear_pending(uid: int):
    with _pending_lock:
        pending_transactions.pop(uid, None)
        logger.info("Pending TX cleared for user %s", uid)


# ── Finance Inline Keyboards ──────────────────────────

def _finance_kbd(lang: str) -> InlineKeyboardMarkup:
    btn_confirm_text = {"uz": "✅ Tasdiqlash", "ru": "✅ Подтвердить", "en": "✅ Confirm"}
    btn_cancel_text = {"uz": "❌ Bekor qilish", "ru": "❌ Отмена", "en": "❌ Cancel"}
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn_confirm_text.get(lang, "✅ Tasdiqlash"), callback_data="confirm_tx"),
            InlineKeyboardButton(text=btn_cancel_text.get(lang, "❌ Bekor qilish"), callback_data="cancel_tx"),
        ],
    ])


async def handle_finance_transaction(uid: int, result, message: types.Message, lang: str):
    await db.ensure_user(uid)
    dup = await db.check_duplicate_transaction(uid, result.amount, result.category)
    if dup:
        msgs = {
            "uz": "⚠️ Bu tranzaksiya allaqachon qayd etilgan (takrorlanish aniqlandi).",
            "ru": "⚠️ Эта транзакция уже записана (обнаружен дубликат).",
            "en": "⚠️ This transaction was already recorded (duplicate detected).",
        }
        await message.answer(msgs.get(lang, msgs["uz"]), reply_markup=MAIN_KBD)
        return

    set_pending(uid, {
        "amount": result.amount,
        "tx_type": result.tx_type,
        "category": result.category,
        "description": result.description,
        "raw_text": getattr(result, "raw_text", result.description),
    })

    confirm_text = await finance_engine.format_confirmation(result, lang)
    msgs = {
        "uz": f"💳 *Moliyaviy tranzaksiya aniqlandi!*\n\n{confirm_text}\n\nTasdiqlaysizmi?",
        "ru": f"💳 *Обнаружена финансовая транзакция!*\n\n{confirm_text}\n\nПодтверждаете?",
        "en": f"💳 *Financial transaction detected!*\n\n{confirm_text}\n\nConfirm?",
    }
    await message.answer(
        msgs.get(lang, msgs["uz"]),
        reply_markup=_finance_kbd(lang),
    )


# ── /money Command ────────────────────────────────────

@dp.message(Command("money"))
async def cmd_money(message: types.Message):
    uid = str(message.from_user.id)
    uidi = message.from_user.id
    lang = await db.get_language(uidi)
    finance_v2_store.reset_state(uid)
    text = finance_v2_engine.build_dashboard(uid, lang)
    game_block = personality_engine.gamification_block(uid, lang)
    text += f"\n\n{game_block}"
    await message.answer(text, reply_markup=finance_v2_engine.get_kb())
    personality_engine.track_interaction(uid)


@dp.message(Command("money_analytics"))
async def cmd_money_analytics(message: types.Message):
    await cmd_money(message)


@dp.message(Command("money_history"))
async def cmd_money_history(message: types.Message):
    await cmd_money(message)


# ── Finance Callback Handlers ─────────────────────────


@dp.callback_query(F.data == "confirm_tx")
async def on_confirm_tx(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    logger.info("confirm_tx callback from user %s", uid)

    pf = get_pending(uid)
    if pf is None:
        logger.warning("No pending TX for user %s on confirm", uid)
        await callback.answer("❌ Kutilayotgan tranzaksiya topilmadi. Yangi tranzaksiya kiriting.")
        await callback.message.edit_text(
            "❌ Tranzaksiya topilmadi. /money orqali yangi tranzaksiya kiriting."
        )
        return

    try:
        result = FinanceParserResult(
            amount=pf["amount"],
            tx_type=pf["tx_type"],
            category=pf["category"],
            description=pf["description"],
            confidence=1.0,
        )
        raw_text = pf.get("raw_text", pf.get("description", ""))
        tx_id = await finance_engine.confirm_and_save(uid, result, raw_text=raw_text)
        pop_pending(uid)

        await callback.answer("✅ Saqlandi!")
        sign = "➕" if pf["tx_type"] == "income" else "➖"
        type_str = {"income": "Kirim", "expense": "Chiqim"}.get(pf["tx_type"], "?")
        cat_label = get_category_label(pf["category"], lang)
        msgs = {
            "uz": f"✅ *Tranzaksiya saqlandi!* (ID: {tx_id})\n{sign} {type_str}: {pf['amount']:,.0f} so'm\n📂 {cat_label}",
            "ru": f"✅ *Транзакция сохранена!* (ID: {tx_id})\n{sign} {type_str}: {pf['amount']:,.0f} сум\n📂 {cat_label}",
            "en": f"✅ *Transaction saved!* (ID: {tx_id})\n{sign} {type_str}: {pf['amount']:,.0f} UZS\n📂 {cat_label}",
        }
        await callback.message.edit_text(msgs.get(lang, msgs["uz"]))
        await callback.message.answer(
            await finance_engine.get_today_summary(uid, lang),
            reply_markup=MAIN_KBD,
        )
        logger.info("TX saved for user %s: ID=%s amount=%.0f type=%s", uid, tx_id, pf["amount"], pf["tx_type"])
    except Exception as e:
        logger.exception("Failed to save transaction for user %s: %s", uid, e)
        await callback.answer("❌ Xatolik yuz berdi.")
        await callback.message.edit_text(
            "❌ Tranzaksiyani saqlashda xatolik. Iltimos qaytadan urinib ko'ring."
        )


@dp.callback_query(F.data == "cancel_tx")
async def on_cancel_tx(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    logger.info("cancel_tx callback from user %s", uid)

    pf = get_pending(uid)
    if pf is None:
        await callback.answer("✅ Hech qanday kutilayotgan tranzaksiya yo'q.")
        return

    clear_pending(uid)
    await callback.answer("❌ Bekor qilindi.")
    msgs = {
        "uz": "❌ Tranzaksiya bekor qilindi.",
        "ru": "❌ Транзакция отменена.",
        "en": "❌ Transaction cancelled.",
    }
    await callback.message.edit_text(msgs.get(lang, msgs["uz"]))



@dp.callback_query(F.data == "fin:income")
async def on_fin_income(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    uid_int = callback.from_user.id
    lang = await db.get_language(uid_int)
    finance_v2_store.set_state(uid, "awaiting_income")
    await callback.message.edit_text(fin_income_prompt(lang))
    await callback.answer()


@dp.callback_query(F.data == "fin:expense")
async def on_fin_expense(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    uid_int = callback.from_user.id
    lang = await db.get_language(uid_int)
    finance_v2_store.set_state(uid, "awaiting_expense")
    await callback.message.edit_text(fin_expense_prompt(lang))
    await callback.answer()


@dp.callback_query(F.data == "fin:calc")
async def on_fin_calc(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    lang = await db.get_language(callback.from_user.id)
    text = finance_v2_engine.build_analytics(uid, lang)
    await callback.message.edit_text(text, reply_markup=finance_v2_engine.get_kb())
    await callback.answer()


@dp.callback_query(F.data.startswith("fin:yana:"))
async def on_fin_yana(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    lang = await db.get_language(callback.from_user.id)
    action = callback.data.split(":")[2]
    if action == "income":
        finance_v2_store.set_state(uid, "awaiting_income")
        await callback.message.edit_text(fin_income_prompt(lang))
    elif action == "expense":
        finance_v2_store.set_state(uid, "awaiting_expense")
        await callback.message.edit_text(fin_expense_prompt(lang))
    await callback.answer()


@dp.callback_query(F.data.startswith("fin:boldi:"))
async def on_fin_boldi(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    lang = await db.get_language(callback.from_user.id)
    finance_v2_store.reset_state(uid)
    summary = finance_v2_engine.build_daily_summary(uid, lang)
    await callback.message.edit_text(summary, reply_markup=finance_v2_engine.get_kb())
    await callback.answer()


# ── Life Modules: Checkin Callbacks ────────────────────

from modules.checkin.engine import MOOD_EMOJI, MOOD_LABELS
from modules.reminder.engine import REMINDER_TYPES, REMINDER_LABELS

def _checkin_mood_kb(lang: str) -> InlineKeyboardMarkup:
    L = lang if lang in ("uz", "ru", "en") else "uz"
    labels = MOOD_LABELS[L]
    btns = [
        [
            InlineKeyboardButton(text=f"{MOOD_EMOJI['good']} {labels['good']}", callback_data="life_mood:good"),
            InlineKeyboardButton(text=f"{MOOD_EMOJI['mid']} {labels['mid']}", callback_data="life_mood:mid"),
            InlineKeyboardButton(text=f"{MOOD_EMOJI['bad']} {labels['bad']}", callback_data="life_mood:bad"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=btns)


@dp.callback_query(F.data.startswith("life_mood:"))
async def on_life_mood(callback: types.CallbackQuery):
    uid = callback.from_user.id
    mood = callback.data.split(":", 1)[1]
    lang = await db.get_language(uid)
    result = await checkin_engine.process_checkin(uid, mood, lang)
    await callback.message.edit_text(result["message"])
    await callback.answer()


@dp.callback_query(F.data.startswith("life_rem_del:"))
async def on_life_rem_del(callback: types.CallbackQuery):
    uid = callback.from_user.id
    rid = int(callback.data.split(":", 1)[1])
    await life_reminder_engine.delete_reminder(rid)
    lang = await db.get_language(uid)
    text = await life_reminder_engine.get_reminder_list_text(uid, lang)
    await callback.message.edit_text(text)
    await callback.answer()


@dp.callback_query(F.data.startswith("life_rem_toggle:"))
async def on_life_rem_toggle(callback: types.CallbackQuery):
    uid = callback.from_user.id
    rid = int(callback.data.split(":", 1)[1])
    reminders = await life_reminder_engine.get_user_reminders(uid)
    for r in reminders:
        if r["id"] == rid:
            new_active = 0 if r["active"] else 1
            await life_reminder_engine.toggle_reminder(rid, new_active)
            break
    lang = await db.get_language(uid)
    text = await life_reminder_engine.get_reminder_list_text(uid, lang)
    await callback.message.edit_text(text)
    await callback.answer()


@dp.callback_query(F.data.startswith("life_hw_done:"))
async def on_life_hw_done(callback: types.CallbackQuery):
    uid = callback.from_user.id
    hw_id = int(callback.data.split(":", 1)[1])
    await student_engine.complete_homework(hw_id)
    lang = await db.get_language(uid)
    text = await student_engine.get_homework_text(uid, lang)
    await callback.message.edit_text(text)
    await callback.answer()


@dp.callback_query(F.data.startswith("life_hw_del:"))
async def on_life_hw_del(callback: types.CallbackQuery):
    uid = callback.from_user.id
    hw_id = int(callback.data.split(":", 1)[1])
    await student_engine.delete_homework(hw_id)
    lang = await db.get_language(uid)
    text = await student_engine.get_homework_text(uid, lang)
    await callback.message.edit_text(text)
    await callback.answer()


# ── Life Modules: Commands ─────────────────────────────


@dp.message(Command("reminder"))
async def cmd_reminder(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    text = message.text.strip()
    parts = text.split(maxsplit=2)

    if len(parts) >= 3 and parts[1] == "add":
        rtype = parts[2].split()[0] if " " in parts[2] else parts[2]
        time_part = parts[2].split()[1] if len(parts[2].split()) > 1 else ""
        if rtype in REMINDER_TYPES and time_part:
            rid = await life_reminder_engine.create_reminder(uid, rtype, time_part)
            msgs = {
                "uz": f"✅ Reminder qo'shildi (ID: {rid})",
                "ru": f"✅ Напоминание добавлено (ID: {rid})",
                "en": f"✅ Reminder added (ID: {rid})",
            }
            await message.answer(msgs.get(lang, msgs["en"]))
            return
        else:
            usage = {
                "uz": "Ishlatish: /reminder add <type> <HH:MM>\nTurlar: water, gym, study, work, sleep, supplement, custom",
                "ru": "Использование: /reminder add <тип> <ЧЧ:ММ>\nТипы: water, gym, study, work, sleep, supplement, custom",
                "en": "Usage: /reminder add <type> <HH:MM>\nTypes: water, gym, study, work, sleep, supplement, custom",
            }
            await message.answer(usage.get(lang, usage["en"]))
            return

    if len(parts) >= 3 and parts[1] == "del":
        try:
            rid = int(parts[2])
            await life_reminder_engine.delete_reminder(rid)
            msgs = {"uz": "✅ O'chirildi", "ru": "✅ Удалено", "en": "✅ Deleted"}
            await message.answer(msgs.get(lang, msgs["en"]))
        except ValueError:
            pass
        return

    if len(parts) >= 3 and parts[1] == "toggle":
        try:
            rid = int(parts[2])
            reminders = await life_reminder_engine.get_user_reminders(uid)
            for r in reminders:
                if r["id"] == rid:
                    new_active = 0 if r["active"] else 1
                    await life_reminder_engine.toggle_reminder(rid, new_active)
                    break
            msgs = {"uz": "✅ O'zgartirildi", "ru": "✅ Изменено", "en": "✅ Toggled"}
            await message.answer(msgs.get(lang, msgs["en"]))
        except ValueError:
            pass
        return

    text = await life_reminder_engine.get_reminder_list_text(uid, lang)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add", callback_data="life_rem_add")],
    ])
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "life_rem_add")
async def on_life_rem_add(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    labels = REMINDER_LABELS.get(lang, REMINDER_LABELS["uz"])
    btns = []
    row = []
    for i, rtype in enumerate(REMINDER_TYPES):
        label = labels.get(rtype, rtype)
        row.append(InlineKeyboardButton(text=label, callback_data=f"life_rem_type:{rtype}"))
        if (i + 1) % 4 == 0:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    msgs = {"uz": "Reminder turini tanlang:", "ru": "Выберите тип напоминания:", "en": "Select reminder type:"}
    await callback.message.edit_text(msgs.get(lang, msgs["en"]), reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    await callback.answer()


@dp.callback_query(F.data.startswith("life_rem_type:"))
async def on_life_rem_type(callback: types.CallbackQuery):
    uid = callback.from_user.id
    rtype = callback.data.split(":", 1)[1]
    lang = await db.get_language(uid)
    msgs = {
        "uz": f"Vaqtni kiriting (HH:MM):\nMisol: 14:30",
        "ru": f"Введите время (ЧЧ:ММ):\nПример: 14:30",
        "en": f"Enter time (HH:MM):\nExample: 14:30",
    }
    await callback.message.edit_text(msgs.get(lang, msgs["en"]))
    session_manager.set_mode(uid, "awaiting_reminder_time")
    session_manager.get(uid).pending_reminder_type = rtype
    await callback.answer()


@dp.message(Command("checkin"))
async def cmd_checkin(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    status = await checkin_engine.get_checkin_status(uid, lang)
    if status["done_today"]:
        await message.answer(status["message"])
    else:
        await message.answer(status["message"], reply_markup=_checkin_mood_kb(lang))


@dp.message(Command("study"))
async def cmd_study(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    parts = message.text.split()
    if len(parts) == 2:
        try:
            hours = float(parts[1])
            result = await student_engine.log_study(uid, hours, lang)
            await message.answer(result["message"])
        except ValueError:
            usage = {"uz": "Ishlatish: /study <soat>\nMisol: /study 2.5", "ru": "Использование: /study <часы>\nПример: /study 2.5", "en": "Usage: /study <hours>\nExample: /study 2.5"}
            await message.answer(usage.get(lang, usage["en"]))
    else:
        stats = await student_engine.get_study_stats_text(uid, lang)
        await message.answer(stats)


@dp.message(Command("exam"))
async def cmd_exam(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    parts = message.text.split(maxsplit=3)
    if len(parts) >= 4 and parts[1] == "add":
        subject = parts[2]
        exam_date = parts[3]
        await student_engine.add_exam(uid, subject, exam_date)
        msgs = {"uz": f"✅ Imtihon qo'shildi: {subject} — {exam_date}", "ru": f"✅ Экзамен добавлен: {subject} — {exam_date}", "en": f"✅ Exam added: {subject} — {exam_date}"}
        await message.answer(msgs.get(lang, msgs["en"]))
        return
    if len(parts) >= 3 and parts[1] == "del":
        try:
            eid = int(parts[2])
            await student_engine.delete_exam(eid)
            msgs = {"uz": "✅ O'chirildi", "ru": "✅ Удалено", "en": "✅ Deleted"}
            await message.answer(msgs.get(lang, msgs["en"]))
        except ValueError:
            pass
        return
    text = await student_engine.get_exams_text(uid, lang)
    await message.answer(text)


@dp.message(Command("focus"))
async def cmd_focus(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    active = await student_engine.get_active_focus(uid)
    if active:
        msgs = {"uz": "Sizning active fokus sessiyangiz bor. Avval uni tugating.", "ru": "У вас уже есть активная сессия. Сначала завершите её.", "en": "You already have an active focus session. Finish it first."}
        await message.answer(msgs.get(lang, msgs["en"]))
        return
    result = await student_engine.start_focus(uid, lang)
    await message.answer(result["message"])


@dp.message(Command("homework"))
async def cmd_homework(message: types.Message):
    uid = message.from_user.id
    lang = await db.get_language(uid)
    text = message.text.strip()
    parts = text.split(maxsplit=2)

    if len(parts) >= 3 and parts[1] == "add":
        task = parts[2]
        await student_engine.add_homework(uid, task)
        msgs = {"uz": "✅ Topshiriq qo'shildi", "ru": "✅ Задание добавлено", "en": "✅ Homework added"}
        await message.answer(msgs.get(lang, msgs["en"]))
        return

    if len(parts) >= 3 and parts[1] == "done":
        try:
            hw_id = int(parts[2])
            await student_engine.complete_homework(hw_id)
            msgs = {"uz": "✅ Topshiriq bajarildi", "ru": "✅ Задание выполнено", "en": "✅ Homework completed"}
            await message.answer(msgs.get(lang, msgs["en"]))
        except ValueError:
            pass
        return

    if len(parts) >= 3 and parts[1] == "del":
        try:
            hw_id = int(parts[2])
            await student_engine.delete_homework(hw_id)
            msgs = {"uz": "✅ O'chirildi", "ru": "✅ Удалено", "en": "✅ Deleted"}
            await message.answer(msgs.get(lang, msgs["en"]))
        except ValueError:
            pass
        return

    homework = await student_engine.get_homework(uid)
    text = await student_engine.get_homework_text(uid, lang)
    if homework:
        btns = []
        for hw in homework:
            emoji = "\u2705" if hw["completed"] else "\u274c"
            btns.append([
                InlineKeyboardButton(text=f"{emoji} {hw['task'][:20]}", callback_data=f"life_hw_done:{hw['id']}"),
            ])
        btns.append([InlineKeyboardButton(text="\u274c Delete", callback_data="life_hw_del_mode")])
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        await message.answer(text)


@dp.callback_query(F.data == "life_hw_del_mode")
async def on_life_hw_del_mode(callback: types.CallbackQuery):
    uid = callback.from_user.id
    lang = await db.get_language(uid)
    homework = await student_engine.get_homework(uid)
    if not homework:
        await callback.answer()
        return
    btns = []
    for hw in homework:
        btns.append([
            InlineKeyboardButton(text=f"\U0001f5d1 {hw['task'][:20]}", callback_data=f"life_hw_del:{hw['id']}"),
        ])
    msgs = {"uz": "O'chirish uchun topshiriqni tanlang:", "ru": "Выберите задание для удаления:", "en": "Select homework to delete:"}
    await callback.message.edit_text(msgs.get(lang, msgs["en"]), reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    await callback.answer()


# ── Main Message Handler (catch-all) ──────────────────────

@dp.message()
async def handle_message(message: types.Message, state=None):
    if not message.text:
        return

    uid = message.from_user.id
    txt = message.text.strip()
    uid_str = str(uid)
    lang = await db.get_language(uid)
    L = lang if lang in ("uz", "ru", "en") else "uz"

    # ── Finance v2 state machine (highest priority) ──
    fstate = finance_v2_store.get_state(uid_str)
    if fstate == "awaiting_income":
        result = finance_v2_engine.handle_income_input(uid_str, txt, L)
        if result["ok"]:
            personality_engine.track_interaction(uid_str, txt)
            comment = personality_engine.after_income(uid_str, result["amount"], L)
            msg = result["message"]
            if comment:
                msg += f"\n\n{comment}"
            msg += f"\n\n{tr('finance', 'yana_income', L)}"
            await message.answer(msg, reply_markup=finance_v2_engine.get_yana_kb("income"))
        else:
            await message.answer(result["message"])
        return
    if fstate == "awaiting_expense":
        result = finance_v2_engine.handle_expense_input(uid_str, txt, L)
        if result["ok"]:
            personality_engine.track_interaction(uid_str, txt)
            comment = personality_engine.after_expense(uid_str, result["amount"], result.get("description", ""), L)
            msg = result["message"]
            if comment:
                msg += f"\n\n{comment}"
            msg += f"\n\n{tr('finance', 'yana_expense', L)}"
            await message.answer(msg, reply_markup=finance_v2_engine.get_yana_kb("expense"))
        elif result.get("need_amount"):
            personality_engine.track_interaction(uid_str, txt)
            await message.answer(result["message"])
        else:
            await message.answer(result["message"])
        return

    # ── Life Modules: awaiting reminder time ──
    session = session_manager.get(uid)
    if session.active_mode == "awaiting_reminder_time" and hasattr(session, "pending_reminder_type"):
        rtype = session.pending_reminder_type
        pattern = r"^([01]\d|2[0-3]):([0-5]\d)$"
        if re.match(pattern, txt):
            rid = await life_reminder_engine.create_reminder(uid, rtype, txt)
            session_manager.reset(uid)
            food_tracker.reset_state(uid)
            msgs = {"uz": f"✅ Reminder qo'shildi (ID: {rid})", "ru": f"✅ Напоминание добавлено (ID: {rid})", "en": f"✅ Reminder added (ID: {rid})"}
            await message.answer(msgs.get(lang, msgs["uz"]))
        else:
            msgs = {"uz": "Noto'g'ri vaqt formati. Iltimos HH:MM formatida yozing.\nMisol: 14:30", "ru": "Неверный формат времени. Используйте ЧЧ:ММ.\nПример: 14:30", "en": "Invalid time format. Please use HH:MM.\nExample: 14:30"}
            await message.answer(msgs.get(lang, msgs["uz"]))
        return

    # ── Commands handled by dedicated handlers ──
    if txt.startswith("/"):
        return

    # ── Keyboard button text ──
    if txt.lower() in ("food_calorie",):
        session_manager.set_mode(uid, "food_tracking")
        session_manager.get(uid).awaiting_food_input = True
        food_tracker.reset_state(uid)
        await message.answer(greeting(lang), reply_markup=MAIN_KBD)
        return

    # ── Context expiration ──
    if session_manager.is_expired(uid):
        session_manager.reset(uid)
        food_tracker.reset_state(uid)
        msgs = {
            "uz": "⏰ Vaqt o'tdi. Yangi buyruq yuboring.",
            "ru": "⏰ Время истекло. Отправьте новую команду.",
            "en": "⏰ Session expired. Send a new command.",
        }
        await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)
        return

    session = session_manager.get(uid)

    # ── Intent Classification ──
    intent = IntentClassifier.classify(txt, session)

    # ── Route: Active Finance Input (from /money prompt) ──
    if session.awaiting_finance_input and session.active_mode == "finance_input":
        session.awaiting_finance_input = False
        session_manager.reset(uid)
        food_tracker.reset_state(uid)
        from services.nlp_parser import parse_money_text
        data = parse_money_text(txt)
        if data["amount"] > 0:
            tx_id = await finance_engine.save_from_parsed(uid, data)
            sign = "➕" if data["tx_type"] == "income" else "➖"
            type_label = {"income": "Kirim", "expense": "Chiqim"}.get(data["tx_type"], "?")
            from modules.finance.prompts import get_category_label
            cat_label = get_category_label(data["category"], lang)
            saved_msgs = {
                "uz": f"✅ *Tranzaksiya saqlandi!* (ID: {tx_id})\n{sign} {type_label}: {data['amount']:,.0f} so'm\n📂 {cat_label}",
                "ru": f"✅ *Транзакция сохранена!* (ID: {tx_id})\n{sign} {type_label}: {data['amount']:,.0f} сум\n📂 {cat_label}",
                "en": f"✅ *Transaction saved!* (ID: {tx_id})\n{sign} {type_label}: {data['amount']:,.0f} UZS\n📂 {cat_label}",
            }
            await message.answer(saved_msgs.get(lang, saved_msgs["uz"]))
            await message.answer(
                await finance_engine.get_today_summary(uid, lang),
                reply_markup=MAIN_KBD,
            )
        else:
            no_parse_msgs = {
                "uz": "❌ Tranzaksiya aniqlanmadi. Iltimos qaytadan yozing.\nMisol: \"50000 so'm gas uchun\"",
                "ru": "❌ Транзакция не распознана. Попробуйте снова.\nПример: \"50000 сум на газ\"",
                "en": "❌ Transaction not recognized. Please try again.\nExample: \"50000 som for gas\"",
            }
            await message.answer(no_parse_msgs.get(lang, no_parse_msgs["en"]), reply_markup=MAIN_KBD)
        return

    # ── Route: Goal Completion ──
    if intent == Intent.GOAL_COMPLETION:
        session_manager.reset(uid)
        food_tracker.reset_state(uid)
        await handle_goal_completion(uid, txt, message, lang)
        return

    # ── Route: Mission Number (only when in mission mode) ──
    if intent == Intent.MISSION_NUMBER and txt.isdigit() and (session.active_mode == "missions" or session.awaiting_mission_number):
        idx = int(txt)
        result = await goal_handlers.mission_gen.mark_complete(uid, idx, lang)
        session_manager.reset(uid)
        food_tracker.reset_state(uid)
        await message.answer(result, reply_markup=MAIN_KBD)
        return

    # ── Route: Finance (passive detection, before food) ──
    if intent in (Intent.FINANCE_EXPENSE, Intent.FINANCE_INCOME) and session.active_mode != "food_tracking":
        from modules.finance.parser import FinanceParser
        fp_result = FinanceParser.parse(txt)
        if fp_result.is_valid:
            await handle_finance_transaction(uid, fp_result, message, lang)
            return

    # ── Route: Food Tracking (AI-powered) ──
    if session.active_mode == "food_tracking":
        if food_tracker.state(uid) == "awaiting_clarification":
            pending = food_tracker.pending(uid)
            if not pending:
                food_tracker.reset_state(uid)
                session.awaiting_food_clarification = False
            else:
                original = pending.get("original", "")
                combined = f"{original}\nUser added: {txt}"
                async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
                    data = ai_nutrition_engine.analyze(combined)
                if "error" in data:
                    session.awaiting_food_clarification = False
                    food_tracker.reset_state(uid)
                    err_msgs = {
                        "uz": "AI bilan bogʻlanishda xatolik. Qaytadan urinib koʻring.",
                        "ru": "Ошибка соединения с AI. Попробуйте снова.",
                        "en": "AI connection error. Please try again.",
                    }
                    await message.answer(err_msgs.get(lang, err_msgs["en"]), reply_markup=MAIN_KBD)
                    return
                if data.get("clarification_needed"):
                    food_tracker.set_pending(uid, {"original": combined, "question": data.get("question", "?")})
                    q = data.get("question") or data.get("question_en") or "Iltimos aniqlik kiriting:"
                    await message.answer(q, reply_markup=MAIN_KBD)
                    return
                session.awaiting_food_clarification = False
                food_tracker.reset_state(uid)
                total_cal = data.get("total", {}).get("calories", 0)
                food_tracker.add_meal(uid, {"name": original[:100], "calories": total_cal})
                remain = food_tracker.remain(uid)
                result_text = ai_format_result(data, remain, lang)
                await message.answer(result_text, reply_markup=MAIN_KBD)
                return

        if intent == Intent.FOOD_INPUT:
            if not FoodParser.is_likely_food(txt):
                session_manager.reset(uid)
                food_tracker.reset_state(uid)
                msgs = {
                    "uz": "Ovqat aniqlanmadi. Iltimos ovqat nomini yozing.",
                    "ru": "Еда не обнаружена. Пожалуйста, напишите название еды.",
                    "en": "Food not detected. Please enter a food name.",
                }
                await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)
                return

            async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
                data = ai_nutrition_engine.analyze(txt)

            if "error" in data:
                session_manager.reset(uid)
                food_tracker.reset_state(uid)
                err_msgs = {
                    "uz": "AI bilan bogʻlanishda xatolik. Qaytadan urinib koʻring.",
                    "ru": "Ошибка соединения с AI. Попробуйте снова.",
                    "en": "AI connection error. Please try again.",
                }
                await message.answer(err_msgs.get(lang, err_msgs["en"]), reply_markup=MAIN_KBD)
                return

            if data.get("clarification_needed"):
                food_tracker.set_pending(uid, {"original": txt, "question": data.get("question", "?")})
                food_tracker.set_state(uid, "awaiting_clarification")
                session.awaiting_food_clarification = True
                q = data.get("question") or data.get("question_en") or "Iltimos aniqlik kiriting:"
                await message.answer(q, reply_markup=MAIN_KBD)
                return

            total_cal = data.get("total", {}).get("calories", 0)
            food_tracker.add_meal(uid, {"name": txt[:100], "calories": total_cal})
            remain = food_tracker.remain(uid)
            result_text = ai_format_result(data, remain, lang)
            await message.answer(result_text, reply_markup=MAIN_KBD)
            return

        # ── Exit food mode on unrelated text ──
        session_manager.reset(uid)
        food_tracker.reset_state(uid)
        msgs = {
            "uz": "🍽️ Ovqat hisoblash bekor qilindi.",
            "ru": "🍽️ Подсчет калорий отменен.",
            "en": "🍽️ Food tracking cancelled.",
        }
        await message.answer(msgs.get(lang, msgs["en"]), reply_markup=MAIN_KBD)

    session_manager.reset(uid)
    food_tracker.reset_state(uid)

    # ── General AI Chat ──
    await general_chat_handler(message, uid, txt, lang)


# ── Main ───────────────────────────────────────────

async def main():
    logger.info("Starting HuggingFace Telegram bot")
    logger.info("Main model: %s", MAIN_MODEL)

    await db.init()
    logger.info("Database initialized")

    reminder_mgr = ReminderManager(db, bot)
    reminder_mgr.start()
    await reminder_mgr.load_reminders()
    logger.info("Reminders loaded")

    reminder_engine.start()
    reminder_engine.schedule_minute_check()
    reminder_engine.schedule_night_review(21, 0)
    logger.info("Discipline reminder engine started")

    task_tracker.set_scheduler(reminder_engine.scheduler)

    await life_db.init()
    life_scheduler.start()
    await life_reminder_engine.schedule_all_active()
    await checkin_engine.schedule_daily_checkin(20, 0)
    await student_engine.schedule_exam_checks()
    logger.info("Life modules scheduler started")

    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Home"),
        BotCommand(command="goal", description="🎯 Set goals & build AI life system"),

        BotCommand(command="missions", description="🔥 View daily missions"),
        BotCommand(command="profile", description="🧠 View your AI profile"),
        BotCommand(command="done", description="✅ Mark mission complete"),
        BotCommand(command="food_calorie", description="🍽️ Track meal calories"),
        BotCommand(command="progress", description="📊 Weekly report"),
        BotCommand(command="streak", description="🔥 View streaks"),
        BotCommand(command="summary", description="📋 Daily food summary"),
        BotCommand(command="limit", description="Set daily calorie limit"),
        BotCommand(command="money", description="💰 Finance dashboard (analytics + history)"),
        BotCommand(command="report", description="📊 Today's discipline report"),
        BotCommand(command="routine", description="📋 View your daily routine"),
        BotCommand(command="weekly", description="📅 Weekly discipline report"),
        BotCommand(command="stats", description="📈 View your gamification stats"),
        BotCommand(command="today", description="📅 Today's task dashboard"),
        BotCommand(command="reminder", description="⏰ Manage reminders"),
        BotCommand(command="checkin", description="📝 Daily mood check-in"),
        BotCommand(command="study", description="📚 Log study hours"),
        BotCommand(command="exam", description="📋 Manage exams"),
        BotCommand(command="focus", description="🎯 Start Pomodoro focus"),
        BotCommand(command="homework", description="📝 Manage homework"),
        BotCommand(command="language", description="🌐 Change language"),
        BotCommand(command="clear", description="Reset all"),
        BotCommand(command="help", description="Show help"),
        BotCommand(command="cancel", description="⛔ Cancel current flow"),
    ])

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception("Bot polling failed: %s", e)
    finally:
        reminder_mgr.stop()
        reminder_engine.stop()
        life_scheduler.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
  