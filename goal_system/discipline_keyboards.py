from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def reminder_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Completed", callback_data=f"disc_complete:{routine_id}"),
            InlineKeyboardButton(text="⏰ Delay", callback_data=f"disc_delay:{routine_id}"),
            InlineKeyboardButton(text="📊 Report", callback_data=f"disc_report"),
        ],
    ])


def delay_options_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="10 min", callback_data=f"disc_delay_set:{routine_id}:10"),
            InlineKeyboardButton(text="30 min", callback_data=f"disc_delay_set:{routine_id}:30"),
            InlineKeyboardButton(text="1 hour", callback_data=f"disc_delay_set:{routine_id}:60"),
        ],
        [InlineKeyboardButton(text="❌ Skip", callback_data=f"disc_skip:{routine_id}")],
    ])


def quick_complete_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Fully completed", callback_data=f"disc_full:{routine_id}"),
            InlineKeyboardButton(text="🟡 Partial", callback_data=f"disc_partial:{routine_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Skipped", callback_data=f"disc_skip:{routine_id}"),
        ],
    ])


def report_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Today's Report", callback_data="disc_report")],
    ])


# ── Manual Task Activation Keyboards ──


def task_action_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Start Task", callback_data=f"task_start:{routine_id}")],
        [
            InlineKeyboardButton(text="📊 Details", callback_data=f"task_details:{routine_id}"),
            InlineKeyboardButton(text="⏰ Reschedule", callback_data=f"task_reschedule:{routine_id}"),
        ],
    ])


def active_task_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Finish", callback_data=f"task_finish:{routine_id}"),
            InlineKeyboardButton(text="⏸ Pause", callback_data=f"task_pause:{routine_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"task_cancel:{routine_id}"),
        ],
    ])


def active_task_with_focus_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Finish", callback_data=f"task_finish:{routine_id}"),
            InlineKeyboardButton(text="⏸ Pause", callback_data=f"task_pause:{routine_id}"),
        ],
        [
            InlineKeyboardButton(text="🎯 Focus Mode", callback_data=f"task_focus:{routine_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"task_cancel:{routine_id}"),
        ],
    ])


def paused_task_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Resume", callback_data=f"task_resume:{routine_id}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"task_cancel:{routine_id}"),
        ],
    ])


def switch_task_kb(new_routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Continue Current", callback_data="task_keep_current"),
            InlineKeyboardButton(text="🔄 Switch Task", callback_data=f"task_switch_confirm:{new_routine_id}"),
        ],
    ])


def mid_session_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes", callback_data=f"task_mid_yes:{routine_id}"),
            InlineKeyboardButton(text="❌ Stopped", callback_data=f"task_mid_no:{routine_id}"),
        ],
    ])


def focus_options_kb(routine_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 25 min", callback_data=f"task_focus_start:{routine_id}:25"),
            InlineKeyboardButton(text="🎯 45 min", callback_data=f"task_focus_start:{routine_id}:45"),
        ],
        [
            InlineKeyboardButton(text="🎯 60 min", callback_data=f"task_focus_start:{routine_id}:60"),
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"task_back:{routine_id}")],
    ])


def focus_complete_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Done", callback_data="task_focus_done")],
    ])


def today_dashboard_kb(routines: list, logs: list, active_rid: int | None = None) -> InlineKeyboardMarkup:
    kb_rows = []
    log_map = {}
    for l in logs:
        log_map[l["routine_id"]] = l

    for r in routines:
        l = log_map.get(r["id"])
        if l and l["status"] in ("completed", "partial", "skipped"):
            continue
        if r["id"] == active_rid:
            continue
        kb_rows.append([
            InlineKeyboardButton(
                text=f"▶️ {r['scheduled_time']} {r['title']}",
                callback_data=f"task_start:{r['id']}",
            ),
        ])

    if active_rid:
        for r in routines:
            if r["id"] == active_rid:
                kb_rows.append([
                    InlineKeyboardButton(
                        text=f"🔥 Active: {r['title']}",
                        callback_data=f"task_active_menu:{active_rid}",
                    ),
                ])
                break

    kb_rows.append([InlineKeyboardButton(text="📊 Dashboard", callback_data="task_dashboard")])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)
