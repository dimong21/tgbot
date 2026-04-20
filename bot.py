#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бот поддержки «Сияние неба»
Версия: 2.0 (python-telegram-bot)
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_CHAT_ID = int(os.getenv("SUPPORT_CHAT_ID", 0))
FEEDBACK_CHAT_ID = int(os.getenv("FEEDBACK_CHAT_ID", 0))
ROLE_CHAT_ID = int(os.getenv("ROLE_CHAT_ID", 0))
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/siyanie_neba")

# Пути к файлам данных
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Глобальные хранилища данных
users_db = {}
admins_db = {}
tickets_db = []
bans_db = {}
mutes_db = {}
roles_db = {}
feedback_db = []

# Счетчик тикетов
ticket_counter = 1

# Состояния для ConversationHandler
AWAITING_TICKET_TEXT = 1
AWAITING_FEEDBACK = 2
AWAITING_REPLY = 3
AWAITING_MAILING_TEXT = 4


# ==================== Функции работы с данными ====================

def load_all_data():
    """Загрузка всех данных из файлов"""
    global users_db, admins_db, tickets_db, bans_db, mutes_db, roles_db, feedback_db, ticket_counter
    
    try:
        with open(f"{DATA_DIR}/users.json", "r", encoding="utf-8") as f:
            users_db = json.load(f)
    except:
        users_db = {}
    
    try:
        with open(f"{DATA_DIR}/admins.json", "r", encoding="utf-8") as f:
            admins_db = json.load(f)
    except:
        admins_db = {}
    
    try:
        with open(f"{DATA_DIR}/tickets.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            tickets_db = data.get("tickets", [])
            ticket_counter = data.get("counter", 1)
    except:
        tickets_db = []
        ticket_counter = 1
    
    try:
        with open(f"{DATA_DIR}/bans.json", "r", encoding="utf-8") as f:
            bans_db = json.load(f)
    except:
        bans_db = {}
    
    try:
        with open(f"{DATA_DIR}/mutes.json", "r", encoding="utf-8") as f:
            mutes_db = json.load(f)
    except:
        mutes_db = {}
    
    try:
        with open(f"{DATA_DIR}/roles.json", "r", encoding="utf-8") as f:
            roles_db = json.load(f)
    except:
        roles_db = {}
    
    try:
        with open(f"{DATA_DIR}/feedback.json", "r", encoding="utf-8") as f:
            feedback_db = json.load(f)
    except:
        feedback_db = []


def save_all_data():
    """Сохранение всех данных в файлы"""
    with open(f"{DATA_DIR}/users.json", "w", encoding="utf-8") as f:
        json.dump(users_db, f, ensure_ascii=False, indent=2)
    
    with open(f"{DATA_DIR}/admins.json", "w", encoding="utf-8") as f:
        json.dump(admins_db, f, ensure_ascii=False, indent=2)
    
    with open(f"{DATA_DIR}/tickets.json", "w", encoding="utf-8") as f:
        json.dump({"tickets": tickets_db, "counter": ticket_counter}, f, ensure_ascii=False, indent=2)
    
    with open(f"{DATA_DIR}/bans.json", "w", encoding="utf-8") as f:
        json.dump(bans_db, f, ensure_ascii=False, indent=2)
    
    with open(f"{DATA_DIR}/mutes.json", "w", encoding="utf-8") as f:
        json.dump(mutes_db, f, ensure_ascii=False, indent=2)
    
    with open(f"{DATA_DIR}/roles.json", "w", encoding="utf-8") as f:
        json.dump(roles_db, f, ensure_ascii=False, indent=2)
    
    with open(f"{DATA_DIR}/feedback.json", "w", encoding="utf-8") as f:
        json.dump(feedback_db, f, ensure_ascii=False, indent=2)


def is_banned(user_id: int) -> Tuple[bool, Optional[str]]:
    """Проверка на бан пользователя"""
    ban_info = bans_db.get(str(user_id))
    if not ban_info:
        return False, None
    
    if ban_info.get("permanent", False):
        return True, "⛔ Вы заблокированы в боте навсегда."
    
    until = datetime.fromisoformat(ban_info["until"])
    if until > datetime.now():
        return True, f"⛔ Вы заблокированы до {until.strftime('%d.%m.%Y %H:%M')}"
    
    del bans_db[str(user_id)]
    save_all_data()
    return False, None


def is_muted(user_id: int) -> Tuple[bool, Optional[str]]:
    """Проверка на мут пользователя"""
    mute_info = mutes_db.get(str(user_id))
    if not mute_info:
        return False, None
    
    until = datetime.fromisoformat(mute_info["until"])
    if until > datetime.now():
        return True, f"🔇 Вы в муте до {until.strftime('%d.%m.%Y %H:%M')}\nПричина: {mute_info.get('reason', 'Не указана')}"
    
    del mutes_db[str(user_id)]
    save_all_data()
    return False, None


def get_user_mention(user_id: int, username: str = None, first_name: str = None) -> str:
    """Создание упоминания пользователя"""
    if username:
        return f"@{username}"
    return f"<a href='tg://user?id={user_id}'>{first_name or 'Пользователь'}</a>"


def has_permission(admin_id: int, permission: str) -> bool:
    """Проверка наличия права у админа"""
    admin = admins_db.get(str(admin_id), {})
    if admin.get("is_owner", False):
        return True
    return permission in admin.get("permissions", [])


def get_ticket_by_id(ticket_id: int) -> Optional[Dict]:
    """Получение тикета по ID"""
    for ticket in tickets_db:
        if ticket["id"] == ticket_id:
            return ticket
    return None


def parse_duration(time_str: str) -> Optional[timedelta]:
    """Парсинг строки времени в timedelta"""
    import re
    
    match = re.match(r"^(\d+)([dhm])$", time_str.lower())
    if not match:
        return None
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit == "d":
        return timedelta(days=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "m":
        return timedelta(minutes=value)
    
    return None


def format_ticket_info(ticket: Dict) -> str:
    """Форматирование информации о тикете"""
    status_emoji = {"open": "🟢", "taken": "🟡", "closed": "🔴"}
    
    text = f"""
<b>📋 Тикет #{ticket['id']}</b>

{status_emoji.get(ticket['status'], '⚪')} <b>Статус:</b> {ticket['status']}
👤 <b>Клиент:</b> {get_user_mention(ticket['user_id'], ticket.get('username'), ticket.get('first_name'))}
🕐 <b>Создан:</b> {ticket['created_at']}
"""
    if ticket.get('taken_by'):
        admin = admins_db.get(str(ticket['taken_by']), {})
        text += f"👨‍💼 <b>Взял в работу:</b> {get_user_mention(ticket['taken_by'], admin.get('username'), admin.get('first_name'))}\n"
    
    if ticket.get('closed_at'):
        text += f"🔒 <b>Закрыт:</b> {ticket['closed_at']}\n"
    
    if ticket.get('category'):
        text += f"📂 <b>Категория:</b> {ticket['category']}\n"
    
    text += f"\n<b>💬 Сообщения:</b>\n"
    for msg in ticket.get("messages", []):
        sender = "👤 Клиент" if msg["from_user"] else "👨‍💼 Администратор"
        text += f"\n{sender} [{msg['time']}]:\n{msg['text']}\n"
        text += "➖➖➖➖➖➖➖➖➖➖\n"
    
    return text


# ==================== Клавиатуры ====================

def main_menu_keyboard():
    """Главное меню пользователя"""
    keyboard = [
        [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
        [InlineKeyboardButton("📞 Вызвать администратора", callback_data="call_admin")],
        [InlineKeyboardButton("🛠 Техподдержка бота", callback_data="tech_support")],
        [InlineKeyboardButton("📢 Telegram канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="feedback")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_menu_keyboard(admin_id: int):
    """Меню администратора"""
    buttons = []
    
    if has_permission(admin_id, "mailing"):
        buttons.append([InlineKeyboardButton("📨 Рассылка", callback_data="admin_mailing")])
    
    if has_permission(admin_id, "tickets"):
        buttons.append([InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")])
    
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(buttons)


def ticket_action_keyboard(ticket_id: int):
    """Клавиатура действий с тикетом"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Взять в работу", callback_data=f"take_ticket_{ticket_id}"),
            InlineKeyboardButton("ℹ️ Инфо", callback_data=f"ticket_info_{ticket_id}")
        ],
        [
            InlineKeyboardButton("🔒 Закрыть", callback_data=f"close_ticket_{ticket_id}"),
            InlineKeyboardButton("💬 Ответить", callback_data=f"reply_ticket_{ticket_id}")
        ]
    ])


def mailing_keyboard():
    """Клавиатура рассылки"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Всем пользователям", callback_data="mail_all")],
        [InlineKeyboardButton("👨‍💼 Только админам", callback_data="mail_admins")],
        [InlineKeyboardButton("🎯 Активным за 7 дней", callback_data="mail_active")],
        [InlineKeyboardButton("🚀 Отправить", callback_data="mail_send")],
        [InlineKeyboardButton("❌ Отмена", callback_data="mail_cancel")]
    ])


def feedback_keyboard():
    """Клавиатура оценки отзыва"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1 ⭐", callback_data="rate_1"),
            InlineKeyboardButton("2 ⭐", callback_data="rate_2"),
            InlineKeyboardButton("3 ⭐", callback_data="rate_3"),
            InlineKeyboardButton("4 ⭐", callback_data="rate_4"),
            InlineKeyboardButton("5 ⭐", callback_data="rate_5")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_feedback")]
    ])


# ==================== Обработчики команд ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Проверка бана
    banned, ban_reason = is_banned(user_id)
    if banned:
        await update.message.reply_text(ban_reason, parse_mode=ParseMode.HTML)
        return
    
    # Сохранение пользователя
    users_db[str(user_id)] = {
        "id": user_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_active": datetime.now().isoformat()
    }
    save_all_data()
    
    welcome_text = f"""
<b>✨ Добро пожаловать в «Сияние неба»!</b>

🌟 <i>Бот поддержки и общения</i>

Здесь вы можете:
• Получить информацию о боте
• Связаться с администратором
• Сообщить о проблеме
• Оставить отзыв

Выберите нужный пункт в меню ниже 👇
"""
    
    # Проверка, является ли пользователь админом
    if str(user_id) in admins_db:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Меню пользователя", callback_data="user_menu")],
            [InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")],
        ])
        await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode=ParseMode.HTML)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Проверка бана
    banned, ban_reason = is_banned(user_id)
    if banned:
        await query.edit_message_text(ban_reason, parse_mode=ParseMode.HTML)
        return
    
    # Обработка различных callback
    if data == "info":
        await query.edit_message_text(
            """
<b>ℹ️ О боте «Сияние неба»</b>

🌌 <b>Версия:</b> 2.0
👑 <b>Создатель:</b> @administrator

<b>Возможности:</b>
✨ Поддержка пользователей
📞 Связь с администрацией
⭐ Система отзывов
🛠 Техническая поддержка
📢 Новости и обновления

<i>Мы всегда рады помочь вам!</i>
""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ]),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "back_to_main":
        await query.edit_message_text(
            "<b>✨ Главное меню «Сияние неба»</b>\n\nВыберите действие:",
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "call_admin":
        await query.edit_message_text(
            "<b>📞 Вызов администратора</b>\n\nВыберите категорию обращения:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Общение", callback_data="category_chat")],
                [InlineKeyboardButton("🆘 Помощь", callback_data="category_help")],
                [InlineKeyboardButton("💰 Сотрудничество", callback_data="category_partner")],
                [InlineKeyboardButton("📋 Другое", callback_data="category_other")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ]),
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("category_"):
        category = data.replace("category_", "")
        category_names = {
            "chat": "💬 Общение",
            "help": "🆘 Помощь",
            "partner": "💰 Сотрудничество",
            "other": "📋 Другое"
        }
        
        # Проверка мута
        muted, mute_reason = is_muted(user_id)
        if muted:
            await query.edit_message_text(
                mute_reason,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
                ]),
                parse_mode=ParseMode.HTML
            )
            return
        
        context.user_data["ticket_category"] = category
        context.user_data["ticket_category_name"] = category_names.get(category, category)
        
        await query.edit_message_text(
            f"<b>📝 Опишите вашу ситуацию</b>\n\nКатегория: {category_names.get(category, category)}\n\n<i>Отправьте сообщение с описанием</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]
            ]),
            parse_mode=ParseMode.HTML
        )
        
        return AWAITING_TICKET_TEXT
    
    elif data == "tech_support":
        context.user_data["ticket_category"] = "tech"
        context.user_data["ticket_category_name"] = "🛠 Техподдержка"
        
        await query.edit_message_text(
            "<b>🛠 Техническая поддержка</b>\n\nОпишите техническую проблему, и мы поможем вам!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]
            ]),
            parse_mode=ParseMode.HTML
        )
        return AWAITING_TICKET_TEXT
    
    elif data == "feedback":
        await query.edit_message_text(
            "<b>⭐ Оставьте отзыв</b>\n\nПожалуйста, напишите ваш отзыв о боте.\n\nОтправьте сообщение:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]
            ]),
            parse_mode=ParseMode.HTML
        )
        return AWAITING_FEEDBACK
    
    elif data == "user_menu":
        await query.edit_message_text(
            "<b>✨ Главное меню «Сияние неба»</b>\n\nВыберите действие:",
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "admin_panel":
        if str(user_id) not in admins_db:
            await query.answer("У вас нет доступа к админ-панели", show_alert=True)
            return
        
        await query.edit_message_text(
            "<b>👑 Админ-панель «Сияние неба»</b>\n\nВыберите действие:",
            reply_markup=admin_menu_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "admin_mailing":
        if not has_permission(user_id, "mailing"):
            await query.answer("У вас нет доступа к рассылке", show_alert=True)
            return
        
        await query.edit_message_text(
            "<b>📨 Создание рассылки</b>\n\nОтправьте текст сообщения для рассылки.\n\n<i>Поддерживается HTML-разметка</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="mail_cancel")]
            ]),
            parse_mode=ParseMode.HTML
        )
        return AWAITING_MAILING_TEXT
    
    elif data == "mail_cancel":
        if "mailing_text" in context.user_data:
            del context.user_data["mailing_text"]
        await query.edit_message_text(
            "<b>❌ Рассылка отменена</b>",
            reply_markup=admin_menu_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("take_ticket_"):
        ticket_id = int(data.replace("take_ticket_", ""))
        ticket = get_ticket_by_id(ticket_id)
        
        if not ticket:
            await query.answer("Тикет не найден", show_alert=True)
            return
        
        if ticket["status"] != "open":
            await query.answer("Клиент уже занят администратором", show_alert=True)
            return
        
        ticket["status"] = "taken"
        ticket["taken_by"] = user_id
        ticket["taken_at"] = datetime.now().isoformat()
        save_all_data()
        
        # Уведомление клиенту
        try:
            await context.bot.send_message(
                ticket["user_id"],
                f"<b>✅ Администратор взял ваш тикет #{ticket_id} в работу</b>\n\nОжидайте ответа.",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        
        await query.edit_message_text(
            f"<b>✅ Тикет #{ticket_id} взят в работу</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Ответить", callback_data=f"reply_ticket_{ticket_id}")],
                [InlineKeyboardButton("🔒 Закрыть", callback_data=f"close_ticket_{ticket_id}")]
            ]),
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("close_ticket_"):
        ticket_id = int(data.replace("close_ticket_", ""))
        ticket = get_ticket_by_id(ticket_id)
        
        if not ticket:
            await query.answer("Тикет не найден", show_alert=True)
            return
        
        ticket["status"] = "closed"
        ticket["closed_at"] = datetime.now().isoformat()
        ticket["closed_by"] = user_id
        save_all_data()
        
        # Уведомление клиенту
        try:
            await context.bot.send_message(
                ticket["user_id"],
                f"<b>🔒 Ваш тикет #{ticket_id} закрыт</b>\n\nСпасибо за обращение в «Сияние неба»!",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        
        await query.edit_message_text(
            f"<b>🔒 Тикет #{ticket_id} закрыт</b>",
            reply_markup=admin_menu_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("reply_ticket_"):
        ticket_id = int(data.replace("reply_ticket_", ""))
        ticket = get_ticket_by_id(ticket_id)
        
        if not ticket:
            await query.answer("Тикет не найден", show_alert=True)
            return
        
        context.user_data["replying_to"] = ticket_id
        
        await query.edit_message_text(
            f"<b>💬 Ответ на тикет #{ticket_id}</b>\n\nОтправьте ваше сообщение:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_reply")]
            ]),
            parse_mode=ParseMode.HTML
        )
        return AWAITING_REPLY
    
    elif data == "cancel_reply":
        if "replying_to" in context.user_data:
            del context.user_data["replying_to"]
        await query.edit_message_text(
            "<b>❌ Ответ отменен</b>",
            reply_markup=admin_menu_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("rate_"):
        rating = int(data.replace("rate_", ""))
        
        feedback_db.append({
            "user_id": user_id,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "rating": rating,
            "text": context.user_data.get("feedback_text", ""),
            "date": datetime.now().isoformat()
        })
        save_all_data()
        
        if FEEDBACK_CHAT_ID:
            stars = "⭐" * rating
            await context.bot.send_message(
                FEEDBACK_CHAT_ID,
                f"<b>📢 Новый отзыв!</b>\n\n"
                f"{stars} ({rating}/5)\n"
                f"👤 {get_user_mention(user_id, update.effective_user.username, update.effective_user.first_name)}\n"
                f"💬 {context.user_data.get('feedback_text', 'Без текста')}",
                parse_mode=ParseMode.HTML
            )
        
        await query.edit_message_text(
            "<b>⭐ Спасибо за ваш отзыв!</b>\n\nМы ценим ваше мнение о «Сиянии неба»",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_main")]
            ]),
            parse_mode=ParseMode.HTML
        )
        
        context.user_data.pop("feedback_text", None)
    
    elif data == "cancel_feedback":
        context.user_data.pop("feedback_text", None)
        await query.edit_message_text(
            "<b>❌ Отзыв отменен</b>",
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )


async def handle_ticket_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста для создания тикета"""
    user = update.effective_user
    user_id = user.id
    text = update.message.text
    
    category = context.user_data.get("ticket_category", "other")
    category_name = context.user_data.get("ticket_category_name", "📋 Другое")
    
    # Проверка мута
    muted, mute_reason = is_muted(user_id)
    if muted:
        await update.message.reply_text(mute_reason, parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    
    # Создание тикета
    global ticket_counter
    ticket_id = ticket_counter
    ticket_counter += 1
    
    ticket = {
        "id": ticket_id,
        "user_id": user_id,
        "username": user.username,
        "first_name": user.first_name,
        "category": category_name,
        "status": "open",
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "messages": [{
            "from_user": True,
            "text": text,
            "time": datetime.now().strftime("%H:%M")
        }]
    }
    tickets_db.append(ticket)
    save_all_data()
    
    # Уведомление пользователю
    await update.message.reply_text(
        f"<b>✅ Ваше обращение #{ticket_id} принято!</b>\n\n"
        f"📂 Категория: {category_name}\n"
        f"🕐 Статус: ожидает ответа администратора\n\n"
        f"<i>Пожалуйста, ожидайте. Администратор скоро ответит вам.</i>",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    # Отправка в чат поддержки
    if SUPPORT_CHAT_ID:
        await context.bot.send_message(
            SUPPORT_CHAT_ID,
            f"<b>🆕 Новое обращение #{ticket_id}</b>\n\n"
            f"📂 <b>Категория:</b> {category_name}\n"
            f"👤 <b>Клиент:</b> {get_user_mention(user_id, user.username, user.first_name)}\n"
            f"💬 <b>Сообщение:</b>\n{text}",
            reply_markup=ticket_action_keyboard(ticket_id),
            parse_mode=ParseMode.HTML
        )
    
    context.user_data.pop("ticket_category", None)
    context.user_data.pop("ticket_category_name", None)
    
    return ConversationHandler.END


async def handle_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста отзыва"""
    text = update.message.text
    context.user_data["feedback_text"] = text
    
    await update.message.reply_text(
        "<b>⭐ Пожалуйста, оцените бота от 1 до 5:</b>",
        reply_markup=feedback_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END


async def handle_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на тикет"""
    user_id = update.effective_user.id
    text = update.message.text
    
    ticket_id = context.user_data.get("replying_to")
    if not ticket_id:
        await update.message.reply_text("❌ Нет активного тикета для ответа")
        return ConversationHandler.END
    
    ticket = get_ticket_by_id(ticket_id)
    if not ticket or ticket["status"] == "closed":
        await update.message.reply_text("❌ Тикет не найден или закрыт")
        del context.user_data["replying_to"]
        return ConversationHandler.END
    
    # Добавление сообщения в тикет
    ticket["messages"].append({
        "from_user": False,
        "admin_id": user_id,
        "text": text,
        "time": datetime.now().strftime("%H:%M")
    })
    save_all_data()
    
    # Отправка ответа клиенту
    try:
        await context.bot.send_message(
            ticket["user_id"],
            f"<b>💬 Ответ от администратора по тикету #{ticket_id}:</b>\n\n{text}",
            parse_mode=ParseMode.HTML
        )
        await update.message.reply_text("✅ Ответ отправлен клиенту")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось отправить ответ: {e}")
    
    del context.user_data["replying_to"]
    return ConversationHandler.END


async def handle_mailing_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста для рассылки"""
    text = update.message.text
    context.user_data["mailing_text"] = text
    
    await update.message.reply_text(
        "<b>📨 Текст рассылки сохранен</b>\n\nВыберите получателей:",
        reply_markup=mailing_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END


# ==================== Админ-команды ====================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление администраторами"""
    user_id = update.effective_user.id
    
    if str(user_id) not in admins_db:
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    args = context.args
    
    if not args:
        text = "<b>👑 Список администраторов:</b>\n\n"
        for aid, data in admins_db.items():
            text += f"• {get_user_mention(int(aid), data.get('username'), data.get('first_name'))}\n"
            text += f"  Права: {', '.join(data.get('permissions', []))}\n\n"
        
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return
    
    subcommand = args[0].lower()
    
    if subcommand == "add" and len(args) >= 2:
        username = args[1].replace("@", "")
        try:
            # Поиск пользователя (упрощенно)
            target_id = None
            for uid, data in users_db.items():
                if data.get("username") == username:
                    target_id = int(uid)
                    break
            
            if not target_id:
                await update.message.reply_text("❌ Пользователь не найден в базе. Пусть сначала напишет /start")
                return
            
            if str(target_id) in admins_db:
                await update.message.reply_text("❌ Этот пользователь уже администратор")
                return
            
            admins_db[str(target_id)] = {
                "id": target_id,
                "username": username,
                "first_name": users_db[str(target_id)].get("first_name", ""),
                "permissions": ["tickets"],
                "added_by": user_id,
                "added_at": datetime.now().isoformat()
            }
            save_all_data()
            
            await update.message.reply_text(
                f"✅ @{username} назначен администратором",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    
    elif subcommand == "del" and len(args) >= 2:
        username = args[1].replace("@", "")
        
        target_id = None
        for aid, data in admins_db.items():
            if data.get("username") == username:
                target_id = aid
                break
        
        if not target_id:
            await update.message.reply_text("❌ Этот пользователь не администратор")
            return
        
        del admins_db[target_id]
        save_all_data()
        
        await update.message.reply_text(
            f"✅ @{username} удален из администраторов",
            parse_mode=ParseMode.HTML
        )
    
    else:
        await update.message.reply_text(
            "<b>📋 Использование:</b>\n"
            "/admin - список админов\n"
            "/admin add @username - добавить админа\n"
            "/admin del @username - удалить админа",
            parse_mode=ParseMode.HTML
        )


async def sysban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Системный бан пользователя"""
    user_id = update.effective_user.id
    
    if str(user_id) not in admins_db or not has_permission(user_id, "sysban"):
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    if not context.args:
        await update.message.reply_text(
            "<b>📋 Использование:</b>\n"
            "/sysban @username - полный бан\n"
            "/sysban @username 1d причина",
            parse_mode=ParseMode.HTML
        )
        return
    
    username = context.args[0].replace("@", "")
    
    target_id = None
    for uid, data in users_db.items():
        if data.get("username") == username:
            target_id = uid
            break
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    permanent = len(context.args) < 2
    
    if permanent:
        bans_db[target_id] = {
            "user_id": int(target_id),
            "username": username,
            "permanent": True,
            "banned_by": user_id,
            "banned_at": datetime.now().isoformat(),
            "reason": " ".join(context.args[1:]) if len(context.args) > 1 else "Не указана"
        }
        await update.message.reply_text(f"⛔ @{username} забанен навсегда", parse_mode=ParseMode.HTML)
    else:
        duration = parse_duration(context.args[1])
        if not duration:
            await update.message.reply_text("❌ Неверный формат времени")
            return
        
        until = datetime.now() + duration
        bans_db[target_id] = {
            "user_id": int(target_id),
            "username": username,
            "permanent": False,
            "until": until.isoformat(),
            "banned_by": user_id,
            "banned_at": datetime.now().isoformat(),
            "reason": " ".join(context.args[2:]) if len(context.args) > 2 else "Не указана"
        }
        await update.message.reply_text(
            f"⛔ @{username} забанен до {until.strftime('%d.%m.%Y %H:%M')}",
            parse_mode=ParseMode.HTML
        )
    
    save_all_data()


async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мут пользователя"""
    user_id = update.effective_user.id
    
    if str(user_id) not in admins_db or not has_permission(user_id, "mute"):
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "<b>📋 Использование:</b>\n"
            "/mute @username 1d причина",
            parse_mode=ParseMode.HTML
        )
        return
    
    username = context.args[0].replace("@", "")
    
    target_id = None
    for uid, data in users_db.items():
        if data.get("username") == username:
            target_id = uid
            break
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    duration = parse_duration(context.args[1])
    if not duration:
        await update.message.reply_text("❌ Неверный формат времени")
        return
    
    until = datetime.now() + duration
    
    mutes_db[target_id] = {
        "user_id": int(target_id),
        "username": username,
        "until": until.isoformat(),
        "muted_by": user_id,
        "muted_at": datetime.now().isoformat(),
        "reason": " ".join(context.args[2:]) if len(context.args) > 2 else "Не указана"
    }
    save_all_data()
    
    await update.message.reply_text(
        f"🔇 @{username} в муте до {until.strftime('%d.%m.%Y %H:%M')}",
        parse_mode=ParseMode.HTML
    )


async def level_up_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повышение уровня в чате"""
    if not ROLE_CHAT_ID:
        await update.message.reply_text("❌ Чат для ролей не настроен")
        return
    
    if not context.args:
        await update.message.reply_text("<b>📋 Использование:</b> /level_up @username", parse_mode=ParseMode.HTML)
        return
    
    username = context.args[0].replace("@", "")
    
    target_id = None
    target_first = username
    for uid, data in users_db.items():
        if data.get("username") == username:
            target_id = uid
            target_first = data.get("first_name", username)
            break
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    current_level = roles_db.get(str(target_id), {}).get("level", 0)
    new_level = current_level + 1
    
    roles_db[str(target_id)] = {
        "user_id": int(target_id),
        "username": username,
        "first_name": target_first,
        "level": new_level,
        "updated_at": datetime.now().isoformat()
    }
    save_all_data()
    
    try:
        await context.bot.send_message(
            ROLE_CHAT_ID,
            f"""
<b>✨ <i>~ Сияние неба ~</i> ✨</b>

<b>🌟 ПОВЫШЕНИЕ УРОВНЯ! 🌟</b>

Поздравляем, @{username}!

Ваш новый уровень: <b>{new_level} ⭐</b>

<i>Продолжайте сиять вместе с нами!</i>
""",
            parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(f"✅ Уровень @{username} повышен до {new_level}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def level_down_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Понижение уровня в чате"""
    if not ROLE_CHAT_ID:
        await update.message.reply_text("❌ Чат для ролей не настроен")
        return
    
    if not context.args:
        await update.message.reply_text("<b>📋 Использование:</b> /level_down @username", parse_mode=ParseMode.HTML)
        return
    
    username = context.args[0].replace("@", "")
    
    target_id = None
    target_first = username
    for uid, data in users_db.items():
        if data.get("username") == username:
            target_id = uid
            target_first = data.get("first_name", username)
            break
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    current_level = roles_db.get(str(target_id), {}).get("level", 0)
    new_level = max(0, current_level - 1)
    
    roles_db[str(target_id)] = {
        "user_id": int(target_id),
        "username": username,
        "first_name": target_first,
        "level": new_level,
        "updated_at": datetime.now().isoformat()
    }
    save_all_data()
    
    try:
        await context.bot.send_message(
            ROLE_CHAT_ID,
            f"""
<b>✨ <i>~ Сияние неба ~</i> ✨</b>

<b>💫 ИЗМЕНЕНИЕ УРОВНЯ 💫</b>

@{username}, ваш уровень изменен.

Текущий уровень: <b>{new_level} ⭐</b>

<i>Не угасайте! Впереди новые возможности!</i>
""",
            parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(f"✅ Уровень @{username} понижен до {new_level}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


# ==================== Запуск бота ====================

def main():
    """Главная функция запуска"""
    print("🌟 Запуск бота «Сияние неба»...")
    
    # Загрузка данных
    load_all_data()
    print(f"📊 Загружено пользователей: {len(users_db)}")
    print(f"👑 Загружено администраторов: {len(admins_db)}")
    print(f"📋 Загружено тикетов: {len(tickets_db)}")
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler для создания тикета/отзыва/ответа/рассылки
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_callback, pattern="^(category_|tech_support|feedback|admin_mailing|reply_ticket_)"),
        ],
        states={
            AWAITING_TICKET_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ticket_text),
                CallbackQueryHandler(button_callback, pattern="^back_to_main$"),
            ],
            AWAITING_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_text),
                CallbackQueryHandler(button_callback, pattern="^back_to_main|cancel_feedback$"),
            ],
            AWAITING_REPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply_text),
                CallbackQueryHandler(button_callback, pattern="^cancel_reply$"),
            ],
            AWAITING_MAILING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mailing_text),
                CallbackQueryHandler(button_callback, pattern="^mail_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(button_callback, pattern="^back_to_main$"),
        ],
    )
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("sysban", sysban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("level_up", level_up_command))
    application.add_handler(CommandHandler("level_down", level_down_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запуск бота
    print("✅ Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
