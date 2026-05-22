import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from aiogram import F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.chat_action import ChatActionSender

from .calorie_calc import CalorieCalculator
from .routine_engine import RoutineEngine
from .ai_content_gen import AITaskContentGenerator
from .schedule_gen import ScheduleGenerator
from .discipline_engine import DisciplineEngine
from .goal_questions import (
    GOAL_QUESTIONS,
    GOAL_BUTTONS_CONFIG,
    GOAL_OPTIONS_ROWS,
    GOAL_DISPLAY_NAMES,
    LABEL_TO_KEY,
    KEY_TO_LABEL,
    get_all_questions,
    get_questions,
    get_category_for_goal,
    FITNESS_GOAL_KEYS,
    LEARNING_GOAL_KEYS,
    MENTAL_PRODUCTIVITY_GOAL_KEYS,
    FUTURE_CAREER_GOAL_KEYS,
    GOAL_CATEGORIES,
)
from .prompts import MAIN_SYSTEM_PROMPT, lang_rule, CUSTOM_GOAL_ANALYSIS_PROMPT, CUSTOM_GOAL_ROUTINE_PROMPT
from .ai_goal_parser import AIGoalParser
from .profile_analyzer import ProfileAnalyzer
from .daily_missions import DailyMissionGenerator

logger = logging.getLogger("goal_handlers")

HF_BASE_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL = "meta-llama/Llama-3.1-8B-Instruct"
FALLBACK_MODEL = "NousResearch/Hermes-2-Pro-Llama-3-8B"
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


class GoalStates(StatesGroup):
    selecting_goals = State()
    goal_qa = State()


CATEGORY_META = {
    "fitness": {"emoji": "🏋️", "label_uz": "FITNESS", "label_ru": "ФИТНЕС", "label_en": "FITNESS"},
    "learning": {"emoji": "📚", "label_uz": "O'RGANISH", "label_ru": "ОБУЧЕНИЕ", "label_en": "LEARNING"},
    "mental_productivity": {"emoji": "🧠", "label_uz": "MENTAL & MAHSULDORLIK", "label_ru": "МЕНТАЛКА & ПРОДУКТИВНОСТЬ", "label_en": "MENTAL & PRODUCTIVITY"},
    "future_career": {"emoji": "💼", "label_uz": "KELAJAK & KARYERA", "label_ru": "БУДУЩЕЕ & КАРЬЕРА", "label_en": "FUTURE & CAREER"},
    "appearance": {"emoji": "🔥", "label_uz": "TASHQI KO'RINISH", "label_ru": "ВНЕШНОСТЬ", "label_en": "LOOKSMAXING"},
}


def make_goal_keyboard(selected: set[str] = None):
    if selected is None:
        selected = set()
    kb = []
    for row in GOAL_OPTIONS_ROWS:
        row_btns = []
        for label in row:
            key = LABEL_TO_KEY.get(label)
            if not key:
                continue
            display = f"✅ {label}" if key in selected else label
            row_btns.append(InlineKeyboardButton(text=display, callback_data=key))
        kb.append(row_btns)
    kb.append([InlineKeyboardButton(text="✅ DONE SELECTING", callback_data="done_selecting")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def build_goal_selection_text(selected: set[str], lang: str = "uz") -> str:
    lines = ["🎯 *AI LIFE OPERATING SYSTEM*", ""]

    header = {
        "uz": "Qaysi maqsadlarga erishmoqchisiz?\nBir nechta maqsad tanlashingiz mumkin.",
        "ru": "Каких целей вы хотите достичь?\nМожно выбрать несколько.",
        "en": "What goals do you want to achieve?\nYou can select multiple.",
    }
    lines.append(header.get(lang, header["en"]))
    lines.append("")

    custom_instruction = {
        "uz": "Agar kerakli goal tugmalarda bo'lmasa,\nuni o'zingiz yozishingiz ham mumkin ✍️",
        "ru": "Если нужной цели нет в кнопках,\nвы можете написать свою ✍️",
        "en": "If your goal isn't in the buttons,\nyou can type your own ✍️",
    }
    lines.append(custom_instruction.get(lang, custom_instruction["en"]))
    lines.append("")

    examples = {
        "uz": "_Misol:_ /goal dan keyin shunchaki matn yozing:\n\"IELTS 8 olmoqchiman\" yoki \"Frontend developer bo'lmoqchiman\"",
        "ru": "_Пример:_ после /goal просто напишите текст:\n\"Хочу сдать IELTS на 8\" или \"Хочу стать фронтенд-разработчиком\"",
        "en": "_Example:_ after /goal just type your goal:\n\"I want IELTS 8\" or \"I want to be a frontend developer\"",
    }
    lines.append(examples.get(lang, examples["en"]))
    lines.append("")

    for cat_key, cat_goals in GOAL_CATEGORIES.items():
        meta = CATEGORY_META[cat_key]
        cat_label = meta.get(f"label_{lang}", meta["label_en"])
        lines.append(f"{meta['emoji']} *{cat_label}*")

        for gk in sorted(cat_goals):
            display_name = GOAL_DISPLAY_NAMES.get(gk, gk)
            check = "✅" if gk in selected else "⬜"
            lines.append(f"{check} {display_name}")
        lines.append("")

    footer = {
        "uz": "👇 Tugmalardan tanlang yoki custom goal yozing.",
        "ru": "👇 Выберите из кнопок или напишите свою цель.",
        "en": "👇 Select from buttons or type your custom goal.",
    }
    lines.append(footer.get(lang, footer["en"]))
    return "\n".join(lines)


def query_hf(messages: list[dict], api_key: str):
    models = [MODEL, FALLBACK_MODEL]
    for model in models:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 4096,
            }
            resp = requests.post(
                HF_BASE_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content:
                return content
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            logger.warning("Model %s HTTP %s: %s", model, status, e.response.text[:300])
            if status == 401:
                raise
        except Exception as e:
            logger.warning("Model %s failed: %s", model, e)
    return None


class GoalHandlers:
    def __init__(self, dp, db, bot, api_key, food_tracker, prompts_module, session_manager=None, discipline_engine=None):
        self.dp = dp
        self.db = db
        self.bot = bot
        self.api_key = api_key
        self.food_tracker = food_tracker
        self.prompts = prompts_module
        self.session_manager = session_manager
        self.discipline_engine = discipline_engine
        self.cal_calc = CalorieCalculator()
        self.routine_engine = RoutineEngine()
        self.ai_content_gen = AITaskContentGenerator(api_key)
        self.schedule_gen = ScheduleGenerator(api_key, prompts_module)
        self.profile_analyzer = ProfileAnalyzer(api_key)
        self.mission_gen = DailyMissionGenerator(api_key, db)
        self.goal_parser = AIGoalParser(api_key)
        self._register()

    def _register(self):

        @self.dp.message(Command("goal"))
        async def cmd_goal(message: types.Message, state: FSMContext):
            uid = message.from_user.id
            lang = await self.db.get_language(uid)
            await self.db.ensure_user(uid)
            await state.set_state(GoalStates.selecting_goals)
            await state.update_data(selected_goals=[], answers={})
            text = build_goal_selection_text(set(), lang)
            await message.answer(text, reply_markup=make_goal_keyboard())

        @self.dp.callback_query(F.data == "custom_goal_btn", GoalStates.selecting_goals)
        async def on_custom_goal_btn_click(callback: types.CallbackQuery, state: FSMContext):
            lang = await self.db.get_language(callback.from_user.id)
            msg = {
                "uz": "Qanday maqsadga erishmoqchisiz? Iltimos, aniqroq yozing. Masalan: 'Nemis tilini o'rganish'",
                "ru": "Какую цель вы хотите достичь? Пожалуйста, напишите подробнее. Например: 'Изучение немецкого языка'",
                "en": "What goal do you want to achieve? Please write clearly. Example: 'Learn German'"
            }.get(lang, "Please type your goal.")
            
            await callback.message.answer(msg)
            await callback.answer()

        @self.dp.callback_query(F.data == "done_selecting", GoalStates.selecting_goals)
        async def on_done_selecting(callback: types.CallbackQuery, state: FSMContext):
            data = await state.get_data()
            selected: list[str] = list(data.get("selected_goals", []))
            uid = callback.from_user.id
            lang = await self.db.get_language(uid)

            if not selected:
                msg = {
                    "uz": "Hech bo'lmaganda bitta maqsad tanlang!",
                    "ru": "Выберите хотя бы одну цель!",
                    "en": "Please select at least one goal!",
                }.get(lang, "Please select at least one goal!")
                await callback.answer(msg, show_alert=True)
                return

            await callback.answer()

            data = await state.get_data()
            if data.get("question_queue"):
                return

            goal_keys = selected
            goal_sources = {k: "button" for k in goal_keys}
            question_queue = get_all_questions(goal_keys, lang)

            goals_display = "\n".join(f"• {GOAL_DISPLAY_NAMES.get(k, k)}" for k in selected)
            summary_labels = {
                "uz": f"✅ *Tanlangan maqsadlar:*\n{goals_display}\n\nEndi har bir maqsad bo'yicha savollar beraman. Barchasiga javob bering.",
                "ru": f"✅ *Выбранные цели:*\n{goals_display}\n\nТеперь задам вопросы по каждой цели. Ответьте на все.",
                "en": f"✅ *Selected Goals:*\n{goals_display}\n\nNow I will ask questions for each goal. Answer all of them.",
            }
            await callback.message.edit_text(summary_labels.get(lang, summary_labels["en"]))

            await state.update_data(
                goal_keys=goal_keys,
                goal_sources=goal_sources,
                question_queue=question_queue,
                current_index=0,
                answers={},
            )

            if question_queue:
                await self._ask_next_question(callback.message, state, uid, lang)
            else:
                await self._finish_and_generate(callback.message, state, uid, lang)

        @self.dp.callback_query(F.data.in_(list(KEY_TO_LABEL.keys())), GoalStates.selecting_goals)
        async def on_goal_select(callback: types.CallbackQuery, state: FSMContext):
            data = await state.get_data()
            selected: list[str] = list(data.get("selected_goals", []))
            lang = await self.db.get_language(callback.from_user.id)
            key = callback.data

            if key in selected:
                selected.remove(key)
                label = KEY_TO_LABEL.get(key, key)
                await callback.answer(f"❌ {label} olib tashlandi")
            else:
                selected.append(key)
                label = KEY_TO_LABEL.get(key, key)
                await callback.answer(f"✅ {label} qo'shildi")

            await state.update_data(selected_goals=selected)
            text = build_goal_selection_text(set(selected), lang)
            await callback.message.edit_text(text, reply_markup=make_goal_keyboard(set(selected)))

        @self.dp.message(GoalStates.selecting_goals)
        async def on_custom_goal_text(message: types.Message, state: FSMContext):
            if not message.text:
                return
            goal_text = message.text.strip()
            if not goal_text or goal_text.startswith("/"):
                return

            uid = message.from_user.id
            lang = await self.db.get_language(uid)

            # Ignore if it's a single number (mission completion intent)
            data = await state.get_data()
            selected = data.get("selected_goals", [])
            if goal_text.isdigit() and selected:
                return
            if goal_text.replace(".", "", 1).isdigit():
                return

            async with ChatActionSender.typing(bot=self.bot, chat_id=message.chat.id):
                parse_result = self.goal_parser.parse(goal_text, lang)

            logger.info(
                "[GoalFlow] User %d sent custom goal: '%s' | AI mapped to: %s (confidence=%.2f, category=%s, reasoning=%s)",
                uid, goal_text[:80], parse_result.mapped_goal_keys,
                parse_result.confidence, parse_result.category, parse_result.reasoning,
            )

            selected_goals = data.get("selected_goals", [])

            if parse_result.mapped_goal_keys:
                goal_keys = list(selected_goals)
                goal_sources = {k: "button" for k in selected_goals}
                for k in parse_result.mapped_goal_keys:
                    if k not in goal_sources:
                        goal_keys.append(k)
                        goal_sources[k] = "ai"
                question_queue = []
                for key in goal_keys:
                    question_queue.extend(get_questions(key, lang))

                await state.update_data(
                    is_custom_goal=True,
                    custom_goal_text=goal_text,
                    custom_goal_display=parse_result.normalized_goal,
                    custom_goal_category=parse_result.category,
                    goal_parse_result=parse_result.to_dict(),
                    goal_keys=goal_keys,
                    goal_sources=goal_sources,
                    question_queue=question_queue,
                    current_index=0,
                    answers={},
                )

                goals_display = "\n".join(f"• {GOAL_DISPLAY_NAMES.get(k, k)}" for k in goal_keys)
                summary_labels = {
                    "uz": f"✅ *AI tahlili:* \"{parse_result.normalized_goal}\"\n\n"
                          f"AI sizning maqsadingizni quyidagi sohalarga moslashtirdi:\n{goals_display}\n\n"
                          f"Endi har bir maqsad bo'yicha savollar beraman. Barchasiga javob bering.",
                    "ru": f"✅ *AI анализ:* \"{parse_result.normalized_goal}\"\n\n"
                          f"AI сопоставил вашу цель со следующими областями:\n{goals_display}\n\n"
                          f"Теперь задам вопросы по каждой цели. Ответьте на все.",
                    "en": f"✅ *AI Analysis:* \"{parse_result.normalized_goal}\"\n\n"
                          f"AI mapped your goal to these areas:\n{goals_display}\n\n"
                          f"Now I will ask questions for each area. Answer all of them.",
                }
                await message.answer(summary_labels.get(lang, summary_labels["en"]))
                if question_queue:
                    await self._ask_next_question(message, state, uid, lang)
                else:
                    await self._finish_and_generate(message, state, uid, lang)
            else:
                goal_keys = list(selected_goals) + ["__custom__"]
                goal_sources = {k: "button" for k in selected_goals}
                goal_sources["__custom__"] = "ai"
                await state.update_data(
                    is_custom_goal=True,
                    custom_goal_text=goal_text,
                    custom_goal_display=goal_text,
                    custom_goal_category=parse_result.category,
                    goal_parse_result=parse_result.to_dict(),
                    goal_keys=goal_keys,
                    goal_sources=goal_sources,
                    question_queue=[],
                    current_index=0,
                    answers={},
                )

                ai_questions = await self._analyze_custom_goal(goal_text, uid, lang)
                ai_qs = ai_questions.get("questions", [])
                fake_questions = []
                for q in ai_qs:
                    fake_questions.append({
                        "goal": "__custom__",
                        "field": q.get("field", "custom_answer"),
                        "text": q.get("text", goal_text),
                    })

                if not fake_questions:
                    default_q = {
                        "uz": f"\"{goal_text}\" — bu maqsad siz uchun qanchalik muhim?",
                        "ru": f"\"{goal_text}\" — насколько важна для вас эта цель?",
                        "en": f"\"{goal_text}\" — how important is this goal to you?",
                    }
                    fake_questions.append({
                        "goal": "__custom__",
                        "field": "goal_importance",
                        "text": default_q.get(lang, default_q["en"]),
                    })

                await state.update_data(
                    question_queue=fake_questions,
                    current_index=0,
                    answers={},
                )

                goal_display = ai_questions.get("goal_display", goal_text)
                summary_labels = {
                    "uz": f"✅ *Custom goal qabul qilindi:* \"{goal_display}\"\n\nEndi bu maqsad bo'yicha savollar beraman. Barchasiga javob bering.",
                    "ru": f"✅ *Пользовательская цель принята:* \"{goal_display}\"\n\nТеперь задам вопросы по этой цели. Ответьте на все.",
                    "en": f"✅ *Custom goal accepted:* \"{goal_display}\"\n\nNow I'll ask questions about this goal. Answer all of them.",
                }
                await message.answer(summary_labels.get(lang, summary_labels["en"]))
                await self._ask_next_question(message, state, uid, lang)

        @self.dp.message(GoalStates.goal_qa, ~F.text.startswith("/"))
        async def on_goal_answer(message: types.Message, state: FSMContext):
            if not message.text:
                return
            txt = message.text.strip()
            data = await state.get_data()
            answers = dict(data.get("answers", {}))
            current_field = data.get("current_field", "")
            uid = message.from_user.id
            lang = await self.db.get_language(uid)

            if current_field:
                answers[current_field] = txt

            await state.update_data(answers=answers)
            await self._ask_next_question(message, state, uid, lang)

        @self.dp.message(Command("progress"))
        async def cmd_progress(message: types.Message):
            from .progress import ProgressTracker

            uid = message.from_user.id
            lang = await self.db.get_language(uid)
            pt = ProgressTracker(self.db)
            report = await pt.get_weekly_report(uid, lang)
            await message.answer(report)

        @self.dp.message(Command("streak"))
        async def cmd_streak(message: types.Message):
            from .progress import ProgressTracker

            uid = message.from_user.id
            lang = await self.db.get_language(uid)
            pt = ProgressTracker(self.db)
            msg = await pt.format_streak_message(uid, lang)
            await message.answer(msg)

        @self.dp.message(Command("missions"))
        async def cmd_missions(message: types.Message):
            uid = message.from_user.id
            lang = await self.db.get_language(uid)
            if self.session_manager:
                self.session_manager.set_mode(uid, "missions")
                self.session_manager.get(uid).awaiting_mission_number = True
            data = await self.mission_gen.get_todays_missions_data(uid)
            if not data:
                labels = {
                    "uz": "Bugun uchun missiyalar hali yaratilmagan. /goal orqali maqsadlaringizni belgilang!",
                    "ru": "Миссии на сегодня еще не созданы. Установите цели через /goal!",
                    "en": "No missions for today yet. Set your goals with /goal!",
                }
                await message.answer(labels.get(lang, labels["en"]))
                return
            missions, streak, completed, total = data
            text = DailyMissionGenerator.build_missions_text(missions, streak, completed, total, lang)
            kb = DailyMissionGenerator.build_missions_keyboard(missions)
            await message.answer(text, reply_markup=kb)

        @self.dp.callback_query(F.data.startswith("mc:"))
        async def on_mission_complete(callback: types.CallbackQuery):
            uid = callback.from_user.id
            lang = await self.db.get_language(uid)

            parts = callback.data.split(":")
            if len(parts) != 2 or not parts[1].isdigit():
                await callback.answer("Invalid request", show_alert=True)
                return

            mission_idx = int(parts[1])
            today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")

            row = await self.db.get_daily_missions(uid, today)
            if not row:
                await callback.answer("No missions today", show_alert=True)
                return

            missions = json.loads(row["missions_json"])
            if mission_idx < 0 or mission_idx >= len(missions):
                await callback.answer("Mission not found", show_alert=True)
                return

            if missions[mission_idx].get("completed"):
                await callback.answer("Already completed!", show_alert=True)
                return

            missions[mission_idx]["completed"] = True
            missions[mission_idx]["completed_at"] = datetime.now().strftime("%H:%M")
            await self.db.save_daily_missions(uid, json.dumps(missions, ensure_ascii=False), today)

            streak = await self.db.get_mission_streak(uid)
            completed = sum(1 for m in missions if m.get("completed"))
            total = len(missions)

            text = DailyMissionGenerator.build_missions_text(missions, streak, completed, total, lang)
            kb = DailyMissionGenerator.build_missions_keyboard(missions)

            await callback.message.edit_text(text, reply_markup=kb)
            await callback.answer()

        @self.dp.message(Command("done"))
        async def cmd_done(message: types.Message):
            uid = message.from_user.id
            lang = await self.db.get_language(uid)
            parts = message.text.split()
            if len(parts) == 2 and parts[1].isdigit():
                if self.session_manager:
                    self.session_manager.reset(uid)
                today = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
                row = await self.db.get_daily_missions(uid, today)
                if row:
                    missions = json.loads(row["missions_json"])
                    idx = int(parts[1])
                    if 1 <= idx <= len(missions) and not missions[idx - 1].get("completed"):
                        missions[idx - 1]["completed"] = True
                        missions[idx - 1]["completed_at"] = datetime.now().strftime("%H:%M")
                        await self.db.save_daily_missions(uid, json.dumps(missions, ensure_ascii=False), today)
                        labels = {
                            "uz": f"✅ {idx}-missiya bajarildi!",
                            "ru": f"✅ Миссия {idx} выполнена!",
                            "en": f"✅ Mission {idx} complete!",
                        }
                        await message.answer(labels.get(lang, labels["en"]))
                        return
                labels = {
                    "uz": "❌ Missiya topilmadi yoki allaqachon bajarilgan.",
                    "ru": "❌ Миссия не найдена или уже выполнена.",
                    "en": "❌ Mission not found or already completed.",
                }
                await message.answer(labels.get(lang, labels["en"]))
            else:
                await message.answer("Usage: /done <number>")

        @self.dp.message(Command("profile"))
        async def cmd_profile(message: types.Message):
            uid = message.from_user.id
            lang = await self.db.get_language(uid)
            profile = await self.db.get_user_profile(uid)
            if not profile:
                msg = {
                    "uz": "Hali profilingiz yaratilmagan. /goal orqali maqsadlaringizni belgilang!",
                    "ru": "Ваш профиль еще не создан. Установите цели через /goal!",
                    "en": "Your profile hasn't been created yet. Set your goals with /goal!",
                }
                await message.answer(msg.get(lang, msg["en"]))
                return

            try:
                profile_data = json.loads(profile["profile_json"])
            except (json.JSONDecodeError, TypeError):
                profile_data = {}

            labels = {
                "uz": "🧠 *AI PROFILINGIZ*",
                "ru": "🧠 *ВАШ AI ПРОФИЛЬ*",
                "en": "🧠 *YOUR AI PROFILE*",
            }
            lines = [labels.get(lang, labels["en"]), ""]

            field_labels = {
                "uz": {
                    "discipline_level": "Intizom darajasi",
                    "fitness_level": "Fitness darajasi",
                    "learning_style": "O'rganish uslubi",
                    "stress_level": "Stress darajasi",
                    "sleep_quality": "Uyqu sifati",
                    "focus_ability": "Diqqat qobiliyati",
                    "productivity_level": "Mahsuldorlik darajasi",
                    "consistency_score": "Barqarorlik balli",
                    "confidence_level": "Ishonch darajasi",
                    "personality_summary": "Shaxsiy xulosa",
                },
                "ru": {
                    "discipline_level": "Уровень дисциплины",
                    "fitness_level": "Уровень фитнеса",
                    "learning_style": "Стиль обучения",
                    "stress_level": "Уровень стресса",
                    "sleep_quality": "Качество сна",
                    "focus_ability": "Способность к концентрации",
                    "productivity_level": "Уровень продуктивности",
                    "consistency_score": "Балл последовательности",
                    "confidence_level": "Уровень уверенности",
                    "personality_summary": "Личностное резюме",
                },
                "en": {
                    "discipline_level": "Discipline Level",
                    "fitness_level": "Fitness Level",
                    "learning_style": "Learning Style",
                    "stress_level": "Stress Level",
                    "sleep_quality": "Sleep Quality",
                    "focus_ability": "Focus Ability",
                    "productivity_level": "Productivity Level",
                    "consistency_score": "Consistency Score",
                    "confidence_level": "Confidence Level",
                    "personality_summary": "Personality Summary",
                },
            }
            fl = field_labels.get(lang, field_labels["en"])

            for key, label in fl.items():
                if key in profile_data:
                    val = profile_data[key]
                    if isinstance(val, (int, float)):
                        bar = self._progress_bar(val, 10)
                        lines.append(f"{bar} *{label}*: {val}/100")
                    elif isinstance(val, str):
                        lines.append(f"• *{label}*: {val}")
                    elif isinstance(val, list):
                        lines.append(f"• *{label}*: {', '.join(val)}")

            await message.answer("\n".join(lines))

    async def _ask_next_question(self, msg_obj, state: FSMContext, uid: int, lang: str):
        data = await state.get_data()
        queue = data.get("question_queue", [])
        index = data.get("current_index", 0)

        if index >= len(queue):
            msgs = {
                "uz": "Ajoyib! Barcha savollarga javob berdingiz. Endi profilingizni tahlil qilaman va shaxsiy rejangizni tuzaman...",
                "ru": "Отлично! Вы ответили на все вопросы. Теперь анализирую ваш профиль и создаю план...",
                "en": "Excellent! You've answered all questions. Now analyzing your profile and generating your plan...",
            }
            await msg_obj.answer(msgs.get(lang, msgs["en"]))
            await self._finish_and_generate(msg_obj, state, uid, lang)
            return

        q = queue[index]
        await state.set_state(GoalStates.goal_qa)
        await state.update_data(
            current_index=index + 1,
            current_field=q["field"],
            current_goal=q["goal"],
        )

        display_name = GOAL_DISPLAY_NAMES.get(q["goal"], q["goal"])
        if q["goal"] == "__custom__":
            display_name = (await state.get_data()).get("custom_goal_display", "Custom Goal")
        header = f"📌 *{display_name}* — Savol {index + 1}/{len(queue)}"
        await msg_obj.answer(f"{header}\n\n{q['text']}")

    async def _analyze_custom_goal(self, goal_text: str, uid: int, lang: str) -> dict:
        L = lang if lang in ("uz", "ru", "en") else "uz"
        lang_rule_text = lang_rule(L)
        prompt = CUSTOM_GOAL_ANALYSIS_PROMPT.format(
            language_rule=lang_rule_text,
            goal_text=goal_text,
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"My custom goal: {goal_text}"},
        ]
        try:
            content = query_hf(messages, self.api_key)
            if content:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
        except Exception as e:
            logger.warning("Custom goal analysis failed for user %d: %s", uid, e)
        return {
            "category": "general",
            "goal_display": goal_text,
            "questions": [
                {"field": "goal_importance", "text": self._default_custom_question(goal_text, L)},
            ],
        }

    def _default_custom_question(self, goal_text: str, lang: str) -> str:
        texts = {
            "uz": f"\"{goal_text}\" — bu maqsad siz uchun qanchalik muhim? Nima uchun aynan shu maqsad?",
            "ru": f"\"{goal_text}\" — насколько важна для вас эта цель? Почему именно эта цель?",
            "en": f"\"{goal_text}\" — how important is this goal to you? Why this goal?",
        }
        return texts.get(lang, texts["en"])

    async def _finish_and_generate(self, msg_obj, state: FSMContext, uid: int, lang: str):
        data = await state.get_data()
        answers = dict(data.get("answers", {}))
        goal_keys: list[str] = data.get("goal_keys", [])
        is_custom = data.get("is_custom_goal", False)
        goal_sources: dict = data.get("goal_sources", {})
        custom_goal_text = data.get("custom_goal_text", "")
        custom_goal_display = data.get("custom_goal_display", custom_goal_text)
        custom_goal_category = data.get("custom_goal_category", "general")
        goal_parse_result: dict = data.get("goal_parse_result", {})

        has_real_keys = any(k != "__custom__" for k in goal_keys)
        is_pure_custom = is_custom and not has_real_keys

        if is_pure_custom:
            goals_display = custom_goal_display
            goal_answers_text = "\n".join(f"{k}: {v}" for k, v in sorted(answers.items()))
            custom_data = {
                "text": custom_goal_text,
                "display": custom_goal_display,
                "category": custom_goal_category,
                "ai_parse_result": goal_parse_result,
            }
        else:
            goals_display = ", ".join(GOAL_DISPLAY_NAMES.get(k, k) for k in goal_keys if k != "__custom__")
            goal_answers_text = ""
            for key in goal_keys:
                if key == "__custom__":
                    continue
                display_name = GOAL_DISPLAY_NAMES.get(key, key)
                goal_questions = GOAL_QUESTIONS.get(key, [])
                goal_answers_text += f"\n--- {display_name} ---\n"
                for q in goal_questions:
                    field = q["field"]
                    answer = answers.get(field, "no answer")
                    goal_answers_text += f"{field}: {answer}\n"
            if "__custom__" in goal_keys:
                custom_data = {
                    "text": custom_goal_text,
                    "display": custom_goal_display,
                    "category": custom_goal_category,
                    "ai_parse_result": goal_parse_result,
                }
            else:
                custom_data = None

        all_answers_text = "\n".join(f"{k}: {v}" for k, v in sorted(answers.items()))

        # Step 1: Analyze user profile via AI
        async with ChatActionSender.typing(bot=self.bot, chat_id=msg_obj.chat.id):
            try:
                profile_data = self.profile_analyzer.analyze(goals_display, all_answers_text, lang)
            except Exception as e:
                logger.exception("Profile analysis failed: %s", e)
                profile_data = self.profile_analyzer._default_profile()

            await self.db.save_user_profile(uid, json.dumps(profile_data, ensure_ascii=False))

        # Step 2: Save goals to database
        await self._save_goals(uid, goal_keys, answers, custom_data)
        saved_goals = await self.db.get_goals(uid)

        # Step 3: Generate routine
        if is_pure_custom:
            daily_routine = await self._generate_custom_routine(custom_goal_text, custom_goal_display, all_answers_text, lang)
        else:
            daily_routine = self.routine_engine.generate(goal_keys)
        routine_text = self.routine_engine.format_routine_text(daily_routine, lang)

        # Step 4: Create routines in database
        if self.discipline_engine:
            try:
                created = await self.discipline_engine.create_routines_from_goals(uid, daily_routine, saved_goals)
                if created:
                    logger.info("Created %d routines for user %d", created, uid)
            except Exception as e:
                logger.warning("Routine creation failed for user %d: %s", uid, e)

        # Step 5: Generate AI task content per goal
        task_content: dict[str, list[str]] = {}
        async with ChatActionSender.typing(bot=self.bot, chat_id=msg_obj.chat.id):
            try:
                if is_pure_custom:
                    goal_name = custom_goal_display
                    tasks = await self.ai_content_gen.generate_for_goal(
                        "__custom__", goal_name, goal_answers_text,
                        json.dumps(profile_data, ensure_ascii=False), lang,
                    )
                    task_content[custom_goal_display] = tasks
                else:
                    task_content = await self.ai_content_gen.generate_all(
                        uid, goal_keys, GOAL_QUESTIONS, answers, json.dumps(profile_data, ensure_ascii=False), lang
                    )
            except Exception as e:
                logger.warning("AI task content generation failed: %s", e)

        # Step 6: Generate daily missions
        async with ChatActionSender.typing(bot=self.bot, chat_id=msg_obj.chat.id):
            try:
                missions = await self.mission_gen.generate_missions(
                    uid, goals_display, json.dumps(profile_data, ensure_ascii=False), lang, goal_answers_text
                )
            except Exception as e:
                logger.warning("Mission generation failed: %s", e)
                missions = []

        # Step 7: Display routine + tasks + missions
        await self._display_routine_plan(msg_obj, daily_routine, task_content, missions, lang, profile_data, is_pure_custom, custom_goal_display)
        await state.clear()

    async def _generate_custom_routine(self, goal_text: str, goal_display: str, all_answers: str, lang: str) -> list[dict]:
        L = lang if lang in ("uz", "ru", "en") else "uz"
        lang_rule_text = lang_rule(L)
        prompt = CUSTOM_GOAL_ROUTINE_PROMPT.format(
            language_rule=lang_rule_text,
            goal_display=goal_display,
            goal_answers=all_answers or "No specific data.",
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Generate a daily routine for {goal_display}"},
        ]
        try:
            content = query_hf(messages, self.api_key)
            if content:
                lines = content.strip().split("\n")
                routine = []
                for line in lines:
                    line = line.strip()
                    if "–" in line or "—" in line:
                        sep = "–" if "–" in line else "—"
                        parts = line.split(sep, 1)
                        time_candidate = parts[0].strip()
                        title = parts[1].strip()
                        time_match = __import__("re").match(r"^(\d{2}:\d{2})", time_candidate)
                        if time_match:
                            routine.append({
                                "time": time_match.group(1),
                                "title": title,
                                "category": "custom",
                                "goal_key": "__custom__",
                            })
                if routine:
                    return routine
        except Exception as e:
            logger.warning("Custom routine generation failed: %s", e)

        return [
            {"time": "07:00", "title": "Wake Up & Morning Routine", "category": "general", "goal_key": None},
            {"time": "09:00", "title": f"Work on {goal_display}", "category": "custom", "goal_key": "__custom__"},
            {"time": "12:00", "title": "Lunch & Rest", "category": "general", "goal_key": None},
            {"time": "14:00", "title": f"Continue {goal_display}", "category": "custom", "goal_key": "__custom__"},
            {"time": "17:00", "title": "Break & Recovery", "category": "general", "goal_key": None},
            {"time": "20:00", "title": "Evening Review & Planning", "category": "general", "goal_key": None},
            {"time": "22:00", "title": "Sleep Preparation", "category": "general", "goal_key": None},
            {"time": "23:00", "title": "Sleep", "category": "general", "goal_key": None},
        ]

    async def _save_goals(self, uid: int, goal_keys: list[str], answers: dict, custom_data: dict = None):
        for key in goal_keys:
            if key == "__custom__":
                if custom_data:
                    cat = custom_data.get("category", "general")
                    display_name = custom_data.get("display", custom_data.get("text", "Custom Goal"))
                    gid = await self.db.add_goal(uid, display_name, cat)
                    for field, val in sorted(answers.items()):
                        if val:
                            await self.db.save_goal_detail(uid, gid, field, val)
                continue
            else:
                cat = get_category_for_goal(key)
                display_name = GOAL_DISPLAY_NAMES.get(key, key)
                gid = await self.db.add_goal(uid, display_name, cat)
                questions = GOAL_QUESTIONS.get(key, [])
                for q in questions:
                    field = q["field"]
                    val = answers.get(field, "")
                    if val:
                        await self.db.save_goal_detail(uid, gid, field, val)

    async def _display_routine_plan(self, msg_obj, routine: list[dict], task_content: dict[str, list[str]], missions: list, lang: str, profile: dict, is_custom: bool = False, custom_goal_display: str = ""):
        routine_text = self.routine_engine.format_routine_text(routine, lang)
        await msg_obj.answer(routine_text)

        task_lines = []
        task_labels = {
            "uz": "\U0001f4cb *Vazifalar*",
            "ru": "\U0001f4cb *Задачи*",
            "en": "\U0001f4cb *Tasks*",
        }
        if task_content:
            task_lines.append(task_labels.get(lang, task_labels["en"]))
            for goal_key, tasks in task_content.items():
                if not tasks:
                    continue
                if is_custom:
                    goal_name = custom_goal_display or goal_key
                else:
                    goal_name = GOAL_DISPLAY_NAMES.get(goal_key, goal_key.replace("_", " ").title())
                task_lines.append(f"\n**{goal_name}**")
                for t in tasks:
                    task_lines.append(f"* {t}")
            await msg_obj.answer("\n".join(task_lines))

        profile_lines = [
            {
                "uz": "🧠 *AI PROFILINGIZ*",
                "ru": "🧠 *ВАШ AI ПРОФИЛЬ*",
                "en": "🧠 *YOUR AI PROFILE*",
            }.get(lang, ""),
            "",
        ]
        field_labels = {
            "uz": {"discipline_level": "Intizom", "fitness_level": "Fitness", "focus_ability": "Diqqat", "productivity_level": "Mahsuldorlik", "consistency_score": "Barqarorlik"},
            "ru": {"discipline_level": "Дисциплина", "fitness_level": "Фитнес", "focus_ability": "Фокус", "productivity_level": "Продуктивность", "consistency_score": "Последовательность"},
            "en": {"discipline_level": "Discipline", "fitness_level": "Fitness", "focus_ability": "Focus", "productivity_level": "Productivity", "consistency_score": "Consistency"},
        }
        fl = field_labels.get(lang, field_labels["en"])
        for key, label in fl.items():
            if key in profile:
                val = profile[key]
                if isinstance(val, (int, float)):
                    bar = self._progress_bar(val, 10)
                    profile_lines.append(f"{bar} *{label}*: {val}/100")
        if len(profile_lines) > 1:
            await msg_obj.answer("\n".join(profile_lines))

        if missions:
            text = DailyMissionGenerator.build_missions_text(missions, 0, 0, len(missions), lang)
            kb = DailyMissionGenerator.build_missions_keyboard(missions)
            await msg_obj.answer(text, reply_markup=kb)

        confirm_msgs = {
            "uz": "✅ *AI Life Operating System ishga tushdi!*\n\n"
                  "Buyruqlar:\n"
                  "/missions — Bugungi missiyalar 🔥\n"
                  "/profile — AI profilingiz 🧠\n"
                  "/progress — Haftalik hisobot 📊\n"
                  "/streak — Streyklaringiz 🔥\n"
                  "/routine — Kunlik tartib 📋\n"
                  "/today — Bugungi vazifalar 📅\n"
                  "/food_calorie — Ovqat yozish 🍽️\n"
                  "/goal — Yangi maqsadlar 🎯",
            "ru": "✅ *AI Life Operating System запущена!*\n\n"
                  "Команды:\n"
                  "/missions — Миссии на сегодня 🔥\n"
                  "/profile — AI профиль 🧠\n"
                  "/progress — Еженедельный отчет 📊\n"
                  "/streak — Ваши серии 🔥\n"
                  "/routine — Дневной распорядок 📋\n"
                  "/today — Задачи на сегодня 📅\n"
                  "/food_calorie — Запись еды 🍽️\n"
                  "/goal — Новые цели 🎯",
            "en": "✅ *AI Life Operating System is LIVE!*\n\n"
                  "Commands:\n"
                  "/missions — Today's missions 🔥\n"
                  "/profile — Your AI profile 🧠\n"
                  "/progress — Weekly report 📊\n"
                  "/streak — Your streaks 🔥\n"
                  "/routine — Daily routine 📋\n"
                  "/today — Today's tasks 📅\n"
                  "/food_calorie — Log meals 🍽️\n"
                  "/goal — Set new goals 🎯",
        }
        await msg_obj.answer(confirm_msgs.get(lang, confirm_msgs["en"]))

    def _progress_bar(self, value: int, total_blocks: int = 10) -> str:
        filled = max(0, min(total_blocks, round(value / 100 * total_blocks)))
        empty = total_blocks - filled
        return "▓" * filled + "░" * empty

    def _split_message(self, text: str, max_len: int = 3500) -> list[str]:
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
