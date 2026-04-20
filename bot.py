#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бот поддержки «Сияние неба»
Версия: 1.0
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ChatPermissions
)
from pyrogram.enums import ParseMode, ChatMemberStatus
from pyrogram.errors import UserNotParticipant, UserBannedInChannel, PeerIdInvalid
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_CHAT_ID = int(os.getenv("SUPPORT_CHAT_ID", 0))
FEEDBACK_CHAT_ID = int(os.getenv("FEEDBACK_CHAT_ID", 0))
ROLE_CHAT_ID = int(os.getenv("ROLE_CHAT_ID", 0))
CHANNEL_ID = os.getenv("CHANNEL_ID")
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

# Временные состояния для рассылки
mailing_states = {}

# Инициализация клиента
app = Client(
    "siyanie_neba_bot",
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)


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
    
    # Бан истек
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
    
    # Мут истек
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


def format_ticket_info(ticket: Dict) -> str:
    """Форматирование информации о тикете"""
    status_emoji = {
        "open": "🟢",
        "taken": "🟡",
        "closed": "🔴"
    }
    
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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
        [InlineKeyboardButton("📞 Вызвать администратора", callback_data="call_admin")],
        [InlineKeyboardButton("🛠 Техподдержка бота", callback_data="tech_support")],
        [InlineKeyboardButton("📢 Telegram канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="feedback")]
    ])
    return keyboard


def admin_menu_keyboard(admin_id: int):
    """Меню администратора"""
    buttons = []
    
    if has_permission(admin_id, "mailing"):
        buttons.append([InlineKeyboardButton("📨 Рассылка", callback_data="admin_mailing")])
    
    if has_permission(admin_id, "tickets"):
        buttons.append([InlineKeyboardButton("📊 Статистика тикетов", callback_data="admin_stats")])
    
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(buttons)


def admin_permissions_keyboard(admin_id: int, target_id: int):
    """Клавиатура настройки прав администратора"""
    target_admin = admins_db.get(str(target_id), {})
    current_perms = target_admin.get("permissions", [])
    
    all_permissions = ["mailing", "tickets", "ban", "mute", "getadmin", "infoticket", "sysban"]
    
    buttons = []
    for perm in all_permissions:
        status = "✅" if perm in current_perms else "❌"
        buttons.append([InlineKeyboardButton(
            f"{status} {perm}", 
            callback_data=f"toggle_perm_{target_id}_{perm}"
        )])
    
    buttons.append([InlineKeyboardButton("💾 Сохранить", callback_data=f"save_perms_{target_id}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=f"admin_back")])
    
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
        [InlineKeyboardButton("📝 Предпросмотр", callback_data="mail_preview")],
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

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Проверка бана
    banned, ban_reason = is_banned(user_id)
    if banned:
        await message.reply(ban_reason)
        return
    
    # Сохранение пользователя
    users_db[str(user_id)] = {
        "id": user_id,
        "username": username,
        "first_name": first_name,
        "last_active": datetime.now().isoformat()
    }
    save_all_data()
    
    # Приветственное сообщение
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
        await message.reply(welcome_text, reply_markup=keyboard)
    else:
        await message.reply(welcome_text, reply_markup=main_menu_keyboard())


@app.on_callback_query()
async def handle_callback(client: Client, callback: CallbackQuery):
    """Обработчик всех callback-запросов"""
    user_id = callback.from_user.id
    data = callback.data
    
    # Проверка бана
    banned, ban_reason = is_banned(user_id)
    if banned:
        await callback.answer(ban_reason, show_alert=True)
        return
    
    # Обработка различных callback
    if data == "info":
        await callback.message.edit_text(
            """
<b>ℹ️ О боте «Сияние неба»</b>

🌌 <b>Версия:</b> 1.0
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
            ])
        )
        await callback.answer()
    
    elif data == "back_to_main":
        await callback.message.edit_text(
            "<b>✨ Главное меню «Сияние неба»</b>\n\nВыберите действие:",
            reply_markup=main_menu_keyboard()
        )
        await callback.answer()
    
    elif data == "call_admin":
        await callback.message.edit_text(
            "<b>📞 Вызов администратора</b>\n\nВыберите категорию обращения:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Общение", callback_data="category_chat")],
                [InlineKeyboardButton("🆘 Помощь", callback_data="category_help")],
                [InlineKeyboardButton("💰 Сотрудничество", callback_data="category_partner")],
                [InlineKeyboardButton("📋 Другое", callback_data="category_other")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
    
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
            await callback.answer(mute_reason, show_alert=True)
            await callback.message.edit_text(
                mute_reason,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
                ])
            )
            return
        
        await callback.message.edit_text(
            f"<b>📝 Опишите вашу ситуацию</b>\n\nКатегория: {category_names.get(category, category)}\n\n<i>Отправьте сообщение с описанием</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]
            ])
        )
        
        # Сохраняем состояние ожидания
        users_db[str(user_id)]["awaiting_ticket"] = category
        save_all_data()
        await callback.answer()
    
    elif data == "tech_support":
        await callback.message.edit_text(
            "<b>🛠 Техническая поддержка</b>\n\nОпишите техническую проблему, и мы поможем вам!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ])
        )
        users_db[str(user_id)]["awaiting_ticket"] = "tech"
        save_all_data()
        await callback.answer()
    
    elif data == "feedback":
        await callback.message.edit_text(
            "<b>⭐ Оставьте отзыв</b>\n\nПожалуйста, оцените работу бота и оставьте комментарий.\n\nОтправьте ваш отзыв одним сообщением:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]
            ])
        )
        users_db[str(user_id)]["awaiting_feedback"] = True
        save_all_data()
        await callback.answer()
    
    elif data == "user_menu":
        await callback.message.edit_text(
            "<b>✨ Главное меню «Сияние неба»</b>\n\nВыберите действие:",
            reply_markup=main_menu_keyboard()
        )
        await callback.answer()
    
    elif data == "admin_panel":
        if str(user_id) not in admins_db:
            await callback.answer("У вас нет доступа к админ-панели", show_alert=True)
            return
        
        await callback.message.edit_text(
            "<b>👑 Админ-панель «Сияние неба»</b>\n\nВыберите действие:",
            reply_markup=admin_menu_keyboard(user_id)
        )
        await callback.answer()
    
    elif data == "admin_mailing":
        if not has_permission(user_id, "mailing"):
            await callback.answer("У вас нет доступа к рассылке", show_alert=True)
            return
        
        mailing_states[user_id] = {"step": "waiting_text", "target": None, "text": None}
        
        await callback.message.edit_text(
            "<b>📨 Создание рассылки</b>\n\nОтправьте текст сообщения для рассылки.\n\n<i>Поддерживается HTML-разметка</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="mail_cancel")]
            ])
        )
        await callback.answer()
    
    elif data == "mail_cancel":
        if user_id in mailing_states:
            del mailing_states[user_id]
        await callback.message.edit_text(
            "<b>❌ Рассылка отменена</b>",
            reply_markup=admin_menu_keyboard(user_id)
        )
        await callback.answer()
    
    elif data.startswith("mail_"):
        if user_id not in mailing_states or not mailing_states[user_id].get("text"):
            await callback.answer("Сначала отправьте текст рассылки", show_alert=True)
            return
        
        if data == "mail_all":
            mailing_states[user_id]["target"] = "all"
            await callback.answer("Выбрано: всем пользователям")
        elif data == "mail_admins":
            mailing_states[user_id]["target"] = "admins"
            await callback.answer("Выбрано: только админам")
        elif data == "mail_active":
            mailing_states[user_id]["target"] = "active"
            await callback.answer("Выбрано: активным за 7 дней")
        elif data == "mail_preview":
            text = mailing_states[user_id]["text"]
            await callback.message.edit_text(
                f"<b>📝 Предпросмотр:</b>\n\n{text}",
                reply_markup=mailing_keyboard()
            )
            await callback.answer()
        elif data == "mail_send":
            state = mailing_states[user_id]
            text = state["text"]
            target = state.get("target")
            
            if not target:
                await callback.answer("Выберите получателей!", show_alert=True)
                return
            
            # Отправка рассылки
            sent_count = 0
            fail_count = 0
            
            status_msg = await callback.message.edit_text("<b>📨 Отправка рассылки...</b>")
            
            recipients = []
            if target == "all":
                recipients = list(users_db.keys())
            elif target == "admins":
                recipients = list(admins_db.keys())
            elif target == "active":
                week_ago = datetime.now() - timedelta(days=7)
                for uid, data in users_db.items():
                    last_active = datetime.fromisoformat(data.get("last_active", "2000-01-01T00:00:00"))
                    if last_active > week_ago:
                        recipients.append(uid)
            
            for uid in recipients:
                try:
                    await client.send_message(int(uid), text)
                    sent_count += 1
                    await asyncio.sleep(0.05)  # Защита от флуда
                except:
                    fail_count += 1
            
            await status_msg.edit_text(
                f"<b>✅ Рассылка завершена!</b>\n\n"
                f"📊 Отправлено: {sent_count}\n"
                f"❌ Ошибок: {fail_count}",
                reply_markup=admin_menu_keyboard(user_id)
            )
            del mailing_states[user_id]
    
    elif data.startswith("take_ticket_"):
        ticket_id = int(data.replace("take_ticket_", ""))
        ticket = get_ticket_by_id(ticket_id)
        
        if not ticket:
            await callback.answer("Тикет не найден", show_alert=True)
            return
        
        if ticket["status"] != "open":
            await callback.answer(f"Клиент уже занят администратором", show_alert=True)
            return
        
        ticket["status"] = "taken"
        ticket["taken_by"] = user_id
        ticket["taken_at"] = datetime.now().isoformat()
        save_all_data()
        
        # Уведомление клиенту
        try:
            await client.send_message(
                ticket["user_id"],
                f"<b>✅ Администратор взял ваш тикет #{ticket_id} в работу</b>\n\nОжидайте ответа."
            )
        except:
            pass
        
        await callback.message.edit_text(
            f"<b>✅ Тикет #{ticket_id} взят в работу</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Ответить", callback_data=f"reply_ticket_{ticket_id}")],
                [InlineKeyboardButton("🔒 Закрыть", callback_data=f"close_ticket_{ticket_id}")]
            ])
        )
        await callback.answer("Тикет взят в работу")
    
    elif data.startswith("ticket_info_"):
        ticket_id = int(data.replace("ticket_info_", ""))
        ticket = get_ticket_by_id(ticket_id)
        
        if not ticket:
            await callback.answer("Тикет не найден", show_alert=True)
            return
        
        await callback.message.edit_text(
            format_ticket_info(ticket),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
            ])
        )
        await callback.answer()
    
    elif data.startswith("close_ticket_"):
        ticket_id = int(data.replace("close_ticket_", ""))
        ticket = get_ticket_by_id(ticket_id)
        
        if not ticket:
            await callback.answer("Тикет не найден", show_alert=True)
            return
        
        ticket["status"] = "closed"
        ticket["closed_at"] = datetime.now().isoformat()
        ticket["closed_by"] = user_id
        save_all_data()
        
        # Уведомление клиенту
        try:
            await client.send_message(
                ticket["user_id"],
                f"<b>🔒 Ваш тикет #{ticket_id} закрыт</b>\n\nСпасибо за обращение в «Сияние неба»!"
            )
        except:
            pass
        
        await callback.message.edit_text(
            f"<b>🔒 Тикет #{ticket_id} закрыт</b>",
            reply_markup=admin_menu_keyboard(user_id)
        )
        await callback.answer("Тикет закрыт")
    
    elif data.startswith("reply_ticket_"):
        ticket_id = int(data.replace("reply_ticket_", ""))
        ticket = get_ticket_by_id(ticket_id)
        
        if not ticket:
            await callback.answer("Тикет не найден", show_alert=True)
            return
        
        users_db[str(user_id)]["replying_to"] = ticket_id
        save_all_data()
        
        await callback.message.edit_text(
            f"<b>💬 Ответ на тикет #{ticket_id}</b>\n\nОтправьте ваше сообщение:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_reply")]
            ])
        )
        await callback.answer()
    
    elif data == "cancel_reply":
        if "replying_to" in users_db.get(str(user_id), {}):
            del users_db[str(user_id)]["replying_to"]
            save_all_data()
        await callback.message.edit_text(
            "<b>❌ Ответ отменен</b>",
            reply_markup=admin_menu_keyboard(user_id)
        )
        await callback.answer()
    
    elif data.startswith("rate_"):
        rating = int(data.replace("rate_", ""))
        user_id = callback.from_user.id
        
        feedback_db.append({
            "user_id": user_id,
            "username": callback.from_user.username,
            "first_name": callback.from_user.first_name,
            "rating": rating,
            "text": users_db.get(str(user_id), {}).get("feedback_text", ""),
            "date": datetime.now().isoformat()
        })
        save_all_data()
        
        # Отправка в чат отзывов
        if FEEDBACK_CHAT_ID:
            stars = "⭐" * rating
            await client.send_message(
                FEEDBACK_CHAT_ID,
                f"<b>📢 Новый отзыв!</b>\n\n"
                f"{stars} ({rating}/5)\n"
                f"👤 {get_user_mention(user_id, callback.from_user.username, callback.from_user.first_name)}\n"
                f"💬 {users_db.get(str(user_id), {}).get('feedback_text', 'Без текста')}"
            )
        
        await callback.message.edit_text(
            "<b>⭐ Спасибо за ваш отзыв!</b>\n\nМы ценим ваше мнение о «Сиянии неба»",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
    
    elif data == "cancel_feedback":
        if str(user_id) in users_db:
            users_db[str(user_id)].pop("awaiting_feedback", None)
            users_db[str(user_id)].pop("feedback_text", None)
            save_all_data()
        await callback.message.edit_text(
            "<b>❌ Отзыв отменен</b>",
            reply_markup=main_menu_keyboard()
        )
        await callback.answer()


@app.on_message(filters.text & filters.private)
async def handle_message(client: Client, message: Message):
    """Обработчик текстовых сообщений"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    text = message.text
    
    # Обновление времени активности
    if str(user_id) in users_db:
        users_db[str(user_id)]["last_active"] = datetime.now().isoformat()
        save_all_data()
    
    # Проверка бана
    banned, ban_reason = is_banned(user_id)
    if banned:
        await message.reply(ban_reason)
        return
    
    user_data = users_db.get(str(user_id), {})
    
    # Обработка ожидания создания тикета
    if "awaiting_ticket" in user_data:
        category = user_data["awaiting_ticket"]
        del users_db[str(user_id)]["awaiting_ticket"]
        
        # Проверка мута
        muted, mute_reason = is_muted(user_id)
        if muted:
            await message.reply(mute_reason)
            return
        
        # Создание тикета
        global ticket_counter
        ticket_id = ticket_counter
        ticket_counter += 1
        
        category_names = {
            "chat": "💬 Общение",
            "help": "🆘 Помощь",
            "partner": "💰 Сотрудничество",
            "other": "📋 Другое",
            "tech": "🛠 Техподдержка"
        }
        
        ticket = {
            "id": ticket_id,
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "category": category_names.get(category, category),
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
        await message.reply(
            f"<b>✅ Ваше обращение #{ticket_id} принято!</b>\n\n"
            f"📂 Категория: {category_names.get(category, category)}\n"
            f"🕐 Статус: ожидает ответа администратора\n\n"
            f"<i>Пожалуйста, ожидайте. Администратор скоро ответит вам.</i>",
            reply_markup=main_menu_keyboard()
        )
        
        # Отправка в чат поддержки
        if SUPPORT_CHAT_ID:
            await client.send_message(
                SUPPORT_CHAT_ID,
                f"<b>🆕 Новое обращение #{ticket_id}</b>\n\n"
                f"📂 <b>Категория:</b> {category_names.get(category, category)}\n"
                f"👤 <b>Клиент:</b> {get_user_mention(user_id, username, first_name)}\n"
                f"💬 <b>Сообщение:</b>\n{text}",
                reply_markup=ticket_action_keyboard(ticket_id)
            )
        
        return
    
    # Обработка ожидания отзыва
    if user_data.get("awaiting_feedback"):
        users_db[str(user_id)]["feedback_text"] = text
        users_db[str(user_id)]["awaiting_feedback"] = False
        save_all_data()
        
        await message.reply(
            "<b>⭐ Пожалуйста, оцените бота от 1 до 5:</b>",
            reply_markup=feedback_keyboard()
        )
        return
    
    # Обработка ответа на тикет (для админов)
    if "replying_to" in user_data:
        ticket_id = user_data["replying_to"]
        ticket = get_ticket_by_id(ticket_id)
        
        if not ticket or ticket["status"] == "closed":
            await message.reply("❌ Тикет не найден или закрыт")
            del users_db[str(user_id)]["replying_to"]
            save_all_data()
            return
        
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
            await client.send_message(
                ticket["user_id"],
                f"<b>💬 Ответ от администратора по тикету #{ticket_id}:</b>\n\n{text}"
            )
            await message.reply(f"✅ Ответ отправлен клиенту")
        except Exception as e:
            await message.reply(f"❌ Не удалось отправить ответ: {e}")
        
        del users_db[str(user_id)]["replying_to"]
        save_all_data()
        return
    
    # Обработка текста для рассылки
    if user_id in mailing_states and mailing_states[user_id].get("step") == "waiting_text":
        mailing_states[user_id]["text"] = text
        mailing_states[user_id]["step"] = "choose_target"
        
        await message.reply(
            "<b>📨 Текст рассылки сохранен</b>\n\nВыберите получателей:",
            reply_markup=mailing_keyboard()
        )
        return
    
    # Обычное сообщение - показываем меню
    await message.reply(
        "<b>✨ Главное меню «Сияние неба»</b>\n\nВыберите действие:",
        reply_markup=main_menu_keyboard()
    )


# ==================== Админ-команды ====================

@app.on_message(filters.command("admin"))
async def admin_command(client: Client, message: Message):
    """Управление администраторами"""
    user_id = message.from_user.id
    
    if str(user_id) not in admins_db:
        await message.reply("❌ У вас нет доступа к этой команде")
        return
    
    if not has_permission(user_id, "admin"):
        await message.reply("❌ У вас нет прав на управление админами")
        return
    
    args = message.text.split()
    
    if len(args) == 1:
        # Показать список админов
        text = "<b>👑 Список администраторов:</b>\n\n"
        for aid, data in admins_db.items():
            text += f"• {get_user_mention(int(aid), data.get('username'), data.get('first_name'))}\n"
            text += f"  Права: {', '.join(data.get('permissions', []))}\n\n"
        
        await message.reply(text)
    
    elif len(args) >= 2:
        subcommand = args[1].lower()
        
        # Получение целевого пользователя
        target = None
        if message.reply_to_message:
            target = message.reply_to_message.from_user
        elif len(args) >= 3:
            username = args[2].replace("@", "")
            try:
                target = await client.get_users(username)
            except:
                await message.reply("❌ Пользователь не найден")
                return
        
        if not target:
            await message.reply("❌ Укажите пользователя (ответом или @username)")
            return
        
        if subcommand == "add":
            if str(target.id) in admins_db:
                await message.reply("❌ Этот пользователь уже администратор")
                return
            
            admins_db[str(target.id)] = {
                "id": target.id,
                "username": target.username,
                "first_name": target.first_name,
                "permissions": ["tickets"],
                "added_by": user_id,
                "added_at": datetime.now().isoformat()
            }
            save_all_data()
            
            await message.reply(
                f"✅ {get_user_mention(target.id, target.username, target.first_name)} назначен администратором"
            )
        
        elif subcommand == "del":
            if str(target.id) not in admins_db:
                await message.reply("❌ Этот пользователь не администратор")
                return
            
            del admins_db[str(target.id)]
            save_all_data()
            
            await message.reply(
                f"✅ {get_user_mention(target.id, target.username, target.first_name)} удален из администраторов"
            )
        
        elif subcommand == "" or len(args) == 2:
            # Настройка прав
            if str(target.id) not in admins_db:
                await message.reply("❌ Этот пользователь не администратор")
                return
            
            await message.reply(
                f"<b>⚙️ Настройка прав для {get_user_mention(target.id, target.username, target.first_name)}</b>",
                reply_markup=admin_permissions_keyboard(user_id, target.id)
            )
        
        else:
            await message.reply(
                "<b>📋 Использование:</b>\n"
                "/admin - список админов\n"
                "/admin add @username - добавить админа\n"
                "/admin del @username - удалить админа\n"
                "/admin @username - настроить права"
            )


@app.on_callback_query(filters.regex(r"^toggle_perm_"))
async def toggle_permission(client: Client, callback: CallbackQuery):
    """Переключение права администратора"""
    user_id = callback.from_user.id
    data = callback.data
    
    parts = data.split("_")
    target_id = int(parts[2])
    perm = "_".join(parts[3:])
    
    if str(target_id) not in admins_db:
        await callback.answer("Администратор не найден", show_alert=True)
        return
    
    target_admin = admins_db[str(target_id)]
    current_perms = target_admin.get("permissions", [])
    
    if perm in current_perms:
        current_perms.remove(perm)
    else:
        current_perms.append(perm)
    
    target_admin["permissions"] = current_perms
    save_all_data()
    
    await callback.message.edit_reply_markup(
        reply_markup=admin_permissions_keyboard(user_id, target_id)
    )
    await callback.answer(f"Право '{perm}' {'удалено' if perm not in current_perms else 'добавлено'}")


@app.on_callback_query(filters.regex(r"^save_perms_"))
async def save_permissions(client: Client, callback: CallbackQuery):
    """Сохранение прав администратора"""
    user_id = callback.from_user.id
    target_id = int(callback.data.replace("save_perms_", ""))
    
    await callback.message.edit_text(
        f"<b>✅ Права администратора сохранены</b>",
        reply_markup=admin_menu_keyboard(user_id)
    )
    await callback.answer("Права сохранены")


@app.on_message(filters.command("sysban"))
async def sysban_command(client: Client, message: Message):
    """Системный бан пользователя"""
    user_id = message.from_user.id
    
    if str(user_id) not in admins_db or not has_permission(user_id, "sysban"):
        await message.reply("❌ У вас нет доступа к этой команде")
        return
    
    args = message.text.split()
    
    # Получение целевого пользователя
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(args) >= 2:
        username = args[1].replace("@", "")
        try:
            target = await client.get_users(username)
        except:
            await message.reply("❌ Пользователь не найден")
            return
    
    if not target:
        await message.reply(
            "<b>📋 Использование:</b>\n"
            "/sysban @username - полный бан\n"
            "/sysban @username 1d причина - бан на время\n"
            "/sysban @username 12h причина\n"
            "/sysban @username 30m причина"
        )
        return
    
    if target.id == user_id:
        await message.reply("❌ Нельзя забанить самого себя")
        return
    
    # Определение типа бана
    permanent = len(args) < 3
    
    if permanent:
        bans_db[str(target.id)] = {
            "user_id": target.id,
            "username": target.username,
            "first_name": target.first_name,
            "permanent": True,
            "banned_by": user_id,
            "banned_at": datetime.now().isoformat(),
            "reason": " ".join(args[2:]) if len(args) > 2 else "Не указана"
        }
        
        await message.reply(
            f"<b>⛔ Полный бан</b>\n\n"
            f"👤 {get_user_mention(target.id, target.username, target.first_name)}\n"
            f"📋 Причина: {bans_db[str(target.id)]['reason']}\n"
            f"⏱ Срок: навсегда"
        )
    else:
        # Парсинг времени
        time_str = args[2]
        duration = parse_duration(time_str)
        
        if not duration:
            await message.reply("❌ Неверный формат времени. Примеры: 1d, 12h, 30m")
            return
        
        until = datetime.now() + duration
        
        bans_db[str(target.id)] = {
            "user_id": target.id,
            "username": target.username,
            "first_name": target.first_name,
            "permanent": False,
            "until": until.isoformat(),
            "banned_by": user_id,
            "banned_at": datetime.now().isoformat(),
            "reason": " ".join(args[3:]) if len(args) > 3 else "Не указана"
        }
        
        await message.reply(
            f"<b>⛔ Бан пользователя</b>\n\n"
            f"👤 {get_user_mention(target.id, target.username, target.first_name)}\n"
            f"📋 Причина: {bans_db[str(target.id)]['reason']}\n"
            f"⏱ Срок: до {until.strftime('%d.%m.%Y %H:%M')}"
        )
    
    save_all_data()


@app.on_message(filters.command("mute"))
async def mute_command(client: Client, message: Message):
    """Мут пользователя"""
    user_id = message.from_user.id
    
    if str(user_id) not in admins_db or not has_permission(user_id, "mute"):
        await message.reply("❌ У вас нет доступа к этой команде")
        return
    
    args = message.text.split()
    
    # Получение целевого пользователя
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(args) >= 2:
        username = args[1].replace("@", "")
        try:
            target = await client.get_users(username)
        except:
            await message.reply("❌ Пользователь не найден")
            return
    
    if not target or len(args) < 3:
        await message.reply(
            "<b>📋 Использование:</b>\n"
            "/mute @username 1d причина\n"
            "/mute @username 12h причина\n"
            "/mute @username 30m причина"
        )
        return
    
    if target.id == user_id:
        await message.reply("❌ Нельзя замутить самого себя")
        return
    
    # Парсинг времени
    time_str = args[2]
    duration = parse_duration(time_str)
    
    if not duration:
        await message.reply("❌ Неверный формат времени. Примеры: 1d, 12h, 30m")
        return
    
    until = datetime.now() + duration
    
    mutes_db[str(target.id)] = {
        "user_id": target.id,
        "username": target.username,
        "first_name": target.first_name,
        "until": until.isoformat(),
        "muted_by": user_id,
        "muted_at": datetime.now().isoformat(),
        "reason": " ".join(args[3:]) if len(args) > 3 else "Не указана"
    }
    save_all_data()
    
    await message.reply(
        f"<b>🔇 Мут пользователя</b>\n\n"
        f"👤 {get_user_mention(target.id, target.username, target.first_name)}\n"
        f"📋 Причина: {mutes_db[str(target.id)]['reason']}\n"
        f"⏱ Срок: до {until.strftime('%d.%m.%Y %H:%M')}"
    )


@app.on_message(filters.command("sysunban"))
async def sysunban_command(client: Client, message: Message):
    """Разбан пользователя"""
    user_id = message.from_user.id
    
    if str(user_id) not in admins_db or not has_permission(user_id, "sysban"):
        await message.reply("❌ У вас нет доступа к этой команде")
        return
    
    args = message.text.split()
    
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(args) >= 2:
        username = args[1].replace("@", "")
        try:
            target = await client.get_users(username)
        except:
            await message.reply("❌ Пользователь не найден")
            return
    
    if not target:
        await message.reply("<b>📋 Использование:</b> /sysunban @username")
        return
    
    if str(target.id) in bans_db:
        del bans_db[str(target.id)]
        save_all_data()
        await message.reply(
            f"<b>✅ Разбан пользователя</b>\n\n"
            f"👤 {get_user_mention(target.id, target.username, target.first_name)}"
        )
    else:
        await message.reply("❌ Пользователь не забанен")


@app.on_message(filters.command("unmute"))
async def unmute_command(client: Client, message: Message):
    """Размут пользователя"""
    user_id = message.from_user.id
    
    if str(user_id) not in admins_db or not has_permission(user_id, "mute"):
        await message.reply("❌ У вас нет доступа к этой команде")
        return
    
    args = message.text.split()
    
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(args) >= 2:
        username = args[1].replace("@", "")
        try:
            target = await client.get_users(username)
        except:
            await message.reply("❌ Пользователь не найден")
            return
    
    if not target:
        await message.reply("<b>📋 Использование:</b> /unmute @username")
        return
    
    if str(target.id) in mutes_db:
        del mutes_db[str(target.id)]
        save_all_data()
        await message.reply(
            f"<b>✅ Размут пользователя</b>\n\n"
            f"👤 {get_user_mention(target.id, target.username, target.first_name)}"
        )
    else:
        await message.reply("❌ Пользователь не в муте")


@app.on_message(filters.command("getadmin"))
async def getadmin_command(client: Client, message: Message):
    """Получение статистики пользователя"""
    user_id = message.from_user.id
    
    if str(user_id) not in admins_db or not has_permission(user_id, "getadmin"):
        await message.reply("❌ У вас нет доступа к этой команде")
        return
    
    args = message.text.split()
    
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(args) >= 2:
        username = args[1].replace("@", "")
        try:
            target = await client.get_users(username)
        except:
            await message.reply("❌ Пользователь не найден")
            return
    
    if not target:
        await message.reply("<b>📋 Использование:</b> /getadmin @username")
        return
    
    # Подсчет тикетов пользователя за сегодня
    today = datetime.now().date()
    today_tickets = []
    
    for ticket in tickets_db:
        ticket_date = datetime.strptime(ticket["created_at"].split()[0], "%d.%m.%Y").date()
        if ticket["user_id"] == target.id and ticket_date == today:
            today_tickets.append(ticket)
    
    text = f"""
<b>📊 Статистика пользователя</b>

👤 {get_user_mention(target.id, target.username, target.first_name)}
🆔 ID: <code>{target.id}</code>

<b>📈 За сегодня ({today.strftime('%d.%m.%Y')}):</b>
📋 Обращений: {len(today_tickets)}

<b>📋 Список обращений за сегодня:</b>
"""
    for t in today_tickets:
        status_emoji = {"open": "🟢", "taken": "🟡", "closed": "🔴"}.get(t["status"], "⚪")
        text += f"\n{status_emoji} #{t['id']} - {t['created_at']} - {t['category']}"
    
    await message.reply(text)


@app.on_message(filters.command("infoticket"))
async def infoticket_command(client: Client, message: Message):
    """Информация о тикете"""
    user_id = message.from_user.id
    
    if str(user_id) not in admins_db or not has_permission(user_id, "infoticket"):
        await message.reply("❌ У вас нет доступа к этой команде")
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply("<b>📋 Использование:</b> /infoticket номер_тикета")
        return
    
    try:
        ticket_id = int(args[1])
    except:
        await message.reply("❌ Неверный номер тикета")
        return
    
    ticket = get_ticket_by_id(ticket_id)
    
    if not ticket:
        await message.reply("❌ Тикет не найден")
        return
    
    await message.reply(format_ticket_info(ticket))


@app.on_message(filters.command("level_up"))
async def level_up_command(client: Client, message: Message):
    """Повышение уровня в чате"""
    if not ROLE_CHAT_ID:
        await message.reply("❌ Чат для ролей не настроен")
        return
    
    args = message.text.split()
    
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(args) >= 2:
        username = args[1].replace("@", "")
        try:
            target = await client.get_users(username)
        except:
            await message.reply("❌ Пользователь не найден")
            return
    
    if not target:
        await message.reply("<b>📋 Использование:</b> /level_up @username")
        return
    
    # Получение текущей роли и повышение
    current_role = roles_db.get(str(target.id), {}).get("level", 0)
    new_level = current_role + 1
    
    roles_db[str(target.id)] = {
        "user_id": target.id,
        "username": target.username,
        "first_name": target.first_name,
        "level": new_level,
        "updated_at": datetime.now().isoformat()
    }
    save_all_data()
    
    # Отправка сообщения в чат
    try:
        await client.send_message(
            ROLE_CHAT_ID,
            f"""
<b>✨ <i>~ Сияние неба ~</i> ✨</b>

<b>🌟 ПОВЫШЕНИЕ УРОВНЯ! 🌟</b>

Поздравляем, {get_user_mention(target.id, target.username, target.first_name)}!

Ваш новый уровень: <b>{new_level} ⭐</b>

<i>Продолжайте сиять вместе с нами!</i>

#повышение #уровень{new_level}
""",
            parse_mode=ParseMode.HTML
        )
        await message.reply(f"✅ Уровень пользователя повышен до {new_level}")
    except Exception as e:
        await message.reply(f"❌ Ошибка отправки в чат: {e}")


@app.on_message(filters.command("level_down"))
async def level_down_command(client: Client, message: Message):
    """Понижение уровня в чате"""
    if not ROLE_CHAT_ID:
        await message.reply("❌ Чат для ролей не настроен")
        return
    
    args = message.text.split()
    
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(args) >= 2:
        username = args[1].replace("@", "")
        try:
            target = await client.get_users(username)
        except:
            await message.reply("❌ Пользователь не найден")
            return
    
    if not target:
        await message.reply("<b>📋 Использование:</b> /level_down @username")
        return
    
    # Понижение уровня
    current_role = roles_db.get(str(target.id), {}).get("level", 0)
    new_level = max(0, current_role - 1)
    
    roles_db[str(target.id)] = {
        "user_id": target.id,
        "username": target.username,
        "first_name": target.first_name,
        "level": new_level,
        "updated_at": datetime.now().isoformat()
    }
    save_all_data()
    
    # Отправка сообщения в чат
    try:
        await client.send_message(
            ROLE_CHAT_ID,
            f"""
<b>✨ <i>~ Сияние неба ~</i> ✨</b>

<b>💫 ИЗМЕНЕНИЕ УРОВНЯ 💫</b>

{get_user_mention(target.id, target.username, target.first_name)}, ваш уровень изменен.

Текущий уровень: <b>{new_level} ⭐</b>

<i>Не угасайте! Впереди новые возможности!</i>

#уровень #изменение
""",
            parse_mode=ParseMode.HTML
        )
        await message.reply(f"✅ Уровень пользователя понижен до {new_level}")
    except Exception as e:
        await message.reply(f"❌ Ошибка отправки в чат: {e}")


# ==================== Вспомогательные функции ====================

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


# ==================== Запуск бота ====================

async def main():
    """Главная функция запуска"""
    print("🌟 Запуск бота «Сияние неба»...")
    
    # Загрузка данных
    load_all_data()
    print(f"📊 Загружено пользователей: {len(users_db)}")
    print(f"👑 Загружено администраторов: {len(admins_db)}")
    print(f"📋 Загружено тикетов: {len(tickets_db)}")
    
    # Запуск клиента
    await app.start()
    
    me = await app.get_me()
    print(f"✅ Бот @{me.username} успешно запущен!")
    print("✨ «Сияние неба» готово к работе!")
    
    # Бесконечное ожидание
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        app.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
